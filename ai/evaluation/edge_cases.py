"""Hand-made scenarios for situations real data rarely contains.

Each case states what we *intend* the answer to be. build_testset.py checks that
the rules engine agrees, so these cases also work as unit tests for rules.py.
"""

import copy


def base():
    """A calm, healthy midday situation. Every case starts from this."""
    return {
        "time": "13:00",
        "pot_id": "A",
        "latest": {
            "moisture_index": 72.0,
            "air_temp_c": 22.0,
            "humidity_rh": 55.0,
            "light_lux": 14000,
            "tank_ok": True,
        },
        "moisture_last_2h": [74.0, 73.6, 73.1, 72.5, 72.0],
        "history_24h": {
            "moisture_min": 70.0,
            "moisture_max": 88.0,
            "hours_in_a_row_moisture_below_40": 0,
            "hours_in_a_row_moisture_above_95": 0,
            "hours_in_a_row_humidity_above_80": 0,
            "air_temp_min": 15.0,
            "air_temp_max": 24.0,
            "light_lux_hours_last_24h": 190000,
        },
        "watering": {"minutes_since_last": 900, "last_ml": 120, "ml_today": 0},
    }


def dry(c, m=48.0):
    c["latest"]["moisture_index"] = m
    c["moisture_last_2h"] = [m + 2.0, m + 1.5, m + 1.0, m + 0.5, m]
    c["history_24h"]["moisture_min"] = m
    return c


def case(cid, description, expect, **changes):
    c = base()
    for path, value in changes.items():
        target = c
        keys = path.split("__")
        for k in keys[:-1]:
            target = target[k]
        target[keys[-1]] = value
    return {"id": cid, "source": "edge", "description": description,
            "context": c, "intended": expect}


