"""Test the small models on the simulated 30-day log, version 2.

Test A  "AI decides": the model gets only the raw sensor numbers (no levels from code) and must give
        water + alerts. Prompts v0 (original) and v3 (JSON schema + 4 solved examples), with the v2 rules.
Test B  "hybrid": rules_v2 decides; the model only explains (prompt e3). Fault rows get a fixed message.

Cases: a stratified sample of the v2 key (up to 20 rows per scenario) + every fault row.

    python sim_bench_v2.py --models qwen3.5:0.8b lfm3:1.7b
    python sim_bench_v2.py --report
"""
import argparse, csv, json, os, random, time, urllib.error, urllib.request
from collections import Counter, defaultdict

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "simulation_phase1", "bench"))  # phase-1 code (labels, explain_bench, run_bench)
import explain_bench as eb
import rules_v2
from run_bench import schema, score, FULL_KEYS

URL = "http://127.0.0.1:11434/api/chat"
HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(HERE, "..", "dataset")
OUT = os.path.join(HERE, "..", "results")
NO_THINK_FLAG = set()                            # models that reject think=false (filled at run time)
eb.THRESHOLDS.append(rules_v2.TOO_WET_AT)        # 98 is now a threshold the explainer may quote

LEVEL_RULES_V2 = f"""Levels:
- moisture_level (soil moisture index 0-100):
    "too_wet" {rules_v2.TOO_WET_AT} or above, "optimal" 90 to below {rules_v2.TOO_WET_AT}, "acceptable" above 70 and below 90,
    "dry" above 25 and up to 70, "danger_dry" 25 or below.
- temp_level (air_temp_c): "optimal" 15 to 25, "acceptable" 4 to 36 (outside 15-25), "danger" below 4 or above 36.
- light_level (light_lux_hours_24h): "optimal" 285000 or more, "acceptable" 90000 to 284999, "low" below 90000.
- humidity_level (humidity_rh): "optimal" 60 to 70, otherwise "outside_optimal"."""

DECISION = """Decision:
- water is "yes" if soil_moisture_index is 70 or below, otherwise "no".
- alerts: "DRY_DANGER" if moisture_level is danger_dry, "TOO_WET" if too_wet,
  "HEAT_DANGER" if air_temp_c above 36, "COLD_DANGER" if below 4, "LOW_LIGHT" if light_level is low.
  Use an empty list if there is no alert."""

P_V0 = f"""You are Nabta, the assistant of a smart pot growing spearmint.
You receive the pot's sensor readings and must assess the plant.

{LEVEL_RULES_V2}

{DECISION}

Answer with only this JSON:
{{"water": "yes" or "no", "moisture_level": "...", "temp_level": "...",
 "light_level": "...", "humidity_level": "...", "alerts": [...]}}"""

P_V3 = f"""You are Nabta, the assistant of a smart pot growing spearmint.
You receive the pot's sensor readings and must assess the plant.
Work in this order: first find each level, then the alerts, and decide water last.

{LEVEL_RULES_V2}

{DECISION}

Answer with JSON only, keys in this order:
moisture_level, temp_level, light_level, humidity_level, alerts, water."""

SHOTS = [(64.2, 22.0, 55.0, 30.0, 150000), (83.0, 31.0, 66.0, 900.0, 300000),
         (18.5, 38.2, 30.0, 20000.0, 60000), (99.0, 2.5, 80.0, 0.0, 120000)]
COLS = ["soil_moisture_index", "air_temp_c", "humidity_rh", "light_lux_now", "light_lux_hours_24h"]

# ---- improved prompts (the model still decides everything; nothing is computed by code) ----
SENSOR_LINE = """- If soil_moisture_index is 2 or below, the soil sensor is broken (it reads like dry air):
  water is "no", and do not give DRY_DANGER or TOO_WET."""

