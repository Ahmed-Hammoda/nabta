# Training data for fine-tuning (first model: qwen3.5:0.8b), version 3

Built by `../code/make_train_data.py` (fixed seeds, so it can be rebuilt exactly).

## Task the model learns
- **Input:** one 30-minute reading, as JSON:
  `{"soil_moisture_index": 24.5, "air_temp_c": 17.66, "humidity_rh": 77.4, "light_lux_now": 0.1, "light_lux_hours_24h": 379081.37, "hour": 1, "light_on": 0, "tank_low": 1}`
  - `hour`: 0–23, local time of the reading
  - `light_on`: 1 if the grow light is on right now (the light sensor also sees the LED)
  - `tank_low`: 1 if the float switch says the water tank is almost empty
- **Output:** JSON with 8 keys, in this order:
  `moisture_level, temp_level, light_level, humidity_level, faults, alerts, water, light`
  - `water` = the pump decision (yes/no), `light` = the grow light (on/off)
  - alerts: DRY_DANGER, TOO_WET, HEAT_DANGER, COLD_DANGER, LOW_LIGHT, **TANK_LOW**
- **System prompt:** one short fixed sentence (in every example). The Pi must send the same text.
- **No reasoning in the answers:** train and run the model with **thinking off**.
- **Answer key:** rules v3 (`../code/rules_v3.py`, see `../RULES_v3.md`), one row, no previous row.
  On the Pi the three pump safety rules (3 h wait, 3 a day, no old readings) stay in code after the
  model's decision.

## Files
| File | Rows | Use |
|---|---|---|
| `train.jsonl` | 6,210 | Training, chat format `{"messages": [system, user, assistant]}` |
| `val.jsonl` | 690 | Checking during training (not trained on) |
| `train.csv`, `val.csv` | same | The same rows as a table, to read |
| `stats.txt` | | Counts per part, water, light, alerts, faults, levels |
| `colab/nabta_colab_upload.zip` | | What you upload to Colab (built by `../finetune/make_replay_data.py --mix-only`) |

## Where the rows come from
| Part | Rows | What |
|---|---|---|
| realistic | about 2,400 | The v3 30-day simulator with **other seeds** (2027–2029), grow light and tank included; rare rows (water, faults, alerts, light switches) kept first |
| uniform | about 2,400 | Random values over every input's full range (hour 0–23, light on 40 %, tank low 10 %) |
| boundary | about 1,800 | On and just around every limit: soil 2/25/70/90/98, temp 4/15/25/36, humidity 60/70, light 90,000/225,000, dark 2,000 lux, hours 6 and 22, tank low with dry soil |
| fault | about 300 | Broken sensor: soil 2 or below, impossible temperature or humidity, negative light |

Rows equal to a row of the v3 test set (`../dataset_v3`) are removed, so that test stays unseen.
