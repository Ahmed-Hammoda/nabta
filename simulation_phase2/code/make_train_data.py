"""Training data for fine-tuning a small model (first: qwen3.5:0.8b) to make the Nabta decision itself.

VERSION 3: the model decides the pump (water yes/no), the grow light (on/off) and the alerts, with the
water tank (float switch). Every answer comes from rules v3 (rules_v3.decide, one row, no previous
row): the rules are only the teacher's answer key. On the Pi the three pump safety rules (3 h wait,
3 a day, no old readings) stay in code after the model's decision.

Input (JSON, one 30-min reading):
  soil_moisture_index, air_temp_c, humidity_rh, light_lux_now, light_lux_hours_24h,
  hour (0-23), light_on (0/1, the grow light right now), tank_low (0/1, float switch)
Output (JSON): moisture_level, temp_level, light_level, humidity_level, faults, alerts, water, light

The v3 30-day test dataset (../dataset_v3, seed 2026) is NOT used here; any training row equal to a
test row is removed, so the test stays unseen.

Parts:
  realistic  rows from the v3 30-day simulator run with other seeds (2027, 2028, 2029)
  uniform    random values over the whole range of every input
  boundary   values at and right around every limit (soil 70, 25, 98, 90, 2 / temp 36, 4, 15, 25 /
             humidity 60, 70 / light 90000, 225000 / dark 2000 lux / hours 6 and 22 / tank low)
  fault      broken sensor: soil 2 or below, impossible temperature / humidity, negative light

Output (../train_data/):
  train.jsonl, val.jsonl   chat format {"messages": [system, user, assistant]} (Unsloth / Hugging Face TRL)
  train.csv,   val.csv     the same rows as a table, to read
  stats.txt                counts per part, water, light, alerts, faults

    python make_train_data.py
"""
import csv, json, os, random, tempfile
import rules_v3
import simulate_30days_v3 as sim

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "train_data")
TEST_SENSOR = os.path.join(HERE, "..", "dataset_v3", "sim_sensor_30days.csv")
COLS = rules_v3.INPUTS
DIGITS = [1, 2, 1, 1, 2, 0, 0, 0]             # same rounding as the real 30-min log; the last 3 are integers
KEYS = ["moisture_level", "temp_level", "light_level", "humidity_level", "faults", "alerts", "water", "light"]
N = {"realistic": 2400, "uniform": 2400, "boundary": 1800, "fault": 300}
VAL_SHARE = 0.1

# Short fixed prompt: the same text must be used when the fine-tuned model runs on the Pi.
SYSTEM = ("You are Nabta, the controller of a smart pot growing spearmint. You receive one 30-minute "
          "sensor reading as JSON. Decide the levels, faults and alerts, whether to water (pump) and "
          "whether the grow light is on. Answer with JSON only.")

rnd = random.Random(42)


def row(m, t, h, ln, lh, hour=None, light_on=None, tank_low=None):
    hour = rnd.randrange(24) if hour is None else hour
    light_on = int(rnd.random() < 0.4) if light_on is None else light_on
    tank_low = int(rnd.random() < 0.1) if tank_low is None else tank_low
    r = {c: round(float(v), d) for c, v, d in zip(COLS[:5], (m, t, h, ln, lh), DIGITS)}
    r.update({"hour": int(hour), "light_on": int(light_on), "tank_low": int(tank_low)})
    return r


def lux_pair():
    """Light now and light over 24 h."""
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
                for x in csv.DictReader(f):
                    r = {c: float(x[c]) for c in COLS[:5]}
                    r.update({c: int(x[c]) for c in COLS[5:]})
                    rows.append(r)
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
    T = rules_v3.LIGHT_TARGET
    out = []
    for _ in range(N["boundary"]):
        ln, lh = lux_pair()
        m, t, h = rnd.uniform(3, 100), rnd.uniform(0, 40), rnd.uniform(20, 95)
        hour = light_on = tank_low = None
        which = rnd.choice(["m", "m", "m", "t", "t", "h", "l", "dark", "hour", "hour", "tank"])
        if which == "m": m = min(100.0, max(2.1, near(rnd.choice([70, 70, 25, 25, 98, 98, 90, 2.1]), 1)))
        if which == "t": t = near(rnd.choice([36, 4, 15, 25]), 1)
        if which == "h": h = near(rnd.choice([60, 70]), 1)
        if which == "l":                                   # 24 h total around the low / target limits
            lh = max(0.0, near(rnd.choice([90000, T, T]), 2000))
            hour = rnd.randrange(6, 22)
        if which == "dark":                                # light off, daytime: is it dark enough?
            ln, light_on, hour = max(0.0, near(2000, 50)), 0, rnd.randrange(6, 22)
            lh = rnd.uniform(0, T - 1000) if rnd.random() < 0.8 else rnd.uniform(T, 500000)
        if which == "hour":                                # around 06:00 and 22:00
            hour = rnd.choice([5, 6, 6, 21, 21, 22, 23, 0])
            lh = rnd.uniform(0, T - 1000) if rnd.random() < 0.8 else lh
        if which == "tank":                                # tank low, often when the soil needs water
            tank_low = 1
            m = rnd.uniform(3, 70) if rnd.random() < 0.7 else m
        out.append(row(m, t, h, ln, lh, hour, light_on, tank_low))
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
    k = rules_v3.decide(r)
    return {x: k[x] for x in KEYS}


def example(r):
    return {"messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": json.dumps(r)},
                         {"role": "assistant", "content": json.dumps(answer(r))}]}


def main():
    with open(TEST_SENSOR, encoding="utf-8") as f:
        test = {tuple(round(float(r[c]), d) for c, d in zip(COLS, DIGITS)) for r in csv.DictReader(f)}

    real = realistic()
    # keep every realistic row that needs water, has a fault, an alert other than LOW_LIGHT, or a light switch,
    # then fill up with the rest
    def is_rare(r):
        a = answer(r)
        return (a["water"] == "yes" or a["faults"] or (a["alerts"] and a["alerts"] != ["LOW_LIGHT"])
                or (a["light"] == "on") != bool(r["light_on"]))
    rare = [r for r in real if is_rare(r)]
    common = [r for r in real if not is_rare(r)]
    rnd.shuffle(rare); rnd.shuffle(common)
    real = (rare + common)[:N["realistic"]]

    parts = {"realistic": real, "uniform": uniform(), "boundary": boundary(), "fault": fault()}
    seen, data = set(test), []
    dropped = 0
    for part, rows in parts.items():
        for r in rows:
            key = tuple(round(float(r[c]), d) for c, d in zip(COLS, DIGITS))
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
        lines.append(f"  light:  on {cnt(lambda a: a['light'] == 'on')}, off {cnt(lambda a: a['light'] == 'off')}"
                     f"  (switched vs. light_on: {sum(1 for (_, r), a in zip(rows, ans) if (a['light'] == 'on') != bool(r['light_on']))})")
        lines.append("  alerts: " + ", ".join(f"{x} {cnt(lambda a, x=x: x in a['alerts'])}" for x in rules_v3.ALERT_ORDER)
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
