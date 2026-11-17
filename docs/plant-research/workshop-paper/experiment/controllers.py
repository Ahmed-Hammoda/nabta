"""
The four controllers compared in the paper, and the shared safety gate. Standard library only.

  C1 threshold : index < 60 -> 150 mL. Nothing else (no gap, no day cap, no tank or fault check).
  C2 multirule : threshold + refill-to-88 dose + 150 mL dose cap + 500 mL/day + 2 h gap
                 + tank-low and sensor-fault checks. This is also the REFERENCE for RQ2.
  C3 / C4 llm  : Qwen3.5 0.8B on the Pi (C3) and the ChatGPT API (C4), frozen prompt and params.

Gate policy (config "gate"): by default C2-C4 pass the safety gate and C1 does NOT, so C1 is a
true naive baseline; the gate is still evaluated on C1 and logged as "would_block".
TODO(team): confirm. Set gate.apply_to_threshold=true to gate C1 too.
"""
import json, os, re, time, urllib.request
from datetime import datetime


def soil_index(ctx):
    latest = ctx["latest"]
    return latest.get("soil_index_median_5min", latest.get("soil_index_median_15min"))


def hours_since_watering(ctx):
    """last_watering may be {"hours_ago": h, ...}, an ISO timestamp string, or null."""
    lw = ctx.get("last_watering")
    if isinstance(lw, dict):
        return lw.get("hours_ago", 99)
    if isinstance(lw, str) and ctx.get("timestamp"):
        return (datetime.fromisoformat(ctx["timestamp"]) - datetime.fromisoformat(lw)).total_seconds() / 3600
    return 99


# ---------------------------------------------------------------- C1
def threshold_controller(ctx, prof):
    idx = soil_index(ctx)
    if idx is not None and idx < prof["water_below_index"]:
        return {"action": "water", "ml": int(prof["threshold_dose_ml"])}
    return {"action": "no_water", "ml": 0}


# ---------------------------------------------------------------- C2
def multirule_controller(ctx, prof):
    latest, idx = ctx["latest"], soil_index(ctx)
    if latest.get("tank_low") or latest.get("sensor_fault_flag") or idx is None:
        return {"action": "no_water", "ml": 0}
    if idx < prof["water_below_index"] and hours_since_watering(ctx) >= prof["min_gap_h"]:
        need = (prof["refill_to_index"] - idx) / 100 * prof["pot_awc_ml"]
        ml = min(need, prof["dose_cap_ml"], prof["day_cap_ml"] - ctx.get("given_today_ml", 0))
        if ml > 0:
            return {"action": "water", "ml": int(round(ml))}
    return {"action": "no_water", "ml": 0}


# ---------------------------------------------------------------- gate
def safety_gate(ans, ctx, prof):
    """Returns (final_action, final_ml, intervention or None)."""
    if ans is None:
        return "no_water", 0, "invalid_or_no_answer"
    action, ml = ans.get("action"), ans.get("ml", 0)
    if action not in ("water", "no_water") or not isinstance(ml, (int, float)):
        return "no_water", 0, "schema"
    if action == "no_water":
        return "no_water", 0, None
    idx = soil_index(ctx)
    if ctx["latest"].get("tank_low"):
        return "no_water", 0, "blocked_tank_low"
    if idx is not None and idx >= prof["hard_block_above"]:
        return "no_water", 0, "blocked_too_wet"
    if hours_since_watering(ctx) < prof["min_gap_h"]:
        return "no_water", 0, "blocked_min_gap"
    room = prof["day_cap_ml"] - ctx.get("given_today_ml", 0)
    if room <= 0:
        return "no_water", 0, "blocked_day_cap"
    clipped = min(ml, prof["dose_cap_ml"], room)
    if clipped <= 0:
        return "no_water", 0, "schema"
    return "water", int(clipped), ("clipped_dose" if clipped < ml else None)