# 14 solved examples: every band, every exact limit, and a broken sensor
MANY_SHOTS = [(64.2, 22.0, 55.0, 30.0, 150000), (83.0, 31.0, 66.0, 900.0, 300000),
              (18.5, 38.2, 30.0, 20000.0, 60000), (99.0, 2.5, 80.0, 0.0, 120000),
              (70.0, 20.0, 62.0, 5000.0, 200000), (70.3, 18.0, 58.0, 200.0, 95000),
              (25.0, 26.0, 45.0, 0.0, 310000), (25.4, 24.0, 50.0, 0.0, 89000),
              (97.6, 12.0, 85.0, 0.0, 286000), (98.0, 16.0, 90.0, 1500.0, 40000),
              (91.2, 36.4, 22.0, 61000.0, 340000), (88.5, 3.8, 88.0, 0.0, 100000),
              (45.0, 36.0, 40.0, 50000.0, 284999), (1.2, 23.0, 57.0, 40.0, 500)]
FEW_SHOTS = [MANY_SHOTS[i] for i in (0, 2, 3, 4, 5, 9, 12, 13)]

P_MANY = f"""You are Nabta, the assistant of a smart pot growing spearmint.
You receive the pot's sensor readings and must decide everything yourself.
Work in this order: first find each level, then the alerts, and decide water last.

{LEVEL_RULES_V2}

{DECISION}
{SENSOR_LINE}

Compare every number with its limit carefully. "70 or below" includes 70.0; "above 36" does not include 36.0.
The solved examples show exactly how to decide; follow them.

Answer with JSON only, keys in this order:
moisture_level, temp_level, light_level, humidity_level, alerts, water."""

P_MIN = f"""You are Nabta, the assistant of a smart pot growing spearmint.
You receive the pot's sensor readings and must decide two things: the alerts and whether to water.

Rules:
- water is "yes" if soil_moisture_index is 70 or below (70.0 included), otherwise "no".
- alerts (list every one that applies, empty list if none):
    "DRY_DANGER"  if soil_moisture_index is 25 or below
    "TOO_WET"     if soil_moisture_index is {rules_v2.TOO_WET_AT} or above
    "HEAT_DANGER" if air_temp_c is above 36 (36.0 is not above 36)
    "COLD_DANGER" if air_temp_c is below 4
    "LOW_LIGHT"   if light_lux_hours_24h is below 90000
{SENSOR_LINE}

The solved examples show exactly how to decide; follow them.
Answer with JSON only: alerts first, then water."""

CHECK_KEYS = ["sensor_broken", "soil_70_or_below", "soil_25_or_below", "soil_98_or_above",
              "temp_above_36", "temp_below_4", "light_below_90000"]
P_CHECK = f"""You are Nabta, the assistant of a smart pot growing spearmint.
You receive the pot's sensor readings and must decide everything yourself, in small steps.

Step 1. Answer each question with true or false by comparing ONE number with ONE limit:
- sensor_broken:      soil_moisture_index is 2 or below
- soil_70_or_below:   soil_moisture_index is 70 or below (70.0 gives true)
- soil_25_or_below:   soil_moisture_index is 25 or below (25.0 gives true)
- soil_98_or_above:   soil_moisture_index is {rules_v2.TOO_WET_AT} or above
- temp_above_36:      air_temp_c is above 36 (36.0 gives false)
- temp_below_4:       air_temp_c is below 4
- light_below_90000:  light_lux_hours_24h is below 90000

Step 2. Use only your answers from step 1:
- alerts: "DRY_DANGER" if soil_25_or_below and not sensor_broken;
          "TOO_WET" if soil_98_or_above and not sensor_broken;
          "HEAT_DANGER" if temp_above_36; "COLD_DANGER" if temp_below_4; "LOW_LIGHT" if light_below_90000.
          Empty list if none.
- water: "yes" if soil_70_or_below is true and sensor_broken is false, otherwise "no".

Answer with JSON only, keys in this order: {", ".join(CHECK_KEYS)}, alerts, water."""


