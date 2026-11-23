"""Summarise results/*.jsonl into summary.csv and print a readable table.

Water accuracy is shown with a 95 % Wilson interval. "Balanced" is the mean of the
recall on "yes" and on "no" cases, so a model that always says "no" scores 50 %.
"""
import csv, glob, json, math, os
from labels import label


def wilson(k, n, z=1.96):
    if n == 0:
        return 0, 0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * (c - h), 100 * (c + h)


def summarise(name, rows):
    n = len(rows)
    yes = [r for r in rows if r["key"]["water"] == "yes"]
    no = [r for r in rows if r["key"]["water"] == "no"]
    w = sum(r["water_ok"] for r in rows)
    lo, hi = wilson(w, n)
    rec_yes = sum(r["water_ok"] for r in yes) / max(len(yes), 1)
    rec_no = sum(r["water_ok"] for r in no) / max(len(no), 1)
    lv = [r[k] for r in rows for k in ("moisture_level_ok", "temp_level_ok", "light_level_ok", "humidity_level_ok")
          if r[k] is not None]
    hard = [r for r in rows if r["kind"] == "boundary"]
    danger = [r for r in rows if r["key"]["alerts"] and r["key"]["alerts"] != ["LOW_LIGHT"]]
    pct = lambda x: round(100 * x, 1)
    return {
        "run": name, "n": n,
        "valid_json": pct(sum(r["valid_json"] for r in rows) / n),
        "water_acc": pct(w / n), "water_ci95": f"{lo:.0f}-{hi:.0f}",
        "water_balanced": pct((rec_yes + rec_no) / 2),
        "said_yes_pct": pct(sum(r["water_ok"] for r in yes) / n + sum(not r["water_ok"] for r in no) / n),
        "levels_acc": pct(sum(lv) / len(lv)) if lv else "given",
        "alerts_acc": pct(sum(r["alerts_ok"] for r in rows) / n),
        "danger_alerts_acc": pct(sum(r["alerts_ok"] for r in danger) / max(len(danger), 1)),
        "boundary_water_acc": pct(sum(r["water_ok"] for r in hard) / max(len(hard), 1)),
        "all_correct": pct(sum(r["all_ok"] for r in rows) / n),
        "overwater": sum(r["overwater"] for r in rows),
        "missed_water": sum(r["missed_water"] for r in rows),
        "sec_per_answer": round(sum(r["seconds"] for r in rows) / n, 2),
    }


def baselines(cases):
    """Reference points: two dumb strategies and the 5-line rule code."""
    out = []
    for name, f in [("BASELINE always 'no'", lambda c: "no"), ("BASELINE always 'yes'", lambda c: "yes"),
                    ("BASELINE rule code (if m <= 70)", lambda c: "yes" if c["input"]["soil_moisture_index"] <= 70 else "no")]:
        rows = []
        for c in cases:
            wa = f(c)
            code = name.startswith("BASELINE rule")
            k = c["key"]
            rows.append({"key": k, "kind": c["kind"], "seconds": 0, "valid_json": True,
                         "water_ok": wa == k["water"], "overwater": k["water"] == "no" and wa == "yes",
                         "missed_water": k["water"] == "yes" and wa != "yes", "alerts_ok": code,
                         "all_ok": code and wa == k["water"],
                         **{x + "_ok": (code or None) for x in ("moisture_level", "temp_level", "light_level", "humidity_level")}})
        out.append(summarise(name, rows))
    return out


def main():
    cases = [json.loads(l) for l in open("testset.jsonl")]
    table = baselines(cases)
    for f in sorted(glob.glob("results/*.jsonl")):
        rows = [json.loads(l) for l in open(f)]
        table.append(summarise(os.path.basename(f)[:-6], rows))
    with open("summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    cols = ["run", "water_acc", "water_ci95", "water_balanced", "said_yes_pct", "levels_acc", "alerts_acc",
            "danger_alerts_acc", "boundary_water_acc", "all_correct", "overwater", "missed_water", "sec_per_answer"]
    widths = {c: max(len(c), max(len(str(r[c])) for r in table)) for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    for r in table:
        print("  ".join(str(r[c]).ljust(widths[c]) for c in cols))


if __name__ == "__main__":
    main()
