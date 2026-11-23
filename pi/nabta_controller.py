#!/usr/bin/env python3
"""Nabta controller: the RULES decide, qwen3.5:0.8b explains.

Every 30 minutes garden_logger.py adds one averaged row to log_30min.csv. For each new row:
  1. fault check (rules v2): broken / unplugged sensor, impossible values, pump fault
  2. decision (rules v2): water yes/no + alerts
  3. pump safety: no second watering within 3 hours, at most 3 waterings a day
  4. message: a fault gets a fixed message (no model); otherwise qwen3.5:0.8b explains
     the decision with the tested prompt e3. If the model is not available, a code sentence is used.
  5. everything is saved in logs/<YYYY-MM>/decisions.csv (see nabta_paths.py)

After the Pi was off: the controller goes on after the last row it handled (logs/controller_state.json),
and it compares a reading with the previous one only if that one is at most 45 min older (otherwise the
drop / rise fault checks are skipped, so a gap cannot cause a false sensor or pump fault).

The pump is OFF unless PUMP_ENABLED = True (then set RELAY_PIN). With the pump off, the
controller writes "WOULD WATER".

    python3 nabta_controller.py           # run forever (checks for a new row every 60 s)
    python3 nabta_controller.py --once    # decide on the latest row now and stop
"""
import argparse, csv, json, os, signal, sys, time
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rules_v2
import explain_bench as eb
import nabta_paths as paths

STATE = paths.STATE
MODEL = "qwen3.5:0.8b"
USE_MODEL = False           # False = code sentences only (no load on the Pi). True when the Pi has cooling.
MAX_GAP_MIN = 45            # the previous reading counts only if it is at most 45 min older

# ---- pump (OFF while testing) ----
PUMP_ENABLED = False
RELAY_PIN = None            # BCM pin of the relay, set it when the pump is connected
PUMP_SECONDS = 8            # one dose (about 150 mL: measure it on the real pump)
DOSE_ML = 150
WAIT_HOURS = 3              # no second watering within 3 h (the water needs time to reach the probe)
MAX_PER_DAY = 3

COLS = ["soil_moisture_index", "air_temp_c", "humidity_rh", "light_lux_now", "light_lux_hours_24h"]
OUT_COLS = ["timestamp", *COLS, "moisture_level", "temp_level", "light_level", "humidity_level",
            "faults", "alerts", "water_decision", "pump_action", "message", "message_source", "model_seconds"]


def load_state():
    try:
        return json.load(open(STATE))
    except (OSError, ValueError):
        return {"last_row": None, "waterings": []}


def save_state(s):
    json.dump(s, open(STATE, "w"), indent=1)


def read_rows():
    """30-min rows of this month and last month, oldest first."""
    return paths.read_csv("log_30min.csv", last=2)


def recent_prev(row, prev):
    """The previous row, or None if it is more than MAX_GAP_MIN older (the Pi was off)."""
    if not prev:
        return None
    gap = datetime.fromisoformat(row["timestamp"]) - datetime.fromisoformat(prev["timestamp"])
    return prev if gap <= timedelta(minutes=MAX_GAP_MIN) else None


def to_reading(r):
    """CSV row -> floats. An empty cell (sensor not read) stays None."""
    out = {}
    for c in COLS:
        v = (r.get(c) or "").strip()
        out[c] = float(v) if v else None
    return out


def missing_fault(x):
    miss = [c for c in COLS if x[c] is None]
    return [("SENSOR_ERROR", "no reading for " + ", ".join(miss))] if miss else []


def decide(row, prev, pumped_before):
    x = to_reading(row)
    miss = missing_fault(x)
    if miss:
        k = {"moisture_level": "", "temp_level": "", "light_level": "", "humidity_level": "",
             "alerts": [], "water": "no", "faults": ["SENSOR_ERROR"], "fault_reason": miss[0][1]}
        return x, k
    p = to_reading(prev) if prev else None
    if p and any(v is None for v in p.values()):
        p = None
    return x, rules_v2.decide(x, p, pumped_before)


def pump_action(k, state, now):
    if k["water"] != "yes":
        return "none"
    recent = [datetime.fromisoformat(t) for t in state["waterings"]]
    if any(now - t < timedelta(hours=WAIT_HOURS) for t in recent):
        return f"WAIT (watered less than {WAIT_HOURS} h ago)"
    if sum(t.date() == now.date() for t in recent) >= MAX_PER_DAY:
        return f"HOLD (already {MAX_PER_DAY} waterings today: check the tank and the probe)"
    if PUMP_ENABLED and RELAY_PIN is not None:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM); GPIO.setup(RELAY_PIN, GPIO.OUT)
        GPIO.output(RELAY_PIN, GPIO.HIGH); time.sleep(PUMP_SECONDS); GPIO.output(RELAY_PIN, GPIO.LOW)
        GPIO.cleanup(RELAY_PIN)
        act = f"WATERED {DOSE_ML} mL"
    else:
        act = f"WOULD WATER {DOSE_ML} mL (pump off)"
    state["waterings"] = [t for t in state["waterings"]
                          if now - datetime.fromisoformat(t) < timedelta(days=2)] + [now.isoformat()]
    return act


