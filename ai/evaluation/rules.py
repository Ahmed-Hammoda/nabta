"""Nabta reference rules engine.

Computes the *correct* decision for a scenario from the spearmint plant profile
(docs/plant-research/plant-profile.json) and the evaluation settings (config.json).
Its output is the answer key the language models are scored against.

Standard library only, so it runs the same on Windows, Linux and a Raspberry Pi.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PROFILE_PATH = REPO / "docs" / "plant-research" / "plant-profile.json"
CONFIG_PATH = HERE / "config.json"

# Reason codes for the decision (exactly one per scenario)
REASONS = [
    "DRY_BELOW_MIN",        # moisture below the trigger -> water
    "MOISTURE_OK",          # moisture at or above the trigger -> no watering needed
    "SOAKING_WAIT",         # dry, but watered recently -> let the water spread first
    "RESERVOIR_EMPTY",      # dry, but the tank is empty -> cannot water
    "DAILY_LIMIT_REACHED",  # dry, but the daily water cap is used up
    "SENSOR_FAULT",         # moisture reading missing, impossible or frozen -> do not act
]

# Alert codes (zero or more per scenario)
ALERTS = [
    "DRY_STRESS", "WATERLOGGED", "RESERVOIR_EMPTY", "SENSOR_FAULT",
    "HEAT_STRESS", "HEAT_CRITICAL", "COLD_STRESS", "COLD_CRITICAL",
    "HUMIDITY_HIGH", "LOW_LIGHT",
]


def load_settings():
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return profile, config


def moisture_fault(ctx, config):
    """True if the moisture reading cannot be trusted."""
    m = ctx["latest"]["moisture_index"]
    if m is None:
        return True
    lo, hi = config["sensor_valid_index_range"]
    if not (lo <= m <= hi):
        return True
    recent = ctx.get("moisture_last_2h") or []
    window = config["frozen_sensor_window_readings"]
    if len(recent) >= window and len(set(recent[-window:])) == 1:
        return True
    return False


def decide(ctx, profile=None, config=None):
    """Return the correct decision for one scenario."""
    if profile is None or config is None:
        profile, config = load_settings()

    mi = profile["moisture_index"]
    temp = profile["air_temperature_c"]
    hum = profile["air_humidity_rh"]
    light = profile["light"]
    dose = profile["dose_limits_ml"]

    latest = ctx["latest"]
    hist = ctx["history_24h"]
    water = ctx["watering"]

    alerts = set()
    fault = moisture_fault(ctx, config)
    m = latest["moisture_index"]

    # ---- alerts ------------------------------------------------------------
    if fault:
        alerts.add("SENSOR_FAULT")
    else:
        if hist["hours_in_a_row_moisture_below_40"] >= mi["low_alarm"]["for_hours"]:
            alerts.add("DRY_STRESS")
        if hist["hours_in_a_row_moisture_above_95"] >= mi["high_alarm"]["for_hours"]:
            alerts.add("WATERLOGGED")

    if not latest["tank_ok"]:
        alerts.add("RESERVOIR_EMPTY")

    t = latest["air_temp_c"]
    if t is not None:
        if t > temp["critical_above"]:
            alerts.add("HEAT_CRITICAL")
        elif t > temp["warning_above"]:
            alerts.add("HEAT_STRESS")
        if t < temp["critical_below"]:
            alerts.add("COLD_CRITICAL")
        elif t < temp["warning_below"]:
            alerts.add("COLD_STRESS")

    if hist["hours_in_a_row_humidity_above_80"] >= hum["warning"]["for_hours"]:
        alerts.add("HUMIDITY_HIGH")

    if hist["light_lux_hours_last_24h"] < light["low_light_warning_lux_hours_per_day"]:
        alerts.add("LOW_LIGHT")

    # ---- watering decision -------------------------------------------------
    def no_action(reason):
        return {"action": "no_action", "ml": 0, "reason_code": reason,
                "alerts": sorted(alerts)}

    if fault:
        return no_action("SENSOR_FAULT")
    if m >= mi["water_trigger_below"]:
        return no_action("MOISTURE_OK")
    if not latest["tank_ok"]:
        return no_action("RESERVOIR_EMPTY")
    since = water["minutes_since_last"]
    if since is not None and since < config["soak_wait_minutes"]:
        return no_action("SOAKING_WAIT")

    remaining_today = dose["max_per_day"] - water["ml_today"]
    wanted = (config["refill_target_index"] - m) * config["ml_per_index_point"]
    ml = min(wanted, dose["max_per_watering"], remaining_today)
    ml = int(round(ml / 10.0) * 10)
    if ml < config["min_dose_ml"]:
        return no_action("DAILY_LIMIT_REACHED")

    return {"action": "water", "ml": ml, "reason_code": "DRY_BELOW_MIN",
            "alerts": sorted(alerts)}


if __name__ == "__main__":
    import sys
    for line in sys.stdin:
        if line.strip():
            print(json.dumps(decide(json.loads(line)["context"])))