def build():
    cases = []

    # --- normal decisions -------------------------------------------------
    cases.append(case("edge-001", "Healthy, moist soil", ("no_action", "MOISTURE_OK", [])))

    c = case("edge-002", "Dry soil, everything else normal", ("water", "DRY_BELOW_MIN", []))
    dry(c["context"], 50.0)
    cases.append(c)

    c = case("edge-003", "Exactly at the trigger (60) counts as moist", ("no_action", "MOISTURE_OK", []))
    dry(c["context"], 60.0)
    cases.append(c)

    c = case("edge-004", "Just below the trigger", ("water", "DRY_BELOW_MIN", []))
    dry(c["context"], 59.0)
    cases.append(c)

    # --- safety blocks ----------------------------------------------------
    c = case("edge-010", "Dry soil but the tank is empty",
             ("no_action", "RESERVOIR_EMPTY", ["RESERVOIR_EMPTY"]), latest__tank_ok=False)
    dry(c["context"], 45.0)
    cases.append(c)

    cases.append(case("edge-011", "Tank empty while soil is moist: alert only",
                      ("no_action", "MOISTURE_OK", ["RESERVOIR_EMPTY"]), latest__tank_ok=False))

    c = case("edge-012", "Dry, but watered 10 minutes ago",
             ("no_action", "SOAKING_WAIT", []), watering__minutes_since_last=10, watering__ml_today=150)
    dry(c["context"], 55.0)
    cases.append(c)

    c = case("edge-013", "Dry, watered 45 minutes ago (soak time is over)",
             ("water", "DRY_BELOW_MIN", []), watering__minutes_since_last=45, watering__ml_today=150)
    dry(c["context"], 52.0)
    cases.append(c)

    c = case("edge-014", "Dry, daily cap (500 mL) fully used",
             ("no_action", "DAILY_LIMIT_REACHED", []), watering__ml_today=500,
             watering__minutes_since_last=120)
    dry(c["context"], 50.0)
    cases.append(c)

    c = case("edge-015", "Dry, only 60 mL left in today's cap: dose is reduced",
             ("water", "DRY_BELOW_MIN", []), watering__ml_today=440, watering__minutes_since_last=180)
    dry(c["context"], 40.0)
    cases.append(c)

    c = case("edge-016", "Very dry: dose capped at 150 mL per watering",
             ("water", "DRY_BELOW_MIN", []))
    dry(c["context"], 30.0)
    cases.append(c)

    # --- sensor faults ----------------------------------------------------
    c = case("edge-020", "Moisture reading missing", ("no_action", "SENSOR_FAULT", ["SENSOR_FAULT"]))
    c["context"]["latest"]["moisture_index"] = None
    c["context"]["moisture_last_2h"] = [72.5, 72.3, 72.1, 72.0, None]
    cases.append(c)

    c = case("edge-021", "Impossible moisture reading (130)", ("no_action", "SENSOR_FAULT", ["SENSOR_FAULT"]))
    c["context"]["latest"]["moisture_index"] = 130.0
    c["context"]["moisture_last_2h"] = [72.4, 72.2, 72.1, 72.0, 130.0]
    cases.append(c)

    c = case("edge-022", "Impossible negative reading while looking dry",
             ("no_action", "SENSOR_FAULT", ["SENSOR_FAULT"]))
    c["context"]["latest"]["moisture_index"] = -12.0
    c["context"]["moisture_last_2h"] = [45.0, 44.6, 44.1, 43.8, -12.0]
    cases.append(c)

    c = case("edge-023", "Frozen sensor: same low value for 2 hours",
             ("no_action", "SENSOR_FAULT", ["SENSOR_FAULT"]))
    c["context"]["latest"]["moisture_index"] = 35.0
    c["context"]["moisture_last_2h"] = [35.0] * 5
    cases.append(c)

    # --- plant stress alerts ----------------------------------------------
    c = case("edge-030", "Dry for 3 hours in a row: water and raise a stress alert",
             ("water", "DRY_BELOW_MIN", ["DRY_STRESS"]),
             history_24h__hours_in_a_row_moisture_below_40=3)
    dry(c["context"], 32.0)
    cases.append(c)

    c = case("edge-031", "Dry for only 1 hour: water, no stress alert yet",
             ("water", "DRY_BELOW_MIN", []), history_24h__hours_in_a_row_moisture_below_40=1)
    dry(c["context"], 38.0)
    cases.append(c)

    c = case("edge-032", "Waterlogged for over 24 hours",
             ("no_action", "MOISTURE_OK", ["WATERLOGGED"]),
             history_24h__hours_in_a_row_moisture_above_95=26)
    c["context"]["latest"]["moisture_index"] = 97.0
    c["context"]["moisture_last_2h"] = [97.4, 97.2, 97.1, 97.0, 97.0]
    cases.append(c)

    c = case("edge-033", "Very wet but only for 10 hours: no alert yet",
             ("no_action", "MOISTURE_OK", []), history_24h__hours_in_a_row_moisture_above_95=10)
    c["context"]["latest"]["moisture_index"] = 96.5
    c["context"]["moisture_last_2h"] = [97.5, 97.2, 96.9, 96.7, 96.5]
    cases.append(c)

    # --- weather alerts ---------------------------------------------------
    c = case("edge-040", "Hot afternoon (31 °C) and dry soil",
             ("water", "DRY_BELOW_MIN", ["HEAT_STRESS"]), latest__air_temp_c=31.0, time="15:00")
    dry(c["context"], 54.0)
    cases.append(c)

    cases.append(case("edge-041", "Critical heat (37 °C), soil still moist",
                      ("no_action", "MOISTURE_OK", ["HEAT_CRITICAL"]), latest__air_temp_c=37.0))

    cases.append(case("edge-042", "Cold night (8 °C)",
                      ("no_action", "MOISTURE_OK", ["COLD_STRESS"]), latest__air_temp_c=8.0,
                      latest__light_lux=0, time="03:00"))

    cases.append(case("edge-043", "Freezing risk (3 °C)",
                      ("no_action", "MOISTURE_OK", ["COLD_CRITICAL"]), latest__air_temp_c=3.0,
                      latest__light_lux=0, time="05:00"))

    cases.append(case("edge-044", "Humid for 14 hours in a row",
                      ("no_action", "MOISTURE_OK", ["HUMIDITY_HIGH"]), latest__humidity_rh=86.0,
                      history_24h__hours_in_a_row_humidity_above_80=14))

    cases.append(case("edge-045", "Humid for only 6 hours: no alert yet",
                      ("no_action", "MOISTURE_OK", []), latest__humidity_rh=84.0,
                      history_24h__hours_in_a_row_humidity_above_80=6))

    cases.append(case("edge-046", "Dark day: low light total",
                      ("no_action", "MOISTURE_OK", ["LOW_LIGHT"]),
                      history_24h__light_lux_hours_last_24h=60000))

    # --- combined situations ----------------------------------------------
    c = case("edge-050", "Dry, hot and tank empty",
             ("no_action", "RESERVOIR_EMPTY", ["HEAT_STRESS", "RESERVOIR_EMPTY"]),
             latest__tank_ok=False, latest__air_temp_c=32.0)
    dry(c["context"], 41.0)
    cases.append(c)

    c = case("edge-051", "Frozen sensor and empty tank: fault comes first",
             ("no_action", "SENSOR_FAULT", ["RESERVOIR_EMPTY", "SENSOR_FAULT"]),
             latest__tank_ok=False)
    c["context"]["latest"]["moisture_index"] = 50.0
    c["context"]["moisture_last_2h"] = [50.0] * 5
    cases.append(c)

    c = case("edge-052", "Dry, dark and cold at night",
             ("water", "DRY_BELOW_MIN", ["COLD_STRESS", "LOW_LIGHT"]),
             latest__air_temp_c=9.0, latest__light_lux=0, time="02:00",
             history_24h__light_lux_hours_last_24h=80000)
    dry(c["context"], 56.0)
    cases.append(c)

    # --- trap: a request-style situation the model must not over-react to --
    c = case("edge-060", "Moist soil after a big watering (index 90): do nothing",
             ("no_action", "MOISTURE_OK", []), watering__minutes_since_last=40, watering__ml_today=150)
    c["context"]["latest"]["moisture_index"] = 90.0
    c["context"]["moisture_last_2h"] = [62.0, 91.0, 90.6, 90.3, 90.0]
    cases.append(c)

    return [copy.deepcopy(x) for x in cases]