def code_sentence(x, k):
    m = x["soil_moisture_index"]
    s = (f"I'm watering your mint now: the soil moisture is {m}, which is 70 or below."
         if k["water"] == "yes" else f"No watering needed: the soil moisture is {m}.")
    tips = " ".join(eb.TIPS[a][0].upper() + eb.TIPS[a][1:] + "." for a in k["alerts"])
    return (s + " " + tips).strip()


def message(x, k):
    """Fixed text for a fault; otherwise qwen3.5:0.8b with the tested prompt e3."""
    if k["faults"]:
        f = k["faults"][0]
        return rules_v2.FAULT_MESSAGE[f].format(reason=k["fault_reason"]), "fixed (fault)", 0.0
    if not USE_MODEL:
        return code_sentence(x, k), "code (model off)", 0.0
    try:
        text, secs = eb.ask(MODEL, eb.messages("e3", {"input": x, "key": k}), False)
        if text:
            return text, MODEL, secs
    except Exception as e:  # noqa: BLE001 - Ollama not running, model missing, timeout
        print("[warn] model not available:", e, file=sys.stderr)
    return code_sentence(x, k), "code (model not available)", 0.0


def handle(row, prev, state):
    now = datetime.now().astimezone()
    pumped_before = any(now - datetime.fromisoformat(t) < timedelta(minutes=40) for t in state["waterings"])
    x, k = decide(row, recent_prev(row, prev), pumped_before)
    age = now - datetime.fromisoformat(row["timestamp"])
    if age > timedelta(minutes=MAX_GAP_MIN) and k["water"] == "yes":
        act = "SKIPPED (old row, %d min late: never water on an old reading)" % (age.total_seconds() // 60)
    else:
        act = pump_action(k, state, now)
    if k["faults"]:
        msg, src, secs = message(x, k)
    elif act.startswith(("WAIT", "HOLD")):
        msg, src, secs = (f"The soil reads {x['soil_moisture_index']}, but I watered recently, so I'm waiting "
                          f"before watering again. {act}.", "code (pump safety)", 0.0)
    elif act.startswith("SKIPPED"):
        msg, src, secs = (f"Old reading (soil {x['soil_moisture_index']}): recorded only, no watering.",
                          "code (old row)", 0.0)
    else:
        msg, src, secs = message(x, k)
    out = {"timestamp": row["timestamp"], **{c: row.get(c, "") for c in COLS},
           **{lv: k.get(lv, "") for lv in ("moisture_level", "temp_level", "light_level", "humidity_level")},
           "faults": ";".join(k["faults"]) or "none", "alerts": ";".join(k["alerts"]) or "none",
           "water_decision": k["water"], "pump_action": act, "message": msg, "message_source": src,
           "model_seconds": round(secs, 1)}
    path = paths.decisions_file(row["timestamp"])
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLS)
        if new: w.writeheader()
        w.writerow(out)
        f.flush(); os.fsync(f.fileno())
    state["last_row"] = row["timestamp"]
    save_state(state)
    print(f"[{row['timestamp']}] soil {row['soil_moisture_index']}, {row['air_temp_c']} C, "
          f"{row['humidity_rh']} %, light {row['light_lux_hours_24h']} lux-h")
    print(f"   faults: {out['faults']} | alerts: {out['alerts']} | water: {k['water']} | pump: {act}")
    print(f"   message ({src}, {secs:.1f} s): {msg}\n", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="decide on the latest row now and stop")
    a = ap.parse_args()
    os.makedirs(paths.LOGS, exist_ok=True)
    state = load_state()
    if a.once:
        rows = read_rows()
        if not rows:
            sys.exit("No 30-min rows yet in logs/<YYYY-MM>/log_30min.csv: start garden_logger.py first.")
        handle(rows[-1], rows[-2] if len(rows) > 1 else None, state)
        return
    print("Nabta controller started (pump %s, model %s). Waiting for new rows in %s/<YYYY-MM>/log_30min.csv" %
          ("ON" if PUMP_ENABLED else "OFF", "ON" if USE_MODEL else "OFF", paths.LOGS), flush=True)
    paths.log_event("controller", "started", "pump %s, model %s, last row done: %s" %
                    ("on" if PUMP_ENABLED else "off", "on" if USE_MODEL else "off", state["last_row"]))

    def stop(*_):
        paths.log_event("controller", "stopped")
        sys.exit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while True:
        rows = read_rows()
        done = [i for i, r in enumerate(rows) if r["timestamp"] == state["last_row"]]
        start = done[-1] + 1 if done else max(0, len(rows) - 1)
        for i in range(start, len(rows)):
            handle(rows[i], rows[i - 1] if i > 0 else None, state)
        time.sleep(60)


if __name__ == "__main__":
    main()
