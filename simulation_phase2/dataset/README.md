# Simulation phase 2 dataset: 30-day log with rules v2 (dummy data)

Simulated data for testing the models. It is **not measured**. It uses the same weather, scenarios and
random seed as `../draft_v1`, but the system follows the **v2 rules**:

| Change from v1 | Why |
|---|---|
| TOO_WET at 98 or above (was: above 100) | The calibrated sensor stops at 100 (probe in water), so the old alert could never fire. 98 is a design choice, not a spearmint guideline value. |
| Fault check before every decision (`../code/rules_v2.py`) | In v1, the unplugged sensor (reads 0) made the rules water 8 times and flood the pot |
| Pump adds about 22 points (was about 26) | A normal watering now ends near 92, below the TOO_WET line |
| A stuck relay fills at pump speed | So the fault check can see it |

Generator: `../code/simulate_30days_v2.py` (seed 2026).

## Files

| File | Rows | Content |
|---|---|---|
| `sim_sensor_30days.csv` | 1,440 | Same columns as the real 30-min log: what the sensors send |
| `sim_key_30days.csv` | 1,440 | Scenario, true soil moisture, what the pump did, the v2 decision, and any fault with its reason |

One row every 30 min, 16 Nov 00:00 to 15 Dec 23:30.

## The fault check

| Fault | When | Then |
|---|---|---|
| SENSOR_ERROR | Soil reads 2 or less (like dry air), soil falls more than 15 points in 30 min, or temperature, humidity or light is impossible | No watering. Fixed message, no language model. |
| PUMP_FAULT | Soil rises more than 10 points in 30 min while the pump was off | No watering. Fixed message, no language model. |

"Soil reads 2 or less" is based on the real calibration test: dry air reads 0. What the probe reads when
it is **unplugged** has not been measured yet, so the "falls more than 15 points" test is the backup.

## Scenarios (same as v1)

| Dates | Scenario |
|---|---|
| 16–18 Nov | Indoor shelf, like the real test |
| 19–23 Nov | Balcony, normal |
| 24–25 Nov | Rain: soil soaked, TOO_WET |
| 26–28 Nov | Heat wave, 37–40 °C (stress test) |
| 26 Nov 14:00 – 1 Dec 10:00 | Water tank empty: soil falls below 25 |
| 2–4 Dec | Cold snap, nights 1.5–3 °C (stress test) |
| 5 Dec 11:05–13:35 | Relay stuck on: PUMP_FAULT, then TOO_WET |
| 7 Dec 09:00–13:00 | Sensor unplugged: SENSOR_ERROR, watering blocked |
| 8–11 Dec | Indoors by a window, low light |
| 12–15 Dec | Balcony, normal |

## Decisions in the key

| Water | Rows |
|---|---|
| yes | 233 (219 of them during the empty tank) |
| no | 1,207 |

| Alert or fault | Rows |
|---|---|
| LOW_LIGHT | 633 |
| DRY_DANGER | 111 |
| TOO_WET | 50 |
| COLD_DANGER | 45 |
| HEAT_DANGER | 39 |
| SENSOR_ERROR | 8 |
| PUMP_FAULT | 2 |

## Limits

- **Water "yes" is rare** (16 %). A model that always says "no" would score 84 % on water, so report that baseline next to every result.
- **Rows close in time are near-copies** of each other, so 1,440 rows are not 1,440 independent cases.
- **The key assumes the rules run the pump.** If a model made the decision instead, the soil would follow a different path.
