"""Training data for fine-tuning a small model (first: qwen3.5:0.8b) to make the Nabta decision itself.

Every answer comes from rules v2 (rules_v2.decide, one row, no previous row): the rules are only the
teacher's answer key. On the Pi the fine-tuned model decides alone.

The 30-day test dataset (../dataset, seed 2026) is NOT used here; any training row with exactly the
same 5 numbers as a test row is removed, so the test stays unseen.

Parts:
  realistic  rows from the 30-day simulator run with other seeds (2027, 2028, 2029)
  uniform    random values over the whole range of every sensor
  boundary   values at and right around every limit (70, 25, 98, 90, 2 / 36, 4, 15, 25 / 60, 70 / 90000, 285000)
  fault      broken sensor: soil 2 or below, impossible temperature / humidity, negative light

Output (../train_data/):
  train.jsonl, val.jsonl   chat format {"messages": [system, user, assistant]} (Unsloth / Hugging Face TRL)
  train.csv,   val.csv     the same rows as a table, to read
  stats.txt                counts per part, water, alerts, faults

    python make_train_data.py
"""
import csv, json, os, random, tempfile
import rules_v2
import simulate_30days_v2 as sim

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "train_data")
TEST_SENSOR = os.path.join(HERE, "..", "dataset", "sim_sensor_30days.csv")
COLS = ["soil_moisture_index", "air_temp_c", "humidity_rh", "light_lux_now", "light_lux_hours_24h"]
DIGITS = [1, 2, 1, 1, 2]                      # same rounding as the real 30-min log
KEYS = ["moisture_level", "temp_level", "light_level", "humidity_level", "faults", "alerts", "water"]
N = {"realistic": 2400, "uniform": 2400, "boundary": 1500, "fault": 300}
VAL_SHARE = 0.1

# Short fixed prompt: the same text must be used when the fine-tuned model runs on the Pi.
SYSTEM = ("You are Nabta, the controller of a smart pot growing spearmint. You receive one 30-minute "
          "sensor reading as JSON. Decide the levels, faults, alerts and whether to water. "
          "Answer with JSON only.")

rnd = random.Random(42)


def row(m, t, h, ln, lh):
    return {c: round(float(v), d) for c, v, d in zip(COLS, (m, t, h, ln, lh), DIGITS)}


def lux_pair():
    """Light now and light over 24 h (independent: the decision only uses the 24 h sum)."""
    ln = 0.0 if rnd.random() < 0.4 else 10 ** rnd.uniform(0, 4.9)       # night, or 1 .. 80,000 lux
    r = rnd.random()                                                    # about 45 % low light, as in the 30-day log
    lh = rnd.uniform(0, 600000) if r < 0.6 else (10 ** rnd.uniform(2, 4.95) if r < 0.95 else rnd.uniform(0, 1000))
    return ln, lh


def realistic():
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for seed in (2027, 2028, 2029):
            sim.SEED, sim.OUT = seed, tmp
            sim.main()
            with open(os.path.join(tmp, "sim_sensor_30days.csv"), encoding="utf-8") as f:
                rows += [{c: float(r[c]) for c in COLS} for r in csv.DictReader(f)]
    return rows


def uniform():
    out = []
    for _ in range(N["uniform"]):
        ln, lh = lux_pair()
        out.append(row(rnd.uniform(2.1, 100), rnd.uniform(-5, 45), rnd.uniform(15, 100), ln, lh))
    return out


def near(limit, spread):
    """Exactly on the limit, or just around it."""
    r = rnd.random()
    if r < 0.25: return limit
    if r < 0.5: return limit + rnd.choice([-1, 1]) * rnd.choice([0.1, 0.2, 0.3, 0.5]) * spread
    return limit + rnd.uniform(-2, 2) * spread


def boundary():
    out = []
    for _ in range(N["boundary"]):
        ln, lh = lux_pair()
        m, t, h = rnd.uniform(3, 100), rnd.uniform(0, 40), rnd.uniform(20, 95)
        which = rnd.choice(["m", "m", "m", "t", "t", "h", "l"])
        if which == "m": m = min(100.0, max(2.1, near(rnd.choice([70, 70, 25, 25, 98, 98, 90, 2.1]), 1)))
        if which == "t": t = near(rnd.choice([36, 4, 15, 25]), 1)
        if which == "h": h = near(rnd.choice([60, 70]), 1)
        if which == "l": lh = max(0.0, near(rnd.choice([90000, 285000]), 2000))
        out.append(row(m, t, h, ln, lh))
    return out


