# Simulation phase 2, draft v1: 30-day log with the old rules (dummy data)

> Superseded by `../dataset` (rules v2 + fault check). Kept so it can be reproduced.

Simulated data for testing the models. It is **not measured**: it copies the format and the indoor
values of the real test of 15 Nov 2026 (`log_30min.csv`), and adds 30 days of scenarios.

Generator: `simulate_30days_v1.py` in this folder (rules v1 = `simulation_phase1/bench/labels.py`) (seed 2026, so the same file comes out every time).

## Files

| File | Rows | Content |
|---|---|---|
| `sim_sensor_30days.csv` | 1,440 | Same columns as the real 30-min log: what the sensors send |
| `sim_key_30days.csv` | 1,440 | Scenario of each row, true soil moisture, what the pump did, and the rule decision (`labels.py`) |

One row every 30 min, 16 Nov 00:00 to 15 Dec 23:30. Each row is the average of the previous 30 minutes,
like the real logger. `light_lux_hours_24h` is the light summed over the last 24 h.

## Scenarios

| Dates | Scenario | What happens |
|---|---|---|
| 16–18 Nov | Indoor shelf | Like the real test: 23–24 °C, 58–63 % RH, under 75 lux. LOW_LIGHT all day |
| 19–23 Nov | Balcony, normal | Tunis late November: 11–20 °C, sun up to 55,000 lux, one cloudy day |
| 24–25 Nov | Rain | Rain on the pot: soil soaked (sensor at 100), 90–98 % RH, little light |
| 26–28 Nov | Heat wave (stress test) | 37–40 °C, 15–45 % RH: HEAT_DANGER, fast drying |
| 26 Nov 14:00 – 1 Dec 10:00 | Water tank empty | The rules say water but the pump has no water: soil falls below 25 (DRY_DANGER) |
| 2–4 Dec | Cold snap (stress test) | Nights 1.5–3 °C: COLD_DANGER |
| 5 Dec 11:05–13:35 | Relay stuck on | The pump runs without stopping: the pot floods |
| 7 Dec 09:00–13:00 | Sensor unplugged | The soil reads 0, so the rules water 8 times and the pot becomes waterlogged |
| 8–11 Dec | Indoors by a window | 23–25 °C, light up to 4,500 lux: still LOW_LIGHT |
| 12–15 Dec | Balcony, normal | Back outside |

## Rule decisions in the key

| Water | Rows |
|---|---|
| yes | 238 |
| no | 1,202 |

| Alert | Rows |
|---|---|
| LOW_LIGHT | 633 |
| DRY_DANGER | 119 |
| HEAT_DANGER | 39 |
| COLD_DANGER | 45 |
| TOO_WET | 0 |

## Known limits

- **TOO_WET never fires:** the rule needs moisture above 100, but the sensor index stops at 100.
- **The unplugged-sensor rows** (7 Dec) are labelled "water: yes" because that is what the rules
  decide from a reading of 0. The key's `true_soil_moisture` column shows the soil was in fact wet.
- **Heat wave and cold snap** are extreme on purpose, to test the danger alerts. They are not normal
  Tunis weather in November–December.