def check_answers(m, t, h, ln, lh):
    """True/false answers for the solved examples only (the model computes its own)."""
    return {"sensor_broken": m <= 2, "soil_70_or_below": m <= 70, "soil_25_or_below": m <= 25,
            "soil_98_or_above": m >= rules_v2.TOO_WET_AT, "temp_above_36": t > 36, "temp_below_4": t < 4,
            "light_below_90000": lh < 90000}


def check_schema():
    props = {k: {"type": "boolean"} for k in CHECK_KEYS}
    props.update(schema(["alerts", "water"])["properties"])
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


# p5 = v3 + the broken-sensor rule + one broken-sensor example (so v3 is told about faults like p1-p4)
assert DECISION in P_V3
P_V3S = P_V3.replace(DECISION, DECISION + "\n" + SENSOR_LINE)
SHOTS_S = SHOTS + [(1.2, 23.0, 57.0, 40.0, 500)]

# p6 = p5 + a clear line between "broken" (2 or below) and "very dry" (above 2), with 2 contrast examples
SENSOR_LINE_2 = SENSOR_LINE + """
- Only 2 or below means broken. Any reading above 2 is real soil: for example 3.5 or 12.5 is very dry soil,
  so water is "yes" and DRY_DANGER is given when it is 25 or below."""
P_V3S2 = P_V3.replace(DECISION, DECISION + "\n" + SENSOR_LINE_2)
SHOTS_S2 = SHOTS_S + [(12.5, 21.0, 50.0, 300.0, 200000), (3.5, 19.0, 60.0, 0.0, 95000)]

# name -> (system prompt, answer keys, examples)
PROMPTS = {
    "v0": (P_V0, FULL_KEYS, []),
    "v3": (P_V3, FULL_KEYS, SHOTS),
    "p1": (P_MANY, FULL_KEYS, MANY_SHOTS),
    "p2": (P_MIN, ["alerts", "water"], MANY_SHOTS),
    "p3": (P_CHECK, CHECK_KEYS + ["alerts", "water"], []),
    "p4": (P_CHECK, CHECK_KEYS + ["alerts", "water"], FEW_SHOTS),
    "p5": (P_V3S, FULL_KEYS, SHOTS_S),
    "p6": (P_V3S2, FULL_KEYS, SHOTS_S2),
    "ft": (None, None, []),            # fine-tuned model: short system prompt, no rules, no examples (set below)
}
import make_train_data as _mtd
PROMPTS["ft"] = (_mtd.SYSTEM, _mtd.KEYS, [])


def load_cases():
    sens = list(csv.DictReader(open(os.path.join(SIM, "sim_sensor_30days.csv"), encoding="utf-8")))
    key = list(csv.DictReader(open(os.path.join(SIM, "sim_key_30days.csv"), encoding="utf-8")))
    by = defaultdict(list)
    for n, (s, k) in enumerate(zip(sens, key)):
        inp = {c: float(s[c]) for c in COLS}
        alerts = [] if k["alerts"] == "none" else k["alerts"].split(";")
        faults = [] if k["faults"] == "none" else k["faults"].split(";")
        c = {"id": f"s{n:04d}", "time": s["timestamp"][:16], "scenario": k["scenario"], "input": inp,
             "key": {"moisture_level": k["moisture_level"], "temp_level": k["temp_level"],
                     "light_level": k["light_level"], "humidity_level": k["humidity_level"],
                     "alerts": alerts, "water": k["water"]},
             "faults": faults, "fault_reason": k["fault_reason"]}
        by["FAULT" if faults else k["scenario"]].append(c)
    rnd = random.Random(7)
    cases = list(by.pop("FAULT", []))
    for scen in sorted(by):
        rows = by[scen]
        cases += sorted(rnd.sample(rows, min(20, len(rows))), key=lambda c: c["id"])
    return cases


THINK = False          # --think: let thinking models reason before answering


