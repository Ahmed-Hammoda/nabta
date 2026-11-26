# Nabta rules v3: pump, grow light and water tank

Rules v3 = rules v2 (unchanged, see `RULES_v2.md`) + the float switch + the grow light.
Code: `code/rules_v3.py` (the Pi uses the same file). They are the answer key for the fine-tuning data.

## Inputs (one 30-minute reading)
| Input | From | Values |
|---|---|---|
| soil_moisture_index, air_temp_c, humidity_rh, light_lux_now, light_lux_hours_24h | sensors (as in v2) | numbers |
| hour | the reading's time | 0–23 |
| light_on | the controller (is the grow light on now?) | 0 / 1 |
| tank_low | float switch on GPIO 17 | 0 / 1 |

## Decisions
1. **Faults** (v2): SENSOR_ERROR, PUMP_FAULT. A fault blocks the pump.
2. **Levels and alerts** (v2) + **TANK_LOW** when the float switch says the tank is low. In v3 the light
   level is "optimal" from 225,000 lux-h (v2: 285,000); LOW_LIGHT stays below 90,000.
3. **Pump (`water`)**: yes when soil ≤ 70, no fault, and the tank is **not** low.
4. **Grow light (`light`)**:
   - off at night: before 06:00 and from 22:00 (16 h day, 8 h dark);
   - light sensor broken (negative reading): on for the whole day;
   - off once the 24 h light total reaches 225,000 lux-h (about 15 mol/m²/day, where mint grows best;
     changed from 285,000 on 24 Nov 2026, see `WATER_AND_LIGHT_CHECK.md`);
   - already on: stays on (the sensor now sees the LED, so "dark" can't be measured);
   - off: turns on only when it is dark (below 2,000 lux).

## Always in code (never decided by the model)
- No second watering within 3 hours; at most 3 waterings a day; never water on a reading more
  than 45 minutes old; never run the pump when the tank is low.
- One watering = 3 s of pump = about 75 mL (cup test: 25 mL/s; dose from FAO-56, see `WATER_AND_LIGHT_CHECK.md`).
- Relays are switched by the controller; when it stops, the pump and the light are switched off.

## Assumptions to check
- `LED_LUX = 3000` in the v3 simulator (light the strip adds at the plant). Measure it with the
  BH1750 under the strip and change it if it is very different.
- `DARK_LUX = 2000` (our design choice).
