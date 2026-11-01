"""Build Nabta's model-selection test set.

Steps:
  1. Read a real sensor time series (CSV or XLSX) and convert it to Nabta's fields.
  2. Fill the fields the dataset does not have (tank level, water volume) by simulation.
  3. Turn each reading into a scenario: what the assistant would receive at that moment.
  4. Label every scenario with the reference rules engine (rules.py).
  5. Pick a balanced sample, add the hand-made edge cases, and write testset.jsonl.

Usage:
  python build_testset.py data/source.csv
  python build_testset.py data/source.csv --per-group 20 --seed 7
  python build_testset.py --edge-only           # edge cases only, no dataset needed
"""

import argparse
import csv
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import rules        # noqa: E402
import edge_cases   # noqa: E402

COLUMN_HINTS = {
    "time": ["timestamp", "datetime", "date_time", "time", "date"],
    "moisture": ["soil_moisture", "soilmoisture", "moisture", "soil"],
    "temp": ["temperature", "air_temp", "temp"],
    "humidity": ["humidity", "humid", "rh"],
    "light": ["light_intensity", "light", "lux", "ldr", "luminosity"],
    "pump": ["pump_status", "pump", "motor", "irrigation", "relay"],
}

TIME_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
                "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M:%S",
                "%m/%d/%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M"]


# ---------------------------------------------------------------------------
# 1. Reading the source file
# ---------------------------------------------------------------------------

def read_table(path):
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl
        ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        header = [str(h).strip() for h in rows[0]]
        return [dict(zip(header, r)) for r in rows[1:] if any(v is not None for v in r)]
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def find_columns(header, overrides):
    found = {}
    lower = {h: h.lower().replace(" ", "_") for h in header}
    for key, hints in COLUMN_HINTS.items():
        if overrides.get(key):
            found[key] = overrides[key]
            continue
        for hint in hints:
            match = [h for h, l in lower.items() if hint in l and h not in found.values()]
            if match:
                found[key] = match[0]
                break
    return found


def to_float(v):
    if v is None or str(v).strip() == "":
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def to_pump(v):
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("1", "1.0", "on", "true", "yes", "high")


def parse_time(v):
    if isinstance(v, datetime):
        return v
    s = str(v).strip()
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def load_series(path, overrides, interval_min, light_scale):
    table = read_table(path)
    if not table:
        sys.exit("The source file is empty.")
    cols = find_columns(list(table[0].keys()), overrides)
    print("Columns used:", json.dumps(cols))
    for needed in ("moisture", "temp", "humidity", "light"):
        if needed not in cols:
            sys.exit(f"Could not find a '{needed}' column. Use --col-{needed} to name it.")

    start = datetime(2026, 11, 9, 0, 0)
    series = []
    for i, row in enumerate(table):
        t = parse_time(row[cols["time"]]) if "time" in cols else None
        if t is None:
            t = start + timedelta(minutes=interval_min * i)
        light = to_float(row[cols["light"]])
        series.append({
            "t": t,
            "raw_moisture": to_float(row[cols["moisture"]]),
            "air_temp_c": to_float(row[cols["temp"]]),
            "humidity_rh": to_float(row[cols["humidity"]]),
            "light_lux": None if light is None else light * light_scale,
            "pump": to_pump(row[cols["pump"]]) if "pump" in cols else False,
        })
    series.sort(key=lambda r: r["t"])
    return series


# ---------------------------------------------------------------------------
# 2. Converting and simulating
# ---------------------------------------------------------------------------

