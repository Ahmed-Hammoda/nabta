# Nabta data format (version 3)

What the Pi saves, what goes into the model, and what comes out. The same format is used by the
simulator (`simulation_phase2/code/simulate_30days_v3.py`) and the fine-tuning data
(`simulation_phase2/code/make_train_data.py`), so real data and simulated data can be mixed.

## 1. The model: input and output

**System prompt** (fixed, the same text in training and on the Pi):
> You are Nabta, the controller of a smart pot growing spearmint. You receive one 30-minute sensor
> reading as JSON. Decide the levels, faults and alerts, whether to water (pump) and whether the grow
> light is on. Answer with JSON only.

**Input** (one 30-minute reading, JSON, these 8 keys in this order):

| Key | Unit | Source | Notes |
|---|---|---|---|
| `soil_moisture_index` | 0–100 (1 decimal) | soil probe + ADS1115 | `(16700 − raw) / (16700 − 7886.8) × 100`, limited to 0–100 |
| `air_temp_c` | °C (2 decimals) | BME280 | |
| `humidity_rh` | % (1 decimal) | BME280 | |
| `light_lux_now` | lux (1 decimal) | BH1750 | 30-min average; includes the grow light when it is on |
| `light_lux_hours_24h` | lux·h (2 decimals) | logger | sum of lux × hours over the last 24 h |
| `hour` | 0–23 | timestamp | local time (Africa/Tunis) |
| `light_on` | 0 / 1 | controller | grow light state when the reading was taken |
| `tank_low` | 0 / 1 | float switch, GPIO 17 | majority of the last minute; 0 if the float is not set up |

**Output** (JSON, these 8 keys):

| Key | Values |
|---|---|
| `moisture_level` | danger_dry, dry, acceptable, optimal, too_wet |
| `temp_level` | danger, acceptable, optimal |
| `light_level` | low, acceptable, optimal |
| `humidity_level` | optimal, outside_optimal |
| `faults` | list: SENSOR_ERROR, PUMP_FAULT |
| `alerts` | list: DRY_DANGER, TOO_WET, HEAT_DANGER, COLD_DANGER, LOW_LIGHT, TANK_LOW |
| `water` | yes / no (the pump) |
| `light` | on / off (the grow light) |

The correct answers come from rules v3 (`RULES_v3.md`).

**After the decision, code always checks** (the model can't override these):
1. no second watering within 3 hours;
2. at most 3 waterings a day;
3. never water on a reading more than 45 minutes old;
4. never run the pump when the tank is low (`BLOCK_WHEN_TANK_LOW`).

## 2. Files saved on the Pi (`~/nabta/logs/`)

One folder per month (`YYYY-MM/`). Restarts append to the same files; new columns are added to an
older file automatically (old rows get empty cells).

| File | One row / line every | Use |
|---|---|---|
| `raw_log.csv` | 10 s | the real sensor curves: drying speed, watering jumps, light, LED effect → tune the simulator |
| `log_30min.csv` | 30 min | the averaged reading the decision uses |
| `decisions.csv` | 30 min | readable table: decision, actions, message |
| **`model_io.jsonl`** | 30 min | **the model's exact input + the rules' answer + what the Pi did → training rows** |
| `../events.csv` | each start/stop | gaps (Pi off) |

**raw_log.csv columns:** `timestamp, soil_raw, soil_moisture_index, air_temp_c, humidity_rh, light_lux_now,
light_lux_hours_24h, float_raw, tank_low`

**log_30min.csv columns:** `timestamp, soil_moisture_index, air_temp_c, humidity_rh, light_lux_now,
light_lux_hours_24h, tank_low, samples` (`samples` = readings averaged, 180 for a full 30 min)

**decisions.csv columns:** `timestamp, soil_moisture_index, air_temp_c, humidity_rh, light_lux_now,
light_lux_hours_24h, hour, tank_low, light_before, moisture_level, temp_level, light_level,
humidity_level, faults, alerts, water_decision, pump_action, light_decision, light_action, message,
message_source, model_seconds`

**model_io.jsonl line** (example):
```json
{"v": 3, "timestamp": "2026-11-24T10:00:01+01:00", "decider": "rules",
 "input": {"soil_moisture_index": 55.0, "air_temp_c": 22.0, "humidity_rh": 55.0, "light_lux_now": 50.0,
           "light_lux_hours_24h": 40000.0, "hour": 10, "light_on": 0, "tank_low": 0},
 "tank_known": true,
 "rules": {"moisture_level": "dry", "temp_level": "optimal", "light_level": "low",
           "humidity_level": "outside_optimal", "faults": [], "alerts": ["LOW_LIGHT"],
           "water": "yes", "light": "on"},
 "fault_reason": "",
 "actions": {"pump": "WATERED 150 mL", "light": "LIGHT ON", "pump_seconds": 8,
             "pump_enabled": true, "light_enabled": true},
 "samples": "180", "message_source": "code (model off)"}
```
- `input` + `rules` = one training example (input → correct output), already in the model's format.
- `actions` = what really happened (for the simulator: when the pump ran and for how long, when the
  LED was on).
- `decider` changes to `"model"` when the fine-tuned model makes the decision; then the line will also
  hold the model's own answer, so it can be compared with the rules on real data.

## 3. Turning the saved data into training rows

Each `model_io.jsonl` line becomes:
```
{"messages": [{"role": "system", "content": <system prompt>},
              {"role": "user", "content": json.dumps(line["input"])},
              {"role": "assistant", "content": json.dumps(line["rules"])}]}
```
Use only lines with `"v": 3`. Lines with a fault are useful too (the model must learn to say
SENSOR_ERROR). Keep real rows separate from simulated rows in testing, so we can see how the model does
on real data.
