"""Laptop test of the v3 Pi code in a throwaway copy: header upgrade + controller decisions."""
import csv, io, os, shutil, sys, contextlib
from datetime import datetime, timedelta

SRC, TMP = sys.argv[1], sys.argv[2]
shutil.rmtree(TMP, ignore_errors=True)
shutil.copytree(SRC, TMP, ignore=shutil.ignore_patterns("__pycache__", "logs"))
sys.path.insert(0, TMP)
os.chdir(TMP)
import nabta_paths as paths
import nabta_controller as c
import garden_logger as g

now = datetime.now().astimezone().replace(microsecond=0)
m = paths.month_dir(now)

# 1. an OLD-format 30-min file (7 columns) gets the new column without losing rows
old_hdr = ["timestamp", "soil_moisture_index", "air_temp_c", "humidity_rh", "light_lux_now", "light_lux_hours_24h", "samples"]
with open(os.path.join(m, "log_30min.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(old_hdr)
    w.writerow([(now - timedelta(hours=5)).isoformat(), 80.0, 22.0, 55.0, 300.0, 50000.0, 180])
g.append_row(paths.avg_file(now), g.AVG_HEADER, [(now - timedelta(hours=4)).isoformat(), 79, 22, 55, 300, 50000, 0, 180])
rows = paths.read_csv("log_30min.csv")
print("1. header upgrade:", list(rows[0].keys()) == g.AVG_HEADER, "| rows kept:", len(rows),
      "| old row tank_low:", repr(rows[0]["tank_low"]), "| new row tank_low:", rows[1]["tank_low"])


def case(label, soil, temp, lux_now, lux24, hour, tank, light_on, waterings=()):
    ts = now.replace(hour=hour, minute=0, second=0)
    if ts > now: ts -= timedelta(days=1)
    row = {"timestamp": ts.isoformat(), "soil_moisture_index": str(soil), "air_temp_c": str(temp), "humidity_rh": "55",
           "light_lux_now": str(lux_now), "light_lux_hours_24h": str(lux24), "tank_low": "" if tank is None else str(tank)}
    state = {"last_row": None, "waterings": list(waterings), "light_on": light_on}
    # make the row "fresh" (not an old reading) by moving 'now' in the controller
    real_dt = c.datetime
    class FakeDT(real_dt):
        @classmethod
        def now(cls, tz=None): return ts + timedelta(minutes=1)
    c.datetime = FakeDT
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        c.handle(row, None, state)
    c.datetime = real_dt
    d = paths.read_csv("decisions.csv")[-1]
    print(f"{label:<38} water {d['water_decision']:<3} -> {d['pump_action'][:30]:<30} | light {d['light_decision']:<3} -> "
          f"{d['light_action'][:34]:<34} | alerts {d['alerts']}")
    return d

print("\n2. controller decisions (pump and light not connected):")
case("dry soil, tank OK, 10:00, dark", 55, 22, 50, 40000, 10, 0, False)
d = case("dry soil, TANK LOW, 10:00", 55, 22, 50, 40000, 10, 1, False)
print("   message:", d["message"])
case("dry soil, tank unknown (float not set)", 55, 22, 50, 40000, 10, None, False)
case("wet soil, 23:00 (night)", 85, 22, 0, 40000, 23, 0, False)
case("05:00 dark, before the day starts", 85, 22, 0, 40000, 5, 0, False)
case("12:00 bright sun 20,000 lux", 85, 22, 20000, 150000, 12, 0, False)
case("16:00 LED on, 24 h total low", 85, 22, 3000, 150000, 16, 0, True)
case("16:00 LED on, 24 h total reached", 85, 22, 3000, 300000, 16, 0, True)
case("dry soil, watered 1 h ago (safety)", 55, 22, 50, 40000, 10, 0, False,
     waterings=[(now.replace(hour=9, minute=0, second=0)).isoformat()])
case("probe out of soil (soil 0)", 0, 22, 50, 40000, 10, 0, False)
import json
lines = [json.loads(l) for l in open(paths.model_io_file(now), encoding="utf-8")]
tank = [l for l in lines if l["input"]["tank_low"] == 1][0]
print("4. model_io.jsonl:", len(lines), "lines | input keys:", list(lines[0]["input"]))
print("   rules keys:", list(lines[0]["rules"]))
print("   tank-low line -> rules water:", tank["rules"]["water"], "| pump action:", tank["actions"]["pump"])
hdr = next(csv.reader(open(paths.decisions_file(now), newline="")))
print("\n3. decisions.csv columns:", hdr == c.OUT_COLS, len(hdr))