def fault():
    out = []
    for i in range(N["fault"]):
        ln, lh = lux_pair()
        m, t, h = rnd.uniform(3, 100), rnd.uniform(0, 40), rnd.uniform(20, 95)
        kind = i % 6
        if kind <= 2: m = rnd.choice([0.0, 0.0, 0.1, 0.5, 1.0, 1.5, 2.0, rnd.uniform(0, 2)])   # probe out / unplugged
        if kind == 3: t = rnd.choice([-40.0, -142.5, 85.0, rnd.uniform(-30, -10.5), rnd.uniform(60.5, 90)])
        if kind == 4: h = rnd.choice([0.0, 0.0, 0.5, rnd.uniform(0, 0.9)])
        if kind == 5: ln, lh = (rnd.choice([-1.0, -10.0]), lh) if rnd.random() < 0.5 else (ln, -rnd.uniform(1, 500))
        out.append(row(m, t, h, ln, lh))
    return out


def answer(r):
    k = rules_v2.decide(r)
    return {x: k[x] for x in KEYS}


def example(r):
    return {"messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": json.dumps(r)},
                         {"role": "assistant", "content": json.dumps(answer(r))}]}


def main():
    with open(TEST_SENSOR, encoding="utf-8") as f:
        test = {tuple(round(float(r[c]), d) for c, d in zip(COLS, DIGITS)) for r in csv.DictReader(f)}

    real = realistic()
    # keep every realistic row that needs water or has a fault/alert, then fill up with the rest
    rare = [r for r in real if (a := answer(r))["water"] == "yes" or a["faults"] or a["alerts"] != ["LOW_LIGHT"] and a["alerts"]]
    common = [r for r in real if r not in rare]
    rnd.shuffle(rare); rnd.shuffle(common)
    real = (rare + common)[:N["realistic"]]

    parts = {"realistic": real, "uniform": uniform(), "boundary": boundary(), "fault": fault()}
    seen, data = set(test), []
    dropped = 0
    for part, rows in parts.items():
        for r in rows:
            key = tuple(r[c] for c in COLS)
            if key in seen:
                dropped += 1; continue
            seen.add(key)
            data.append((part, r))
    rnd.shuffle(data)
    nval = int(len(data) * VAL_SHARE)
    splits = {"val": data[:nval], "train": data[nval:]}

    os.makedirs(OUT, exist_ok=True)
    for name, rows in splits.items():
        with open(os.path.join(OUT, f"{name}.jsonl"), "w", encoding="utf-8") as f:
            for _, r in rows:
                f.write(json.dumps(example(r)) + "\n")
        with open(os.path.join(OUT, f"{name}.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["part"] + COLS + KEYS)
            for part, r in rows:
                a = answer(r)
                w.writerow([part] + [r[c] for c in COLS] +
                           [";".join(a[k]) or "none" if isinstance(a[k], list) else a[k] for k in KEYS])

    lines = [f"rows: {len(data)} (train {len(splits['train'])}, val {nval}); "
             f"dropped {dropped} duplicates of the test set or of each other", ""]
    for name, rows in splits.items():
        ans = [answer(r) for _, r in rows]
        cnt = lambda f: sum(1 for a in ans if f(a))
        lines.append(f"[{name}]")
        lines.append("  parts:  " + ", ".join(f"{p} {sum(1 for q, _ in rows if q == p)}" for p in N))
        lines.append(f"  water:  yes {cnt(lambda a: a['water'] == 'yes')}, no {cnt(lambda a: a['water'] == 'no')}")
        lines.append("  alerts: " + ", ".join(f"{x} {cnt(lambda a, x=x: x in a['alerts'])}" for x in rules_v2.ALERT_ORDER)
                     + f", none {cnt(lambda a: not a['alerts'])}")
        lines.append(f"  faults: SENSOR_ERROR {cnt(lambda a: 'SENSOR_ERROR' in a['faults'])}")
        for lv in KEYS[:4]:
            c = {}
            for a in ans: c[a[lv]] = c.get(a[lv], 0) + 1
            lines.append(f"  {lv}: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))
        lines.append("")
    txt = "\n".join(lines)
    print(txt)
    open(os.path.join(OUT, "stats.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
