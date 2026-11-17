#!/usr/bin/env python3
"""
Compute the paper's three tables. Standard library only.

RQ1 precision, from per-controller traces (closed-loop replay, or the real pots):
  python3 metrics.py rq1 --dir ../results/replay                      # *_readings.csv + *_waterings.csv
  python3 metrics.py rq1 --readings ../logs/readings.csv --waterings ../logs/waterings.csv   # real Pot A / B

RQ2 reliability and RQ3 cost, from the log written by llm_decide.py:
  python3 metrics.py rq2 --log ../logs/decisions.jsonl [--hard-only]
  python3 metrics.py rq3 --log ../logs/decisions.jsonl [--cycles-per-day 48 --days 14]
Add --csv <file> to any command to save the table.
"""
import argparse, csv, json, math, statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

OVER_TOL = 5  # index points: watering when the soil is >= 65 counts as unneeded (sensor noise margin)
PROF = json.loads((Path(__file__).resolve().parent / "config.json").read_text())["plant_profile"]


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def kappa(pairs):
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(a == b for a, b in pairs) / n
    labels = {x for p in pairs for x in p}
    pe = sum((sum(a == l for a, _ in pairs) / n) * (sum(b == l for _, b in pairs) / n) for l in labels)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))] if xs else float("nan")


def r(x, n=3):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(x, n)


# ------------------------------------------------------------------ RQ1
def precision_row(name, s, ws, drained):
    lo, hi = PROF["band"]
    s.sort()
    step = (s[1][0] - s[0][0]).total_seconds() / 60 if len(s) > 1 else 5
    days = max(1e-9, (s[-1][0] - s[0][0]).total_seconds() / 86400)
    vals = [v for _, v in s]
    total = sum(ml for _, ml in ws)
    under_events, below = 0, False          # an event = each entry into the stress zone
    for v in vals:
        if v < PROF["stress_below"] and not below:
            under_events += 1
        below = v < PROF["stress_below"]
    over, sp = 0, []
    for t, _ in ws:
        after = [v for tt, v in s if t + timedelta(minutes=25) <= tt <= t + timedelta(minutes=35)]
        before = [v for tt, v in s if t - timedelta(minutes=10) <= tt <= t]
        if after:
            sp.append(after[0] - PROF["refill_to_index"])
        if (after and after[0] > hi) or (before and before[-1] >= PROF["water_below_index"] + OVER_TOL):
            over += 1
    return {"controller": name, "days": r(days, 1), "time_in_band_pct": r(100 * sum(lo <= v <= hi for v in vals) / len(vals), 1),
            "mean_dev_from_band": r(statistics.mean(max(lo - v, 0, v - hi) for v in vals), 2),
            "minutes_below_stress": round(sum(v < PROF["stress_below"] for v in vals) * step),
            "underwater_events": under_events, "overwater_events": over, "waterings": len(ws),
            "total_ml": round(total), "ml_per_day": r(total / days, 1),
            "drained_ml": r(drained, 0) if drained is not None else None,
            "setpoint_err_mean": r(statistics.mean(sp), 1) if sp else None}


def rq1(a):
    rows = []
    if a.dir:
        for rf in sorted(Path(a.dir).glob("*_readings.csv")):
            name = rf.name.replace("_readings.csv", "")
            s, dr = [], 0.0
            with open(rf) as f:
                for x in csv.DictReader(f):
                    if x["soil_index"]:
                        s.append((datetime.fromisoformat(x["timestamp"]), float(x["soil_index"])))
                    dr += float(x.get("drained_ml") or 0)
            with open(rf.with_name(name + "_waterings.csv")) as f:
                ws = [(datetime.fromisoformat(x["timestamp"]), float(x["ml"])) for x in csv.DictReader(f)]
            rows.append(precision_row(name, s, ws, dr))
    else:
        rd, wt = defaultdict(list), defaultdict(list)
        with open(a.readings) as f:
            for x in csv.DictReader(f):
                col = "soil_index_true" if a.use_true and x.get("soil_index_true") else "soil_index"
                if x.get(col):
                    rd[x["pot"]].append((datetime.fromisoformat(x["timestamp"]), float(x[col])))
        with open(a.waterings) as f:
            for x in csv.DictReader(f):
                wt[x["pot"]].append((datetime.fromisoformat(x["timestamp"]), float(x["ml"])))
        rows = [precision_row("pot_" + p, rd[p], wt[p], None) for p in sorted(rd)]
    out(rows, a.csv)