def percentile(values, p):
    v = sorted(values)
    k = (len(v) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def add_moisture_index(series, as_index=False):
    """0 = driest reading (1st percentile), 100 = typical reading right after watering.

    With as_index=True the moisture column is already a 0-100 % scale on which the
    plant's thresholds make sense, so it is used directly.
    """
    if as_index:
        for r in series:
            raw = r["raw_moisture"]
            r["moisture_index"] = None if raw is None else round(max(0.0, min(100.0, raw)), 1)
        print("Moisture index: moisture column used directly (0-100 %)")
        return
    raws = [r["raw_moisture"] for r in series if r["raw_moisture"] is not None]
    after_pump = [series[i + 1]["raw_moisture"] for i in range(len(series) - 1)
                  if series[i]["pump"] and series[i + 1]["raw_moisture"] is not None]

    # Capacitive raw values usually fall as soil gets wetter; percentages rise.
    wetter_is_higher = True
    if len(after_pump) >= 3:
        wetter_is_higher = statistics.median(after_pump) > statistics.median(raws)
    elif max(raws) > 100:
        wetter_is_higher = False

    sign = 1 if wetter_is_higher else -1
    wet = [sign * x for x in raws]
    dry_ref = percentile(wet, 1)
    wet_ref = (statistics.median([sign * x for x in after_pump]) if len(after_pump) >= 3
               else percentile(wet, 99))
    span = (wet_ref - dry_ref) or 1.0
    for r in series:
        raw = r["raw_moisture"]
        r["moisture_index"] = (None if raw is None
                               else round(max(0.0, min(100.0, (sign * raw - dry_ref) / span * 100)), 1))
    print(f"Moisture index: wetter_is_higher={wetter_is_higher}, dry_ref={sign * dry_ref:g}, "
          f"wet_ref={sign * wet_ref:g}, pump readings={sum(r['pump'] for r in series)}")


def add_watering_and_tank(series, config):
    dose = config["dataset_dose_ml_per_pump_reading"]
    tank = config["tank_capacity_ml"]
    empty_since = None
    last_t, last_ml = None, None
    day, ml_today = None, 0
    for r in series:
        if r["t"].date() != day:
            day, ml_today = r["t"].date(), 0
        if empty_since and r["t"] - empty_since >= timedelta(hours=config["tank_refill_delay_hours"]):
            tank, empty_since = config["tank_capacity_ml"], None

        # state *before* this reading's decision
        r["tank_ok"] = tank >= config["tank_empty_below_ml"]
        r["minutes_since_last"] = (None if last_t is None
                                   else int((r["t"] - last_t).total_seconds() // 60))
        r["last_ml"] = last_ml
        r["ml_today"] = ml_today

        if r["pump"] and r["tank_ok"]:
            last_t, last_ml = r["t"], dose
            ml_today += dose
            tank -= dose
            if tank < config["tank_empty_below_ml"] and empty_since is None:
                empty_since = r["t"]


def hours_in_a_row(series, i, test, step_h):
    n = 0
    j = i
    while j >= 0 and series[j]["moisture_index"] is not None and test(series[j]):
        n += 1
        j -= 1
    return round(n * step_h, 1)


def build_context(series, i, step_h):
    r = series[i]
    per_2h = int(round(2 / step_h)) + 1
    per_24h = int(round(24 / step_h))
    window = series[max(0, i - per_24h + 1): i + 1]
    m24 = [x["moisture_index"] for x in window if x["moisture_index"] is not None]
    t24 = [x["air_temp_c"] for x in window if x["air_temp_c"] is not None]
    return {
        "time": r["t"].strftime("%H:%M"),
        "pot_id": "A",
        "latest": {
            "moisture_index": r["moisture_index"],
            "air_temp_c": r["air_temp_c"],
            "humidity_rh": r["humidity_rh"],
            "light_lux": None if r["light_lux"] is None else round(r["light_lux"]),
            "tank_ok": r["tank_ok"],
        },
        "moisture_last_2h": [x["moisture_index"] for x in series[max(0, i - per_2h + 1): i + 1]],
        "history_24h": {
            "moisture_min": min(m24),
            "moisture_max": max(m24),
            "hours_in_a_row_moisture_below_40": hours_in_a_row(series, i, lambda x: x["moisture_index"] < 40, step_h),
            "hours_in_a_row_moisture_above_95": hours_in_a_row(series, i, lambda x: x["moisture_index"] > 95, step_h),
            "hours_in_a_row_humidity_above_80": hours_in_a_row(
                series, i, lambda x: (x["humidity_rh"] or 0) > 80, step_h),
            "air_temp_min": min(t24),
            "air_temp_max": max(t24),
            "light_lux_hours_last_24h": int(sum((x["light_lux"] or 0) * step_h for x in window)),
        },
        "watering": {
            "minutes_since_last": r["minutes_since_last"],
            "last_ml": r["last_ml"],
            "ml_today": r["ml_today"],
        },
    }


# ---------------------------------------------------------------------------
# 3-5. Labelling, sampling, writing
# ---------------------------------------------------------------------------

def dataset_scenarios(series, profile, config, per_group, seed):
    steps = [(b["t"] - a["t"]).total_seconds() / 3600 for a, b in zip(series, series[1:])]
    step_h = statistics.median(steps)
    first_full = int(round(24 / step_h))  # need 24 h of history
    pool = defaultdict(list)
    for i in range(first_full, len(series)):
        r = series[i]
        if None in (r["moisture_index"], r["air_temp_c"], r["humidity_rh"], r["light_lux"]):
            continue
        ctx = build_context(series, i, step_h)
        exp = rules.decide(ctx, profile, config)
        key = (exp["reason_code"], tuple(exp["alerts"]))
        pool[key].append({"id": f"data-{i:04d}", "source": "dataset",
                          "description": f"Real trace, reading {i}, {r['t']:%Y-%m-%d %H:%M}",
                          "context": ctx, "expected": exp})

    rng = random.Random(seed)
    chosen = []
    for key in sorted(pool):
        items = pool[key]
        rng.shuffle(items)
        chosen.extend(items[:per_group])
    chosen.sort(key=lambda s: s["id"])
    print(f"Sampling step: {step_h * 60:.0f} min. Labelled readings available:",
          {"+".join((k[0],) + k[1]): len(v) for k, v in sorted(pool.items())})
    return chosen


def edge_scenarios(profile, config):
    out, problems = [], []
    for c in edge_cases.build():
        exp = rules.decide(c["context"], profile, config)
        action, reason, alerts = c.pop("intended")
        if (exp["action"], exp["reason_code"], exp["alerts"]) != (action, reason, sorted(alerts)):
            problems.append(f"{c['id']}: intended {action}/{reason}/{sorted(alerts)}, "
                            f"rules gave {exp['action']}/{exp['reason_code']}/{exp['alerts']}")
        c["expected"] = exp
        out.append(c)
    if problems:
        sys.exit("Edge cases disagree with the rules engine:\n  " + "\n  ".join(problems))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", help="CSV or XLSX sensor time series")
    ap.add_argument("--edge-only", action="store_true")
    ap.add_argument("--per-group", type=int, default=12,
                    help="max scenarios per (reason, alert combination) group from the dataset")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--interval-min", type=float, default=30, help="used only if the file has no timestamps")
    ap.add_argument("--light-scale", type=float, default=1.0, help="multiply the light column to get lux")
    ap.add_argument("--moisture-as-index", action="store_true",
                    help="use the moisture column directly as the 0-100 index (it is already a %%)")
    ap.add_argument("--out", default=str(HERE / "testset.jsonl"))
    for key in COLUMN_HINTS:
        ap.add_argument(f"--col-{key}", help=f"name of the {key} column if auto-detection fails")
    args = ap.parse_args()

    profile, config = rules.load_settings()
    scenarios = []
    if not args.edge_only:
        if not args.source:
            sys.exit("Give a source file, or use --edge-only.")
        overrides = {k: getattr(args, f"col_{k}") for k in COLUMN_HINTS}
        series = load_series(args.source, overrides, args.interval_min, args.light_scale)
        add_moisture_index(series, args.moisture_as_index)
        add_watering_and_tank(series, config)
        scenarios += dataset_scenarios(series, profile, config, args.per_group, args.seed)
    scenarios += edge_scenarios(profile, config)

    with open(args.out, "w", encoding="utf-8") as f:
        for s in scenarios:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    reasons = Counter(s["expected"]["reason_code"] for s in scenarios)
    alerts = Counter(a for s in scenarios for a in s["expected"]["alerts"])
    print(f"\nWrote {len(scenarios)} scenarios to {args.out}")
    print("  by source :", dict(Counter(s["source"] for s in scenarios)))
    print("  by reason :", dict(reasons))
    print("  alerts    :", dict(alerts))


if __name__ == "__main__":
    main()