# ---------------------------------------------------------------- LLM
def parse(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        return d if isinstance(d, dict) else None
    except json.JSONDecodeError:
        return None


def llm_view(ctx):
    """What the LLM sees: the live context without any reference answer."""
    return {k: v for k, v in ctx.items() if k not in ("rules_decision", "case_id")}


def call_llm(ctrl, cfg, ctx):
    """Returns (text, latency_s, prompt_tokens, completion_tokens)."""
    p = cfg["params"]
    body = {"model": ctrl["model"], "temperature": p["temperature"], "top_p": p["top_p"],
            "max_tokens": p["max_tokens"], "seed": p["seed"],
            "messages": [{"role": "system", "content": cfg["system_prompt"]},
                         {"role": "user", "content": json.dumps(llm_view(ctx))}]}
    if ctrl.get("where") != "cloud":
        body["options"] = {"num_ctx": p["num_ctx"]}  # Ollama-specific
    key = os.environ.get(ctrl.get("api_key_env", ""), "ollama")
    req = urllib.request.Request(ctrl["base_url"].rstrip("/") + "/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=p["timeout_s"]) as r:
        data = json.loads(r.read())
    usage = data.get("usage") or {}
    return (data["choices"][0]["message"]["content"], time.time() - t0,
            usage.get("prompt_tokens"), usage.get("completion_tokens"))


def mock_llm(ctrl, ctx, prof, rng):
    """Fake LLM for dry runs: follows C2 with noise (more noise for the small model)."""
    noise = 0.25 if ctrl.get("where") == "pi" else 0.06
    if rng.random() < noise / 3:
        return "Sure! I think you should water.", rng.uniform(4, 12), 600, 12
    ref = multirule_controller(ctx, prof)
    if rng.random() < noise:
        ref = ({"action": "water", "ml": rng.choice([100, 150, 200])} if ref["action"] == "no_water"
               else {"action": "no_water", "ml": 0})
    lat = rng.uniform(4, 12) if ctrl.get("where") == "pi" else rng.uniform(0.6, 2.0)
    return json.dumps({**ref, "reason": "mock"}), lat, 600, 30


def decide(ctrl, cfg, ctx, rng=None, mock=False):
    """Run one controller on one context. Returns a log record (without reference fields)."""
    prof = cfg["plant_profile"]
    rec = {"controller": ctrl["id"], "kind": ctrl["kind"], "name": ctrl.get("model", ctrl["kind"]),
           "where": ctrl.get("where", "pi"), "raw": None, "latency_s": 0.0, "prompt_tokens": None,
           "completion_tokens": None, "cost_usd": 0.0, "error": None}
    if ctrl["kind"] in ("threshold", "multirule"):
        t0 = time.perf_counter()
        ans = (threshold_controller if ctrl["kind"] == "threshold" else multirule_controller)(ctx, prof)
        rec["latency_s"] = time.perf_counter() - t0
    else:
        try:
            text, lat, pt, ct = mock_llm(ctrl, ctx, prof, rng) if mock else call_llm(ctrl, cfg, ctx)
            rec.update(raw=text, latency_s=lat, prompt_tokens=pt, completion_tokens=ct)
            price = ctrl.get("price_usd_per_1m", {"input": 0, "output": 0})
            rec["cost_usd"] = ((pt or 0) * price["input"] + (ct or 0) * price["output"]) / 1e6
        except Exception as e:  # timeout / no network counts as "no answer"
            text, rec["latency_s"], rec["error"] = None, None, type(e).__name__
        ans = parse(text)
    valid = ans is not None and ans.get("action") in ("water", "no_water")
    act, ml, gate = safety_gate(ans, ctx, prof)
    gated = ctrl["kind"] != "threshold" or cfg["gate"].get("apply_to_threshold", False)
    if not gated:  # C1 acts ungated; record what the gate would have done
        act, ml = (ans["action"], ans["ml"])
        rec["would_block"] = gate
        gate = None
    rec.update(valid_json=valid, proposed_action=(ans or {}).get("action") if valid else None,
               proposed_ml=(ans or {}).get("ml") if valid else None,
               final_action=act, final_ml=ml, gate=gate, actuates=ctrl.get("actuates_pot"))
    return rec