def ask(model, msgs, fmt=None, num_predict=400):
    if THINK:
        num_predict = 6000                       # thinking tokens count towards the limit
        num_ctx = 12288                          # default 4096 cut lfm3 off mid-thought
    body = {"model": model, "stream": False, "keep_alive": "30m", "messages": msgs,
            "options": {"temperature": 0, "seed": 1, "num_predict": num_predict}}
    if THINK:
        body["options"]["num_ctx"] = num_ctx
    if fmt is not None:
        body["format"] = fmt
    if model not in NO_THINK_FLAG:
        body["think"] = THINK                    # off by default: thinking models loop or run out of tokens
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            out = json.loads(r.read())
    except urllib.error.HTTPError as e:
        if "think" in body and "think" in e.read().decode(errors="replace").lower():
            NO_THINK_FLAG.add(model)
            return ask(model, msgs, fmt, num_predict)
        raise
    ask.last_thinking = out["message"].get("thinking") or ""
    ask.last_tokens = out.get("eval_count", 0)
    return out["message"]["content"].strip(), time.time() - t0


def decide_messages(cfg, inp):
    prompt, keys, shots = PROMPTS[cfg]
    msgs = [{"role": "system", "content": prompt}]
    for vals in shots:
        shot = dict(zip(COLS, vals))
        k = rules_v2.decide(shot)            # the correct answer of the example
        ans = {**check_answers(*vals), **k}
        msgs += [{"role": "user", "content": json.dumps(shot)},
                 {"role": "assistant", "content": json.dumps({x: ans[x] for x in keys})}]
    user = {k: str(v) for k, v in inp.items()} if cfg == "v0" else inp   # v0 as in the original test_model.py
    msgs.append({"role": "user", "content": json.dumps(user)})
    return msgs


def fmt_for(cfg):
    if cfg in ("v0", "ft"):
        return "json"
    keys = PROMPTS[cfg][1]
    return check_schema() if keys[0] == "sensor_broken" else schema(keys)


