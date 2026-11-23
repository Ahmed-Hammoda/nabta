"""Benchmark small models on the Nabta decision task with several prompt designs.

    python run_bench.py --models qwen2.5:0.5b qwen2.5:1.5b            # all configs
    python run_bench.py --models qwen2.5:1.5b --configs v3_fewshot:B --limit 30

Each run is saved to results/<model>__<config>.jsonl and skipped if it already exists,
so the benchmark can be stopped and restarted. Then run: python report.py
"""
import argparse, json, os, time, urllib.request
from labels import label, ALERT_ORDER

URL = "http://127.0.0.1:11434/api/chat"
LEVEL_KEYS = ["moisture_level", "temp_level", "light_level", "humidity_level"]

LEVEL_RULES = """Levels:
- moisture_level (soil moisture index 0-100):
    "too_wet" above 100, "optimal" 90 to 100, "acceptable" above 70 and below 90,
    "dry" above 25 and up to 70, "danger_dry" 25 or below.
- temp_level (air_temp_c): "optimal" 15 to 25, "acceptable" 4 to 36 (outside 15-25), "danger" below 4 or above 36.
- light_level (light_lux_hours_24h): "optimal" 285000 or more, "acceptable" 90000 to 284999, "low" below 90000.
- humidity_level (humidity_rh): "optimal" 60 to 70, otherwise "outside_optimal"."""

NUMBER_DECISION = """Decision:
- water is "yes" if soil_moisture_index is 70 or below, otherwise "no".
- alerts: "DRY_DANGER" if moisture_level is danger_dry, "TOO_WET" if too_wet,
  "HEAT_DANGER" if air_temp_c above 36, "COLD_DANGER" if below 4, "LOW_LIGHT" if light_level is low.
  Use an empty list if there is no alert."""

# v0: the exact prompt from test_model.py (the first experiment)
P_V0 = f"""You are Nabta, the assistant of a smart pot growing spearmint.
You receive the pot's sensor readings and must assess the plant.

{LEVEL_RULES}

{NUMBER_DECISION}

Answer with only this JSON:
{{"water": "yes" or "no", "moisture_level": "...", "temp_level": "...",
 "light_level": "...", "humidity_level": "...", "alerts": [...]}}"""

# v2+: same rules, but the answer order follows the reasoning order (levels -> alerts -> water)
P_ORDERED = f"""You are Nabta, the assistant of a smart pot growing spearmint.
You receive the pot's sensor readings and must assess the plant.
Work in this order: first find each level, then the alerts, and decide water last.

{LEVEL_RULES}

{NUMBER_DECISION}

Answer with JSON only, keys in this order:
moisture_level, temp_level, light_level, humidity_level, alerts, water."""

P_REASON = P_ORDERED + """
Before the answer keys, write "reasoning": one short line that compares each number
with its thresholds, for example "moisture 64.2 <= 70 and > 25 -> dry; temp 22 in 15-25 -> optimal; ..."."""

# v5: code already computed the levels; the model only applies rules written on the levels
P_LEVELS = """You are Nabta, the assistant of a smart pot growing spearmint.
The sensor readings come with levels already computed by the system. Trust the levels.

Rules:
- water is "yes" if moisture_level is "dry" or "danger_dry". Otherwise water is "no".
- alerts (list every one that applies, empty list if none):
    "DRY_DANGER"  if moisture_level is "danger_dry"
    "TOO_WET"     if moisture_level is "too_wet"
    "HEAT_DANGER" if temp_level is "danger" and air_temp_c is above 36
    "COLD_DANGER" if temp_level is "danger" and air_temp_c is below 4
    "LOW_LIGHT"   if light_level is "low"

Answer with JSON only: alerts first, then water."""

ENUMS = {
    "moisture_level": ["too_wet", "optimal", "acceptable", "dry", "danger_dry"],
    "temp_level": ["optimal", "acceptable", "danger"],
    "light_level": ["optimal", "acceptable", "low"],
    "humidity_level": ["optimal", "outside_optimal"],
}


def schema(keys, reasoning=False):
    """JSON schema for Ollama structured outputs: fixed key order and allowed values only."""
    props = {}
    if reasoning:
        props["reasoning"] = {"type": "string"}
    for k in keys:
        if k in ENUMS:
            props[k] = {"type": "string", "enum": ENUMS[k]}
        elif k == "alerts":
            props[k] = {"type": "array", "items": {"type": "string", "enum": ALERT_ORDER}}
        elif k == "water":
            props[k] = {"type": "string", "enum": ["yes", "no"]}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


FULL_KEYS = LEVEL_KEYS + ["alerts", "water"]
MIN_KEYS = ["alerts", "water"]

# Few-shot examples (values chosen so they are not in the test set)
SHOTS = [(64.2, 22.0, 55.0, 150000), (83.0, 31.0, 66.0, 300000),
         (18.5, 38.2, 30.0, 60000), (102.3, 2.5, 80.0, 120000)]


def make_input(vals, dataset, as_string=False, lux_now=0):
    m, t, h, lh = vals
    d = {"soil_moisture_index": m, "air_temp_c": t, "humidity_rh": h,
         "light_lux_now": lux_now, "light_lux_hours_24h": lh}
    if dataset == "B":
        k = label(m, t, h, lh)
        d.update({x: k[x] for x in LEVEL_KEYS})
    if as_string:
        d = {x: str(v) for x, v in d.items()}
    return d


