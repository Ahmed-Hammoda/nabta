"""Build testset.jsonl: real rows from the Mendeley trace + synthetic rows that cover
every level and every threshold boundary. Labels come from labels.py."""
import csv, json, random
from collections import defaultdict
from labels import label

rng = random.Random(7)
cases = []


def add(kind, m, t, h, lh, lux_now=None, src=None):
    lux_now = lux_now if lux_now is not None else rng.choice([0, 0, 1200, 8000, 15000])
    cases.append({
        "id": f"{kind[0]}{len(cases):03d}", "kind": kind, "source": src,
        "input": {"soil_moisture_index": round(m, 1), "air_temp_c": round(t, 1),
                  "humidity_rh": round(h, 1), "light_lux_now": lux_now,
                  "light_lux_hours_24h": int(lh)},
        "key": label(m, t, h, lh),
    })


# 1) Real rows: balanced sample over (water, temp_level, light_level)
groups = defaultdict(list)
for r in csv.DictReader(open("../dataset_A_numbers.csv")):
    vals = [float(r[c]) for c in ["soil_moisture_index", "air_temp_c", "humidity_rh", "light_lux_hours_24h"]]
    k = label(*vals)
    groups[(k["water"], k["temp_level"], k["light_level"])].append((r, vals))
for g in groups.values():
    rng.shuffle(g)
picked, i = [], 0
while len(picked) < 100:
    for g in sorted(groups):
        if i < len(groups[g]) and len(picked) < 100:
            picked.append(groups[g][i])
    i += 1
for r, (m, t, h, lh) in picked:
    add("real", m, t, h, lh, lux_now=int(float(r["light_lux_now"])), src=r["id"])

# Helpers for "normal" random values
nt = lambda: rng.uniform(16, 24)
nh = lambda: rng.uniform(40, 85)
nl = lambda: rng.uniform(100000, 400000)

# 2) Every moisture level x every temperature zone (x2) -> covers all level combos
M = {"danger_dry": (5, 25), "dry": (26, 70), "acceptable": (71, 89), "optimal": (90, 100), "too_wet": (101, 104)}
T = {"cold": (-3, 3.9), "cool": (4, 14.9), "optimal": (15, 25), "warm": (25.1, 36), "heat": (36.1, 42)}
L = [(20000, 89000), (90000, 284000), (285000, 450000)]
j = 0
for mr in M.values():
    for tr in T.values():
        for _ in range(2):
            add("coverage", rng.uniform(*mr), rng.uniform(*tr), nh(), rng.uniform(*L[j % 3]))
            j += 1

# 3) Exact threshold boundaries (the hardest cases for a language model)
for m in [25.0, 25.1, 69.9, 70.0, 70.1, 89.9, 90.0, 100.0, 100.1]:
    for _ in range(2):
        add("boundary", m, nt(), nh(), nl())
for t in [3.9, 4.0, 14.9, 15.0, 25.0, 25.1, 36.0, 36.1]:
    add("boundary", rng.uniform(30, 95), t, nh(), nl())
for lh in [89999, 90000, 284999, 285000]:
    add("boundary", rng.uniform(30, 95), nt(), nh(), lh)
for h in [59.9, 60.0, 70.0, 70.1]:
    add("boundary", rng.uniform(30, 95), nt(), h, nl())

with open("testset.jsonl", "w") as f:
    for c in cases:
        f.write(json.dumps(c) + "\n")

from collections import Counter
print(len(cases), Counter(c["kind"] for c in cases))
print("water", Counter(c["key"]["water"] for c in cases))
for lv in ["moisture_level", "temp_level", "light_level", "humidity_level"]:
    print(lv, Counter(c["key"][lv] for c in cases))
print("alerts", Counter(a for c in cases for a in c["key"]["alerts"]), "no alert:", sum(not c["key"]["alerts"] for c in cases))