def run_decide(model, cfg, cases):
    path = os.path.join(OUT, f"{model.replace(':', '_')}{'_think' if THINK else ''}__A_{cfg}.jsonl")
    if os.path.exists(path):
        print("skip (done):", path); return
    fmt = fmt_for(cfg)
    keys = PROMPTS[cfg][1]
    ask(model, decide_messages(cfg, cases[0]["input"]), fmt)  # warm-up
    rows = []
    for c in cases:
        raw, secs = ask(model, decide_messages(cfg, c["input"]), fmt)
        try:
            ans = json.loads(raw); ans = ans if isinstance(ans, dict) else {}
            valid = bool(ans)
        except json.JSONDecodeError:
            ans, valid = {}, False
        s = score(ans, c["key"], keys)
        rows.append({"id": c["id"], "time": c["time"], "scenario": c["scenario"], "fault": bool(c["faults"]),
                     "seconds": round(secs, 3), "valid_json": valid, **s, "answer": raw, "key": c["key"],
                     "tokens": ask.last_tokens, "thinking": ask.last_thinking})
    with open(path, "w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    print("saved", path)


def run_explain(model, cases):
    path = os.path.join(OUT, f"{model.replace(':', '_')}__B_e3.jsonl")
    if os.path.exists(path):
        print("skip (done):", path); return
    ask(model, eb.messages("e3", cases[-1]), num_predict=150)  # warm-up
    rows = []
    for c in cases:
        if c["faults"]:   # the system never asks the model about a fault: fixed message
            f = c["faults"][0]
            text = rules_v2.FAULT_MESSAGE[f].format(reason=c["fault_reason"])
            rows.append({"id": c["id"], "time": c["time"], "scenario": c["scenario"], "fault": True,
                         "seconds": 0.0, "explanation": text}); continue
        text, secs = ask(model, eb.messages("e3", c), num_predict=150)
        rows.append({"id": c["id"], "time": c["time"], "scenario": c["scenario"], "fault": False,
                     "seconds": round(secs, 3), "decision": c["key"]["water"], "alerts": c["key"]["alerts"],
                     "moisture": c["input"]["soil_moisture_index"], "explanation": text, **eb.check(text, c)})
    with open(path, "w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    print("saved", path)


def _water(raw):
    try:
        a = json.loads(raw)
        return str(a.get("water", "")).strip().lower() if isinstance(a, dict) else ""
    except json.JSONDecodeError:
        return ""


def pct(a, b): return f"{100 * a / b:5.1f}" if b else "  -  "


def report():
    cases = load_cases()
    normal = [c for c in cases if not c["faults"]]
    no_rate = sum(c["key"]["water"] == "no" for c in normal) / len(normal)
    none_alert = sum(not c["key"]["alerts"] for c in normal) / len(normal)
    lines = [f"Cases: {len(cases)} ({len(normal)} normal + {len(cases) - len(normal)} fault rows)",
             f"Baseline 'always no water': {100 * no_rate:.1f} % water correct; 'never alert': {100 * none_alert:.1f} % alerts correct", ""]
    lines.append("TEST A - the model decides alone from raw numbers (normal rows)")
    lines.append(f"{'model':<14}{'prompt':<7}{'water %':>8}{'alerts %':>9}{'both %':>8}{'overwater':>10}{'missed':>7}"
                 f"{'no decision':>12}{'fault rows watered':>20}{'s/case':>8}")
    summary = []
    for f in sorted(os.listdir(OUT)):
        if "__A_" not in f: continue
        rows = [json.loads(l) for l in open(os.path.join(OUT, f), encoding="utf-8")]
        model, cfg = f[:-6].split("__A_")
        nr = [r for r in rows if not r["fault"]]; fr = [r for r in rows if r["fault"]]
        fault_watered = sum(_water(r["answer"]) == "yes" for r in fr)
        sec = sum(r["seconds"] for r in rows) / len(rows)
        lines.append(f"{model:<14}{cfg:<7}{pct(sum(r['water_ok'] for r in nr), len(nr)):>8}"
                     f"{pct(sum(r['alerts_ok'] for r in nr), len(nr)):>9}{pct(sum(r['water_ok'] and r['alerts_ok'] for r in nr), len(nr)):>8}"
                     f"{sum(r['overwater'] for r in nr):>10}{sum(r['missed_water'] for r in nr):>7}"
                     f"{sum(_water(r['answer']) not in ('yes', 'no') for r in rows):>12}{f'{fault_watered}/{len(fr)}':>20}{sec:>8.2f}")
        summary.append({"test": "A", "model": model, "prompt": cfg,
                        "water_pct": round(100 * sum(r['water_ok'] for r in nr) / len(nr), 1),
                        "alerts_pct": round(100 * sum(r['alerts_ok'] for r in nr) / len(nr), 1),
                        "both_pct": round(100 * sum(r['water_ok'] and r['alerts_ok'] for r in nr) / len(nr), 1),
                        "overwater": sum(r['overwater'] for r in nr), "missed": sum(r['missed_water'] for r in nr),
                        "fault_rows_watered": fault_watered, "sec_per_case_laptop": round(sec, 2)})
        # alert misses by type
        miss = Counter(); fake = Counter()
        for r in nr:
            try: got = set(json.loads(r["answer"]).get("alerts") or [])
            except Exception: got = set()
            for a in r["key"]["alerts"]:
                if a not in got: miss[a] += 1
            for a in got - set(r["key"]["alerts"]): fake[a] += 1
        need = Counter(a for r in nr for a in r["key"]["alerts"])
        lines.append("      missed alerts: " + ", ".join(f"{a} {miss[a]}/{need[a]}" for a in rules_v2.ALERT_ORDER if need[a])
                     + ("   invented: " + ", ".join(f"{a} {n}" for a, n in fake.items()) if fake else ""))
    ranked = sorted([x for x in summary if x["test"] == "A"],
                    key=lambda x: (-x["both_pct"], -x["water_pct"], x["overwater"] + x["missed"], x["fault_rows_watered"]))
    lines += ["", "RANKING (water and alerts both correct, then water, then fewest watering errors)"]
    for n, x in enumerate(ranked, 1):
        lines.append(f"{n:>3}. {x['model']:<14}{x['prompt']:<5} both {x['both_pct']:5.1f} %  water {x['water_pct']:5.1f} %  "
                     f"alerts {x['alerts_pct']:5.1f} %  over/missed {x['overwater']}/{x['missed']}  "
                     f"broken sensor watered {x['fault_rows_watered']}/10  {x['sec_per_case_laptop']:.2f} s")
    blen = len(lines)
    lines += ["", "TEST B - rules decide, the model explains (prompt e3, normal rows)"]
    checks = ["c1_same_action", "c2_no_invented_numbers", "c3_moisture_quoted", "c4_all_alerts_mentioned",
              "c5_no_fake_alert", "c6_short"]
    lines.append(f"{'model':<14}" + "".join(f"{c[:12]:>14}" for c in checks) + f"{'all pass':>10}{'s/case':>8}")
    for f in sorted(os.listdir(OUT)):
        if "__B_" not in f: continue
        rows = [json.loads(l) for l in open(os.path.join(OUT, f), encoding="utf-8")]
        cmap = {c["id"]: c for c in cases}
        nr = [{**r, **eb.check(r["explanation"], cmap[r["id"]])} for r in rows if not r["fault"]]
        allp = sum(all(r[c] for c in checks if c != "c3_moisture_quoted") for r in nr)
        sec = sum(r["seconds"] for r in nr) / len(nr)
        model = f.split("__B_")[0]
        lines.append(f"{model:<14}" + "".join(f"{pct(sum(r[c] for r in nr), len(nr)):>14}" for c in checks)
                     + f"{pct(allp, len(nr)):>10}{sec:>8.2f}")
        summary.append({"test": "B", "model": model, "prompt": "e3",
                        **{c: round(100 * sum(r[c] for r in nr) / len(nr), 1) for c in checks},
                        "all_pass_pct": round(100 * allp / len(nr), 1), "sec_per_case_laptop": round(sec, 2)})
    lines.append("(all pass = every check except c3; a fault row always gets the fixed message)")
    if not any("__B_" in f for f in os.listdir(OUT)):
        lines = lines[:blen]                  # Test B dropped in this phase
    txt = "\n".join(lines)
    print(txt)
    open(os.path.join(OUT, "summary.txt"), "w", encoding="utf-8").write(txt + "\n")
    keys = sorted({k for s in summary for k in s}, key=lambda k: list(summary[0]).index(k) if k in summary[0] else 99)
    with open(os.path.join(OUT, "summary.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys([k for s in summary for k in s])))
        w.writeheader(); w.writerows(summary)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["qwen3.5:0.8b", "lfm3:1.7b", "granite4:1b-h", "qwen3:1.7b",
                                                    "llama3.2:1b"])
    ap.add_argument("--tests", nargs="+", default=[f"A_{p}" for p in PROMPTS])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--think", action="store_true", help="turn thinking on (results saved as <model>_think)")
    ap.add_argument("--out", default=None, help="results folder (default: simulation_phase2/results)")
    a = ap.parse_args()
    global OUT, THINK
    THINK = a.think
    OUT = a.out or OUT
    os.makedirs(OUT, exist_ok=True)
    if a.report:
        return report()
    cases = load_cases()
    if a.limit:
        cases = cases[:a.limit]
    print(f"{len(cases)} cases")
    for model in a.models:
        for t in a.tests:
            t0 = time.time()
            if t == "B": run_explain(model, cases)
            else: run_decide(model, t.split("_")[1], cases)
            print(f"  {model} {t}: {time.time() - t0:.0f} s")
    report()


if __name__ == "__main__":
    main()