def reasoning_text(m, t, h, lh, k):
    mops = {"too_wet": "> 100", "optimal": "in 90-100", "acceptable": "> 70 and < 90",
            "dry": "<= 70 and > 25", "danger_dry": "<= 25"}
    return (f"moisture {m} {mops[k['moisture_level']]} -> {k['moisture_level']}; "
            f"temp {t} -> {k['temp_level']}; light {lh} -> {k['light_level']}; "
            f"humidity {h} -> {k['humidity_level']}; water {k['water']} because moisture "
            f"{'<=' if k['water'] == 'yes' else '>'} 70")


def shot_messages(dataset, keys, reasoning=False):
    msgs = []
    for vals in SHOTS:
        k = label(*vals)
        ans = {}
        if reasoning:
            ans["reasoning"] = reasoning_text(*vals, k)
        ans.update({x: k[x] for x in keys})
        msgs += [{"role": "user", "content": json.dumps(make_input(vals, dataset))},
                 {"role": "assistant", "content": json.dumps(ans)}]
    return msgs


# name -> (system prompt, answer keys, format, values-as-strings, few-shot, reasoning field)
CONFIGS = {
    "v0_baseline": (P_V0, FULL_KEYS, "json", True, False, False),
    "v1_numbers": (P_V0, FULL_KEYS, "json", False, False, False),
    "v2_schema": (P_ORDERED, FULL_KEYS, "schema", False, False, False),
    "v3_fewshot": (P_ORDERED, FULL_KEYS, "schema", False, True, False),
    "v4_reasoning": (P_REASON, FULL_KEYS, "schema", False, True, True),
    "v5_levels_rules": (P_LEVELS, MIN_KEYS, "schema", False, True, False),
}
DEFAULT_RUNS = [f"{c}:{d}" for c in CONFIGS for d in "AB" if not (c == "v5_levels_rules" and d == "A")]


THINK = None  # None = model default, False = thinking off, True = thinking on (for "thinking" models)


def ask(model, messages, fmt):
    req_body = {"model": model, "stream": False, "format": fmt, "keep_alive": "30m",
                "options": {"temperature": 0, "seed": 1, "num_predict": 400}, "messages": messages}
    if THINK is not None:
        req_body["think"] = THINK
    if THINK:  # thinking needs much more room before the answer
        req_body["options"].update({"num_predict": 7000, "num_ctx": 8192})
    body = json.dumps(req_body).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.loads(r.read())
    return out["message"]["content"], time.time() - t0, out.get("eval_count", 0)


def score(ans, key, keys):
    s = {}
    water = str(ans.get("water", "")).strip().lower()
    s["water_ok"] = water == key["water"]
    s["overwater"] = key["water"] == "no" and water == "yes"
    s["missed_water"] = key["water"] == "yes" and water != "yes"
    got = ans.get("alerts")
    s["alerts_ok"] = isinstance(got, list) and set(got) == set(key["alerts"])
    for lv in LEVEL_KEYS:
        s[lv + "_ok"] = (ans.get(lv) == key[lv]) if lv in keys else None
    s["all_ok"] = s["water_ok"] and s["alerts_ok"] and all(s[lv + "_ok"] is not False for lv in LEVEL_KEYS)
    return s


def run(model, cfg, dataset, cases, outdir):
    prompt, keys, fmt, as_str, fewshot, reasoning = CONFIGS[cfg]
    fmt_value = schema(keys, reasoning) if fmt == "schema" else "json"
    base = [{"role": "system", "content": prompt}]
    if fewshot:
        base += shot_messages(dataset, keys, reasoning)
    suffix = "_think" if THINK else ""
    path = os.path.join(outdir, f"{model.replace(':', '_')}{suffix}__{cfg}_{dataset}.jsonl")
    if os.path.exists(path):
        print("skip (done):", path)
        return
    ask(model, base + [{"role": "user", "content": "{}"}], fmt_value)  # warm-up, not scored
    rows = []
    for n, c in enumerate(cases, 1):
        i = c["input"]
        vals = (i["soil_moisture_index"], i["air_temp_c"], i["humidity_rh"], i["light_lux_hours_24h"])
        user = json.dumps(make_input(vals, dataset, as_str, i["light_lux_now"]))
        raw, secs, ntok = ask(model, base + [{"role": "user", "content": user}], fmt_value)
        try:
            ans, valid = json.loads(raw), True
            if not isinstance(ans, dict):
                ans, valid = {}, False
        except json.JSONDecodeError:
            ans, valid = {}, False
        rows.append({"id": c["id"], "kind": c["kind"], "seconds": round(secs, 3), "tokens": ntok,
                     "valid_json": valid, **score(ans, c["key"], keys), "answer": raw, "key": c["key"]})
        if n % 25 == 0:
            print(f"  {model} {cfg}:{dataset} {n}/{len(cases)} water ok {sum(r['water_ok'] for r in rows)}/{n}")
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print("saved", path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["qwen2.5:0.5b", "qwen2.5:1.5b"])
    ap.add_argument("--configs", nargs="+", default=DEFAULT_RUNS, help="config:dataset, e.g. v3_fewshot:B")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="results")
    ap.add_argument("--think", choices=["default", "off", "on"], default="default",
                    help="thinking mode for models that support it (e.g. qwen3.5)")
    a = ap.parse_args()
    global THINK
    THINK = {"default": None, "off": False, "on": True}[a.think]
    os.makedirs(a.out, exist_ok=True)
    cases = [json.loads(l) for l in open("testset.jsonl")]
    if a.limit:
        cases = cases[:a.limit]
    for model in a.models:
        for rc in a.configs:
            cfg, ds = rc.split(":")
            run(model, cfg, ds, cases, a.out)


if __name__ == "__main__":
    main()
