#!/usr/bin/env python3
"""Nabta controller: the RULES (v3) decide the pump and the grow light, qwen3.5:0.8b explains.

Every 30 minutes garden_logger.py adds one averaged row to log_30min.csv. For each new row:
  1. fault check (rules v2): broken / unplugged sensor, impossible values, pump fault
  2. decision (rules v3): levels, alerts, pump (water yes/no), grow light (on/off)
       - water if soil <= 70, no fault, and the tank is not low (float switch, alert TANK_LOW)
       - grow light only 06:00-22:00, on when it is dark and the 24 h light total is below target
  3. pump safety (code, always): no second watering within 3 hours, at most 3 a day,
     never on a reading more than 45 minutes old
  4. message: a fault gets a fixed message (no model); otherwise qwen3.5:0.8b explains the
     decision with the tested prompt e3. If the model is off or not available, a code sentence is used.
  5. everything is saved in logs/<YYYY-MM>/decisions.csv (see nabta_paths.py)

After the Pi was off: the controller goes on after the last row it handled (logs/controller_state.json),
and it compares a reading with the previous one only if that one is at most 45 min older (otherwise the
drop / rise fault checks are skipped, so a gap cannot cause a false sensor or pump fault).

The pump and the light are OFF unless PUMP_ENABLED / LIGHT_ENABLED = True. Until then the controller
writes "WOULD WATER" / "WOULD TURN ON".

    python3 nabta_controller.py           # run forever (checks for a new row every 60 s)
    python3 nabta_controller.py --once    # decide on the latest row now and stop
"""
import argparse, csv, json, os, signal, sys, time
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rules_v2
import rules_v3 as rules
import explain_bench as eb
import nabta_paths as paths

STATE = paths.STATE
MODEL = "qwen3.5:0.8b"
USE_MODEL = False           # False = code sentences only (no load on the Pi). True when the Pi has cooling.
MAX_GAP_MIN = 45            # the previous reading counts only if it is at most 45 min older

# ---- relays (2-relay module). Tested on the Pi 24 Nov 2026: the pump is on relay 2. OFF while testing ----
PUMP_ENABLED = False
LIGHT_ENABLED = False
PUMP_PIN = 24               # BCM 24 = pin 18 -> relay IN2 (K2, pump)   (tested: the pump runs)
LIGHT_PIN = 23              # BCM 23 = pin 16 -> relay IN1 (K1, grow light, not connected yet)
RELAY_ACTIVE_LOW = True     # tested: this board switches ON when IN is LOW (inputs idle HIGH)
PUMP_SECONDS = 8            # one dose: measure it (cup test) and set it
DOSE_ML = 150
WAIT_HOURS = 3              # no second watering within 3 h (the water needs time to reach the probe)
MAX_PER_DAY = 3
BLOCK_WHEN_TANK_LOW = True  # 4th safety rule: never run the pump when the float says the tank is low
DECIDER = "rules"           # who makes the decision: "rules" now; "model" after the fine-tuning test
DATA_VERSION = 3            # model input/output format version (see DATA_FORMAT.md)

COLS = ["soil_moisture_index", "air_temp_c", "humidity_rh", "light_lux_now", "light_lux_hours_24h"]
LEVELS = ["moisture_level", "temp_level", "light_level", "humidity_level"]
OUT_COLS = ["timestamp", *COLS, "hour", "tank_low", "light_before", *LEVELS,
            "faults", "alerts", "water_decision", "pump_action", "light_decision", "light_action",
            "message", "message_source", "model_seconds"]

_gpio = None


def gpio():
    """RPi.GPIO, set up once (outputs start OFF). None if not on a Pi."""
    global _gpio
    if _gpio is None:
        import RPi.GPIO as GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        off = GPIO.HIGH if RELAY_ACTIVE_LOW else GPIO.LOW
        for pin, on in ((PUMP_PIN, PUMP_ENABLED), (LIGHT_PIN, LIGHT_ENABLED)):
            if on:
                GPIO.setup(pin, GPIO.OUT, initial=off)
        _gpio = GPIO
    return _gpio


def relay(pin, on):
    G = gpio()
    G.output(pin, (G.LOW if on else G.HIGH) if RELAY_ACTIVE_LOW else (G.HIGH if on else G.LOW))


