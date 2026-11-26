"""Nabta rules v3: rules v2 + the water tank (float switch) + the grow light.

Rules v2 (rules_v2.py) stay unchanged: the phase 2 model results were scored with them.
v3 adds three inputs and one decision:

  inputs   hour      0-23, local time of the reading
           light_on  0/1, is the grow light on right now (the light sensor also sees the LED)
           tank_low  0/1, float switch: the tank is almost empty
  decision light     "on" / "off"

Pump (key "water"):  yes if soil <= 70, no fault, and the tank is NOT low.
Tank low:            alert TANK_LOW and no watering (the pump would run dry).
Grow light:
  - off at night (before 06:00 or from 22:00): 16 h day, 8 h dark
  - light sensor broken (negative reading): on for the whole day (schedule only)
  - off once the 24 h light total reached 225,000 lux-h (= 15 mol/m2/day, where mint grows best;
    see WATER_AND_LIGHT_CHECK.md). v3 also uses 225,000 as the start of the "optimal" light level.
  - already on: stays on (the sensor now sees the LED, so "dark" can't be measured)
  - off: turns on only when it is dark (below 2,000 lux)

The three pump safety rules (3 h wait, 3 a day, no old readings) are NOT here: they stay in the
controller code and run after the decision, whoever made it (rules or model).
"""
import rules_v2
from rules_v2 import ALERT_ORDER as _V2_ALERTS, FAULT_MESSAGE, FAULTS, TOO_WET_AT

DAY_START, DAY_END = 6, 22        # light allowed 06:00-21:59
DARK_LUX = 2000                    # below this (light off) it is dark enough to need the LED
LIGHT_TARGET = 225000              # lux-h in 24 h (~15 mol/m2/day): sources [R3, R4], changed from 285,000
LOW_LIGHT_BELOW = 90000            # LOW_LIGHT alert below this (unchanged)
ALERT_ORDER = _V2_ALERTS + ["TANK_LOW"]
INPUTS = ["soil_moisture_index", "air_temp_c", "humidity_rh", "light_lux_now", "light_lux_hours_24h",
          "hour", "light_on", "tank_low"]

# Words the explainer and chat use for the new alert (only if the phase 1 explainer is loaded)
try:
    import explain_bench as _eb
    _eb.TIPS.setdefault("TANK_LOW", "the water tank is almost empty, please refill it")
    _eb.ALERT_MENTION.setdefault("TANK_LOW", r"tank|refill|out of water|no water left")
    _eb.ALERT_FAKE.setdefault("TANK_LOW", r"tank is (almost )?empty|refill the tank")
    if LIGHT_TARGET not in _eb.THRESHOLDS:
        _eb.THRESHOLDS.append(LIGHT_TARGET)        # a limit the explainer may quote
except ImportError:
    pass


def light_level(lux_24h):
    """v3 light level: optimal from 225,000 lux-h (v2 used 285,000)."""
    if lux_24h >= LIGHT_TARGET: return "optimal"
    if lux_24h >= LOW_LIGHT_BELOW: return "acceptable"
    return "low"


def light_decision(hour, lux_now, lux_24h, light_on, light_sensor_ok=True):
    if not (DAY_START <= hour < DAY_END):
        return "off"
    if not light_sensor_ok:
        return "on"
    if lux_24h >= LIGHT_TARGET:
        return "off"
    if light_on:
        return "on"
    return "on" if lux_now < DARK_LUX else "off"


def decide(row, prev=None, pumped_before=False):
    """Full v3 decision for one 30-min row. Missing new inputs default to: hour 12, light off, tank OK."""
    k = rules_v2.decide(row, prev, pumped_before)
    k["light_level"] = light_level(row["light_lux_hours_24h"])
    hour = int(row.get("hour", 12))
    light_on = bool(row.get("light_on", 0))
    tank_low = bool(row.get("tank_low", 0))
    if tank_low:
        k["water"] = "no"
        k["alerts"] = k["alerts"] + ["TANK_LOW"]
    light_ok = row["light_lux_now"] >= 0 and row["light_lux_hours_24h"] >= 0
    k["light"] = light_decision(hour, row["light_lux_now"], row["light_lux_hours_24h"], light_on, light_ok)
    return k
