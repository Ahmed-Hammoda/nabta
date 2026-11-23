"""Run the final explainer (qwen3.5:0.8b, prompt e3) on a live Nabta log.

The rules (labels.py) decide; the model only explains; explain_bench.check() scores each answer.

    python live_explain.py "C:/Users/hamou/Downloads/log_30min (1).csv"
"""
import csv, json, os, sys

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "simulation_phase1", "bench"))  # phase-1 code (labels, explain_bench, run_bench)
from labels import label
from explain_bench import messages, ask, check

MODEL = "qwen3.5:0.8b"


def main(path):
    cases = []
    for n, r in enumerate(csv.DictReader(open(path, encoding="utf-8"))):
        i = {"soil_moisture_index": float(r["soil_moisture_index"]), "air_temp_c": float(r["air_temp_c"]),
             "humidity_rh": float(r["humidity_rh"]), "light_lux_now": float(r["light_lux_now"]),
             "light_lux_hours_24h": float(r["light_lux_hours_24h"])}
        k = label(i["soil_moisture_index"], i["air_temp_c"], i["humidity_rh"], i["light_lux_hours_24h"])
        cases.append({"id": f"live{n:02d}", "time": r["timestamp"][11:16], "input": i, "key": k})

    res = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(res, exist_ok=True)
    out = os.path.join(res, os.path.splitext(os.path.basename(path))[0].replace(" ", "_") + ".jsonl")
    ask(MODEL, messages("e3", cases[0]), False)  # warm-up
    rows = []
    for c in cases:
        text, secs = ask(MODEL, messages("e3", c), False)
        rows.append({"id": c["id"], "time": c["time"], "moisture": c["input"]["soil_moisture_index"],
                     "decision": c["key"]["water"], "alerts": c["key"]["alerts"], "seconds": round(secs, 2),
                     "explanation": text, **check(text, c)})
        print(f"{c['time']}  m={c['input']['soil_moisture_index']:5.1f}  water={c['key']['water']:<3} "
              f"{','.join(c['key']['alerts']) or 'none':<20} {secs:4.1f}s  {text}")
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    checks = ["c1_same_action", "c2_no_invented_numbers", "c3_moisture_quoted",
              "c4_all_alerts_mentioned", "c5_no_fake_alert", "c6_short"]
    print(f"\n{len(rows)} explanations, {sum(r['seconds'] for r in rows) / len(rows):.2f} s each")
    for k in checks:
        bad = [r["time"] for r in rows if not r[k]]
        print(f"  {k:<26} {100 * (len(rows) - len(bad)) / len(rows):5.1f} %  {('failed: ' + ', '.join(bad)) if bad else ''}")
    print("saved", out)


if __name__ == "__main__":
    main(sys.argv[1])
