"""Test a small language model on Nabta's datasets A and B with Ollama.

Usage (in the folder with the CSV files):
    python test_model.py qwen2.5:1.5b A
    python test_model.py qwen2.5:1.5b B
    python test_model.py qwen2.5:1.5b A --rows 30      # quicker run

Needs only Python 3 and Ollama running (no pip install).
"""
import argparse, csv, json, random, time, urllib.request
from collections import defaultdict

OLLAMA_URL = "http://localhost:11434/api/chat"

SYSTEM_PROMPT = """You are Nabta, the assistant of a smart pot growing spearmint.
You receive the pot's sensor readings and must assess the plant.

Levels:
- moisture_level (soil moisture index 0-100):
    "too_wet" above 100, "optimal" 90 to 100, "acceptable" above 70 and below 90,
    "dry" above 25 and up to 70, "danger_dry" 25 or below.
- temp_level (air_temp_c): "optimal" 15 to 25, "acceptable" 4 to 36 (outside 15-25), "danger" below 4 or above 36.
- light_level (light_lux_hours_24h): "optimal" 285000 or more, "acceptable" 90000 to 284999, "low" below 90000.
- humidity_level (humidity_rh): "optimal" 60 to 70, otherwise "outside_optimal".

Decision:
- water is "yes" if soil_moisture_index is 70 or below, otherwise "no".
- alerts: "DRY_DANGER" if moisture_level is danger_dry, "TOO_WET" if too_wet,
  "HEAT_DANGER" if air_temp_c above 36, "COLD_DANGER" if below 4, "LOW_LIGHT" if light_level is low.
  Use an empty list if there is no alert.

Answer with only this JSON:
{"water": "yes" or "no", "moisture_level": "...", "temp_level": "...",
 "light_level": "...", "humidity_level": "...", "alerts": [...]}"""

LEVELS = ["moisture_level", "temp_level", "light_level", "humidity_level"]


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def pick_rows(key, n, seed):
    """Balanced sample: same rows for A and B because the seed is fixed."""
    groups = defaultdict(list)
    for rid, k in key.items():
        groups[(k["water"], k["light_level"], k["temp_level"])].append(rid)
    rng = random.Random(seed)
    for g in groups.values():
        rng.shuffle(g)
    chosen, i = [], 0
    while len(chosen) < n and any(i < len(g) for g in groups.values()):
        for g in sorted(groups):
            if i < len(groups[g]) and len(chosen) < n:
                chosen.append(groups[g][i])
        i += 1
    return sorted(chosen)


def ask(model, row):
    data = {k: v for k, v in row.items() if k not in ("id", "timestamp")}
    body = json.dumps({
        "model": model, "stream": False, "format": "json",
        "options": {"temperature": 0},
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": json.dumps(data)}],
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
    start = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        out = json.loads(resp.read())
    return out["message"]["content"], time.time() - start


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("dataset", choices=["A", "B"])
    ap.add_argument("--rows", type=int, default=60)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    data = load("dataset_A_numbers.csv" if args.dataset == "A" else "dataset_B_numbers_levels.csv")
    key = load("answer_key.csv")
    ids = pick_rows(key, args.rows, args.seed)

    ask(args.model, data[ids[0]])  # warm-up: loads the model, not timed

    results, score = [], defaultdict(int)
    for n, rid in enumerate(ids, 1):
        raw, secs = ask(args.model, data[rid])
        k = key[rid]
        try:
            ans = json.loads(raw)
            valid = True
        except json.JSONDecodeError:
            ans, valid = {}, False
        exp_alerts = set() if k["alerts"] == "none" else set(k["alerts"].split(";"))
        got_alerts = set(ans.get("alerts") or []) if isinstance(ans.get("alerts"), list) else set()
        r = {
            "id": rid, "seconds": round(secs, 2), "valid_json": valid,
            "water_ok": str(ans.get("water")).lower() == k["water"],
            "alerts_ok": valid and got_alerts == exp_alerts,
            "overwater": k["water"] == "no" and str(ans.get("water")).lower() == "yes",
            "missed_water": k["water"] == "yes" and str(ans.get("water")).lower() != "yes",
        }
        for lv in LEVELS:
            r[lv + "_ok"] = ans.get(lv) == k[lv]
        r["all_ok"] = r["water_ok"] and r["alerts_ok"] and all(r[lv + "_ok"] for lv in LEVELS)
        r["answer"] = raw.replace("\n", " ")
        results.append(r)
        for c in r:
            if isinstance(r[c], bool) and r[c]:
                score[c] += 1
        print(f"[{n}/{len(ids)}] {rid} water={'OK ' if r['water_ok'] else 'BAD'} "
              f"all={'OK ' if r['all_ok'] else 'BAD'} {secs:.1f}s")

    total = len(results)
    out = f"results_{args.model.replace(':', '_').replace('/', '_')}_{args.dataset}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader(); w.writerows(results)

    pct = lambda c: f"{100 * score[c] / total:5.1f} %"
    print(f"\n=== {args.model} on dataset {args.dataset} ({total} rows) ===")
    print(f"Valid JSON        {pct('valid_json')}")
    print(f"Water decision    {pct('water_ok')}")
    for lv in LEVELS:
        print(f"{lv:<17} {pct(lv + '_ok')}")
    print(f"Alerts            {pct('alerts_ok')}")
    print(f"Everything right  {pct('all_ok')}")
    print(f"Overwatering      {score['overwater']} rows   <- most dangerous")
    print(f"Missed watering   {score['missed_water']} rows")
    print(f"Average time      {sum(r['seconds'] for r in results) / total:.2f} s per answer")
    print(f"Details saved to  {out}")


if __name__ == "__main__":
    main()
