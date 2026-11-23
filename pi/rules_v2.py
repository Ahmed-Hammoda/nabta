"""Nabta rules v2: the rules for the live system, after the sensor calibration of 2026-11-15.

simulation_phase1/bench/labels.py stays frozen: it is the key of the 184-case benchmark (phase 1).
v2 changes two things:

1. TOO_WET at 98 or above (design choice). With the new calibration the index stops at 100
   (= probe in water), so the old rule "above 100" could never fire.
2. A fault check runs BEFORE the decision. It needs the previous row, so it lives outside label().
   On a fault the system does not water, and the user gets a fixed message (no language model).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "simulation_phase1", "bench"))  # phase-1 labels.py
from labels import temp_level, light_level, humidity_level

TOO_WET_AT = 98
ALERT_ORDER = ["DRY_DANGER", "TOO_WET", "HEAT_DANGER", "COLD_DANGER", "LOW_LIGHT"]
FAULTS = ["SENSOR_ERROR", "PUMP_FAULT"]

# Fault limits (30-min rows)
PROBE_IN_AIR = 2.0      # calibrated: dry air = 0. Soil in a pot never reads this low.
MAX_DROP = 15.0         # drying is at most ~3 points per hour; a bigger fall is a sensor problem
MAX_RISE_NO_PUMP = 10.0 # rain adds ~2 per 30 min; a bigger rise with the pump off = pump stuck or sensor fault


def moisture_level(m):
    if m >= TOO_WET_AT: return "too_wet"
    if m >= 90: return "optimal"
    if m > 70: return "acceptable"
    if m > 25: return "dry"
    return "danger_dry"


def label(m, t, h, lh):
    """Decision for one valid reading (same structure as labels.label)."""
    ml = moisture_level(m)
    alerts = []
    if ml == "danger_dry": alerts.append("DRY_DANGER")
    if ml == "too_wet": alerts.append("TOO_WET")
    if t > 36: alerts.append("HEAT_DANGER")
    if t < 4: alerts.append("COLD_DANGER")
    if light_level(lh) == "low": alerts.append("LOW_LIGHT")
    return {"moisture_level": ml, "temp_level": temp_level(t), "light_level": light_level(lh),
            "humidity_level": humidity_level(h), "alerts": alerts, "water": "yes" if m <= 70 else "no"}


def check_faults(row, prev=None, pumped_before=False):
    """Return a list of (fault, reason). row/prev: dicts with the log columns (floats)."""
    out = []
    m = row["soil_moisture_index"]
    if not (0 <= m <= 100):
        out.append(("SENSOR_ERROR", f"soil reading {m} is outside 0-100"))
    elif m <= PROBE_IN_AIR:
        out.append(("SENSOR_ERROR", f"soil reads {m}, like dry air: probe out of the soil or unplugged"))
    if not (-10 <= row["air_temp_c"] <= 60):
        out.append(("SENSOR_ERROR", f"air temperature {row['air_temp_c']} is impossible"))
    if not (1 <= row["humidity_rh"] <= 100):
        out.append(("SENSOR_ERROR", f"humidity {row['humidity_rh']} is impossible"))
    if row["light_lux_now"] < 0 or row["light_lux_hours_24h"] < 0:
        out.append(("SENSOR_ERROR", "negative light reading"))
    if prev is not None:
        d = m - prev["soil_moisture_index"]
        if d < -MAX_DROP:
            out.append(("SENSOR_ERROR", f"soil fell {-d:.1f} points in 30 min, faster than soil can dry"))
        elif d > MAX_RISE_NO_PUMP and not pumped_before and prev["soil_moisture_index"] > PROBE_IN_AIR:
            # (a rise right after a probe-in-air reading is the sensor coming back, not the pump)
            out.append(("PUMP_FAULT", f"soil rose {d:.1f} points in 30 min with the pump off: pump stuck on?"))
    return out


FAULT_MESSAGE = {
    "SENSOR_ERROR": "Sensor problem: {reason}. I am not watering until it is checked.",
    "PUMP_FAULT": "Pump problem: {reason}. I have stopped watering; please check the pump.",
}


def decide(row, prev=None, pumped_before=False):
    """Full v2 decision: fault check first, then the rules. Returns the key dict."""
    faults = check_faults(row, prev, pumped_before)
    k = label(row["soil_moisture_index"], row["air_temp_c"], row["humidity_rh"], row["light_lux_hours_24h"])
    if faults:
        k["water"] = "no"
        # moisture alerts are meaningless on a broken soil reading; keep the others
        k["alerts"] = [a for a in k["alerts"] if a not in ("DRY_DANGER", "TOO_WET")]
        k["faults"] = sorted({f for f, _ in faults})
        k["fault_reason"] = "; ".join(r for _, r in faults)
    else:
        k["faults"], k["fault_reason"] = [], ""
    return k