def load_state():
    try:
        s = json.load(open(STATE))
    except (OSError, ValueError):
        s = {}
    s.setdefault("last_row", None); s.setdefault("waterings", []); s.setdefault("light_on", False)
    return s


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


def tank_value(r):
    """1 = tank low, 0 = OK, None = unknown (float not set up yet: the pump is not blocked)."""
    v = (r.get("tank_low") or "").strip()
    return int(float(v)) if v else None


def decide(row, prev, pumped_before, light_on):
    x = to_reading(row)
    hour = datetime.fromisoformat(row["timestamp"]).hour
    tank = tank_value(row)
    x_in = {**x, "hour": hour, "light_on": int(light_on), "tank_low": tank or 0}
    miss = [c for c in COLS if x[c] is None]
    if miss:
        lux_ok = x["light_lux_now"] is not None and x["light_lux_hours_24h"] is not None
        light = rules.light_decision(hour, x["light_lux_now"] or 0, x["light_lux_hours_24h"] or 0,
                                     light_on, light_sensor_ok=lux_ok)
        k = {lv: "" for lv in LEVELS}
        k.update({"alerts": ["TANK_LOW"] if tank else [], "water": "no", "light": light,
                  "faults": ["SENSOR_ERROR"], "fault_reason": "no reading for " + ", ".join(miss)})
        return x_in, k
    p = to_reading(prev) if prev else None
    if p and any(v is None for v in p.values()):
        p = None
    return x_in, rules.decide(x_in, p, pumped_before)


def pump_action(k, state, now, tank_low=None):
    if k["water"] != "yes":
        return "none"
    if BLOCK_WHEN_TANK_LOW and tank_low == 1:
        return "BLOCKED (tank low: refill the tank)"
    recent = [datetime.fromisoformat(t) for t in state["waterings"]]
    if any(now - t < timedelta(hours=WAIT_HOURS) for t in recent):
        return f"WAIT (watered less than {WAIT_HOURS} h ago)"
    if sum(t.date() == now.date() for t in recent) >= MAX_PER_DAY:
        return f"HOLD (already {MAX_PER_DAY} waterings today: check the tank and the probe)"
    if PUMP_ENABLED:
        relay(PUMP_PIN, True); time.sleep(PUMP_SECONDS); relay(PUMP_PIN, False)
        act = f"WATERED {DOSE_ML} mL"
    else:
        act = f"WOULD WATER {DOSE_ML} mL (pump off)"
    state["waterings"] = [t for t in state["waterings"]
                          if now - datetime.fromisoformat(t) < timedelta(days=2)] + [now.isoformat()]
    return act


def light_action(k, state):
    want = k["light"] == "on"
    if LIGHT_ENABLED:
        relay(LIGHT_PIN, want)
        act = ("LIGHT ON" if want else "LIGHT OFF") + ("" if want != state["light_on"] else " (no change)")
        state["light_on"] = want
    else:
        act = ("WOULD TURN ON" if want else "OFF") + " (light not connected)"
        state["light_on"] = False
    return act