# ------------------------------------------------------------------ RQ2 / RQ3
def load_log(a):
    recs = [json.loads(l) for l in Path(a.log).read_text().splitlines() if l.strip()]
    if getattr(a, "hard_only", False):
        recs = [x for x in recs if x.get("hard_case")]
    by = defaultdict(list)
    for x in recs:
        by[x["controller"]].append(x)
    return by


def rq2(a):
    rows = []
    for cid, rs in sorted(load_log(a).items()):
        first = [x for x in rs if x["repeat"] == 0]
        n = len(first)
        prop = [x["proposed_action"] if x["valid_json"] else "invalid" for x in first]   # judged BEFORE the gate
        ref = [x["ref_action"] for x in first]
        k = sum(p == t for p, t in zip(prop, ref))
        lo, hi = wilson(k, n)
        tp = sum(p == "water" == t for p, t in zip(prop, ref))
        fp = sum(p == "water" != t for p, t in zip(prop, ref))
        fn = sum(p != "water" == t for p, t in zip(prop, ref))
        prec = tp / (tp + fp) if tp + fp else float("nan")
        rec = tp / (tp + fn) if tp + fn else float("nan")
        dose = [abs(x["proposed_ml"] - x["ref_ml"]) for x in first if x["proposed_action"] == "water"
                and x["ref_action"] == "water" and isinstance(x["proposed_ml"], (int, float))]
        unsafe = sum(1 for x in first if (x.get("gate") or x.get("would_block")) not in (None, "invalid_or_no_answer"))
        groups = defaultdict(list)
        for x in rs:
            groups[x["case"]].append(x["proposed_action"] if x["valid_json"] else "invalid")
        multi = [g for g in groups.values() if len(g) > 1]
        rows.append({"controller": cid, "name": first[0]["name"] if first else "", "n": n,
                     "accuracy": r(k / n) if n else None, "acc_95ci": f"{lo:.3f}-{hi:.3f}",
                     "kappa": r(kappa(list(zip(prop, ref)))), "water_recall": r(rec), "water_precision": r(prec),
                     "dose_mae_ml": r(statistics.mean(dose), 1) if dose else None,
                     "unsafe_rate": r(unsafe / n) if n else None,
                     "valid_json_rate": r(sum(x["valid_json"] for x in first) / n) if n else None,
                     "stability_3x": r(sum(len(set(g)) == 1 for g in multi) / len(multi)) if multi else None})
    out(rows, a.csv)


def rq3(a):
    rows = []
    for cid, rs in sorted(load_log(a).items()):
        lat = [x["latency_s"] for x in rs if x["latency_s"] is not None]
        cost = [x.get("cost_usd") or 0 for x in rs]
        n = len(rs)
        per = statistics.mean(cost) if cost else 0
        rows.append({"controller": cid, "name": rs[0]["name"], "where": rs[0]["where"], "n": n,
                     "latency_median_s": r(statistics.median(lat), 4) if lat else None,
                     "latency_p90_s": r(pct(lat, 0.9), 4) if lat else None,
                     "within_cycle_pct": r(100 * sum(l <= 60 for l in lat) / n, 1) if n else None,
                     "cost_per_decision_usd": r(per, 6),
                     "cost_study_usd": r(per * a.cycles_per_day * a.days, 3),
                     "answered_pct": r(100 * sum(x["error"] is None for x in rs) / n, 1) if n else None,
                     "works_offline": rs[0]["where"] != "cloud"})
    out(rows, a.csv)


def out(rows, path):
    if not rows:
        print("no data"); return
    keys = list(rows[0])
    w = [max(len(k), *(len(str(x[k])) for x in rows)) for k in keys]
    print("  ".join(k.ljust(v) for k, v in zip(keys, w)))
    for x in rows:
        print("  ".join(str(x[k]).ljust(v) for k, v in zip(keys, w)))
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="") as f:
            cw = csv.DictWriter(f, fieldnames=keys); cw.writeheader(); cw.writerows(rows)
        print("saved", path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p1 = sp.add_parser("rq1")
    p1.add_argument("--dir"); p1.add_argument("--readings"); p1.add_argument("--waterings")
    p1.add_argument("--use-true", action="store_true", help="simulator output only: noise-free index")
    for p in (sp.add_parser("rq2"), sp.add_parser("rq3")):
        p.add_argument("--log", required=True); p.add_argument("--hard-only", action="store_true")
        p.add_argument("--cycles-per-day", type=int, default=48); p.add_argument("--days", type=int, default=14)
        p.add_argument("--csv")
    p1.add_argument("--csv")
    a = ap.parse_args()
    {"rq1": rq1, "rq2": rq2, "rq3": rq3}[a.cmd](a)
