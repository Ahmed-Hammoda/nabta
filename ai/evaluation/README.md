# Model-selection test set

**Owner:** Ahmed Hamouda

Goal: find the **smallest language model** that can run Nabta's decisions correctly. The board (and how much RAM it needs) is chosen after that.

## How it works

```
real sensor data ──► convert to Nabta's fields ──► scenarios ──► rules engine labels them ──► testset.jsonl
                     (+ simulate tank and mL)                    (the answer key)
hand-made edge cases ─────────────────────────────────────────►
```

Each line of `testset.jsonl` is one scenario:

| Field | Content |
|---|---|
| `id` | `data-0123` (from the real trace) or `edge-012` (hand-made) |
| `source` | `dataset` or `edge` |
| `description` | What the situation is |
| `context` | **What the model receives**: latest readings, last 2 h of moisture, 24 h history, watering state |
| `expected` | **The correct answer** from `rules.py`: action, mL, reason code, alerts |

The model gets the system prompt in [`../prompts/decision-v1.md`](../prompts/decision-v1.md) and the `context` as JSON, and must answer with the same structure as `expected`, plus an explanation.

## Files

| File | Role |
|---|---|
| [`rules.py`](rules.py) | Reference rules engine: computes the correct decision from the spearmint plant profile |
| [`config.json`](config.json) | Evaluation settings not in the plant profile (soak time, mL per index point, tank simulation) |
| [`edge_cases.py`](edge_cases.py) | 30 hand-made situations: sensor faults, empty tank, daily cap, heat, cold, waterlogging, combinations |
| [`build_testset.py`](build_testset.py) | Converts a sensor dataset, labels it, samples it and writes `testset.jsonl` |
| [`data/`](data/) | The source dataset, its credit and the conversion choices |
| [`testset.jsonl`](testset.jsonl) | **The test set: 124 scenarios** (94 from the dataset, 30 edge cases) |

## Current test set

Built with:

```bash
python build_testset.py data/Edge_IoT_Predictive_Irrigation_Dataset.xlsx --moisture-as-index --light-scale 20
```

| Correct decision | Scenarios |
|---|---|
| MOISTURE_OK (no watering) | 60 |
| DRY_BELOW_MIN (water) | 33 |
| RESERVOIR_EMPTY (dry, tank empty) | 24 |
| SENSOR_FAULT | 5 |
| SOAKING_WAIT | 1 |
| DAILY_LIMIT_REACHED | 1 |

Alerts: HEAT_STRESS 50, RESERVOIR_EMPTY 50, SENSOR_FAULT 5, COLD_STRESS 2, LOW_LIGHT 2, and 1 each of DRY_STRESS, WATERLOGGED, HEAT_CRITICAL, COLD_CRITICAL, HUMIDITY_HIGH.

Rare situations (soak wait, daily cap, cold, waterlogging) have only one or two cases each, so a model's mistakes there should be read case by case, not as a percentage.

Standard library only; `openpyxl` is needed only if the source is an `.xlsx` file.

## Fields the model receives

| Field | Hardware | From the dataset? |
|---|---|---|
| `moisture_index` | Capacitive sensor + ADS1115 | Yes, rescaled to 0–100 |
| `air_temp_c` | SHT31 | Yes |
| `humidity_rh` | SHT31 | Yes |
| `light_lux` | BH1750 | Yes |
| `tank_ok` | Float switch | **Simulated**: 1 L tank, emptied by each watering, refilled 24 h after running low |
| `watering.*` (mL) | YF-S401 flow sensor | **Simulated**: each pump reading in the dataset = 120 mL |
| `time` | Pi clock | Yes |

### Moisture index from the dataset
For the current dataset the moisture column is already a 0–100 % on which our thresholds work, so it is used directly (`--moisture-as-index`). For a raw sensor dataset, the script rescales it:
- **0** = the driest reading (1st percentile).
- **100** = the typical reading right after the dataset's pump turned on (the container-capacity point in Yassine's calibration method).
- The script detects whether the sensor reads higher or lower when the soil is wetter.

## Run it

```bash
cd ai/evaluation
python build_testset.py data/<source file>.csv      # full test set
python build_testset.py --edge-only                 # only the 30 edge cases
python build_testset.py data/<file>.csv --per-group 20   # more scenarios per situation type
```

If a column is not detected, name it: `--col-moisture "Soil Moisture"`, `--col-light "LDR"`, etc. If light is not in lux, use `--light-scale`.

The script stops with an error if any edge case disagrees with the rules engine, so it also tests `rules.py`.

## How models will be scored (next step)

| Measure | Rule |
|---|---|
| Valid JSON | The answer parses and has all fields |
| Decision | `action` and `reason_code` both match |
| Dose | `ml` within ±10 mL of the expected value |
| Alerts | Precision and recall against the expected list |
| Safety errors | Watering when the answer is not `water` (counted separately; the most serious error) |
| Speed | Seconds per answer on the test machine |

## Limits

- The source dataset is not from spearmint. That is fine for this test: the model has to apply **spearmint rules** to the numbers it receives. Real spearmint data comes from the calibration week (2–8 Nov) and will be used to confirm the chosen model.
- The rules engine is the reference for the **test**. During the study, the hard safety rules still run in code; the model is checked here so we know it gives correct decisions and explanations.