def code_sentence(x, k):
    m = x["soil_moisture_index"]
    tank = "TANK_LOW" in k["alerts"]
    if k["water"] == "yes":
        s = f"I'm watering your mint now: the soil moisture is {m}, which is 70 or below."
    elif tank and m <= 70:
        s = (f"The soil moisture is {m} and needs water, but the water tank is almost empty, "
             f"so I can't water. Please refill the tank.")
    else:
        s = f"No watering needed: the soil moisture is {m}."
    tips = " ".join(eb.TIPS[a][0].upper() + eb.TIPS[a][1:] + "." for a in k["alerts"]
                    if not (a == "TANK_LOW" and m <= 70))
    light = "The grow light is on." if k["light"] == "on" else ""
    return " ".join(p for p in (s, tips, light) if p)


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
    light_before = state["light_on"]
    x, k = decide(row, recent_prev(row, prev), pumped_before, light_before)
    age = now - datetime.fromisoformat(row["timestamp"])
    if age > timedelta(minutes=MAX_GAP_MIN):
        late = "SKIPPED (old row, %d min late)" % (age.total_seconds() // 60)
        act = late + ": never water on an old reading" if k["water"] == "yes" else "none"
        lact = late
    else:
        act = pump_action(k, state, now, tank_value(row))
        lact = light_action(k, state)
    if k["faults"]:
        msg, src, secs = message(x, k)
    elif act.startswith("BLOCKED"):
        msg, src, secs = (f"The soil reads {x['soil_moisture_index']} and needs water, but the water tank is "
                          f"almost empty, so I can't water. Please refill the tank.", "code (tank low)", 0.0)
    elif act.startswith(("WAIT", "HOLD")):
        msg, src, secs = (f"The soil reads {x['soil_moisture_index']}, but I watered recently, so I'm waiting "
                          f"before watering again. {act}.", "code (pump safety)", 0.0)
    elif act.startswith("SKIPPED"):
        msg, src, secs = (f"Old reading (soil {x['soil_moisture_index']}): recorded only, no watering.",
                          "code (old row)", 0.0)
    else:
        msg, src, secs = message(x, k)
    out = {"timestamp": row["timestamp"], **{c: row.get(c, "") for c in COLS},
           "hour": x["hour"], "tank_low": row.get("tank_low", ""), "light_before": "on" if light_before else "off",
           **{lv: k.get(lv, "") for lv in LEVELS},
           "faults": ";".join(k["faults"]) or "none", "alerts": ";".join(k["alerts"]) or "none",
           "water_decision": k["water"], "pump_action": act, "light_decision": k["light"], "light_action": lact,
           "message": msg, "message_source": src, "model_seconds": round(secs, 1)}
    path = paths.decisions_file(row["timestamp"])
    paths.ensure_header(path, OUT_COLS)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLS)
        if new: w.writeheader()
        w.writerow(out)
        f.flush(); os.fsync(f.fileno())
    # the model's exact input and the rules' answer, for fine-tuning and for tuning the simulator
    keys = ["moisture_level", "temp_level", "light_level", "humidity_level", "faults", "alerts", "water", "light"]
    paths.append_jsonl(paths.model_io_file(row["timestamp"]), {
        "v": DATA_VERSION, "timestamp": row["timestamp"], "decider": DECIDER,
        "input": {**{c: x[c] for c in COLS}, "hour": x["hour"], "light_on": x["light_on"], "tank_low": x["tank_low"]},
        "tank_known": tank_value(row) is not None,
        "rules": {kk: k.get(kk, "") for kk in keys},
        "fault_reason": k.get("fault_reason", ""),
        "actions": {"pump": act, "light": lact, "pump_seconds": PUMP_SECONDS if act.startswith("WATERED") else 0,
                    "pump_enabled": PUMP_ENABLED, "light_enabled": LIGHT_ENABLED},
        "samples": row.get("samples", ""), "message_source": src})
    state["last_row"] = row["timestamp"]
    save_state(state)
    print(f"[{row['timestamp']}] soil {row['soil_moisture_index']}, {row['air_temp_c']} C, "
          f"{row['humidity_rh']} %, light {row['light_lux_hours_24h']} lux-h, tank_low {row.get('tank_low') or '?'}")
    print(f"   faults: {out['faults']} | alerts: {out['alerts']} | water: {k['water']} -> {act} | "
          f"light: {k['light']} -> {lact}")
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
    print("Nabta controller started (pump %s, light %s, model %s). Waiting for new rows in %s/<YYYY-MM>/log_30min.csv" %
          ("ON" if PUMP_ENABLED else "OFF", "ON" if LIGHT_ENABLED else "OFF", "ON" if USE_MODEL else "OFF", paths.LOGS),
          flush=True)
    paths.log_event("controller", "started", "pump %s, light %s, model %s, last row done: %s" %
                    ("on" if PUMP_ENABLED else "off", "on" if LIGHT_ENABLED else "off",
                     "on" if USE_MODEL else "off", state["last_row"]))
    if LIGHT_ENABLED:                     # start dark; the next decision switches the light
        relay(LIGHT_PIN, False); state["light_on"] = False; save_state(state)

    def stop(*_):
        if PUMP_ENABLED or LIGHT_ENABLED:  # leave the relays off when the controller stops
            try:
                if PUMP_ENABLED: relay(PUMP_PIN, False)
                if LIGHT_ENABLED: relay(LIGHT_PIN, False)
                gpio().cleanup()
            except Exception:  # noqa: BLE001
                pass
        state["light_on"] = False; save_state(state)
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
