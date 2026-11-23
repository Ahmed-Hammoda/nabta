# Nabta rules v2

These are the rules the Nabta pot uses to decide on watering and alerts. They replace the old rules
(`simulation_phase1/bench/labels.py`) in the app and on the Raspberry Pi. The code version is
`simulation_phase2/code/rules_v2.py`. If this file and the code ever disagree, the code is right.

The language model never decides. It only explains the result of these rules to the user.

---

## 1. Inputs

The rules run on one row of the 30-minute log, plus the row before it.

| Column | Unit | Sensor |
|---|---|---|
| `soil_moisture_index` | 0–100 | Capacitive soil probe through the ADS1115 |
| `air_temp_c` | °C | GY-BME280 |
| `humidity_rh` | % | GY-BME280 |
| `light_lux_now` | lux | BH1750 |
| `light_lux_hours_24h` | lux-hours over the last 24 h | BH1750 |

The soil index must use the new calibration:

```
soil_moisture_index = (16700 − raw) / 8813.2 × 100     (limited to 0–100)
```

Calibrated on the Pi on 17 Nov 2026 (`~/Downloads/soil_calibration.json`: dry_air 16700, water 7886.8):
- **Water:** 7,887 = median of 30 s with the probe in drinking water up to its max line.
- **Dry air:** 16,700 = the **lowest** air reading seen. In air this probe drifts between 16,700 and
  18,150, so using the lowest value makes air always read 0, and a probe out of the soil is caught
  as a broken sensor.

The earlier formula `(16650 − raw) / 9000 × 100` was replaced. The 0–100 scale means the same
(air = 0, water = 100), so the rules below don't change.

---

## 2. Order of the steps

```
new row ──► Step 1: fault check ──► fault?  ── yes ──► do not water, send the fixed fault message
                                      │
                                      no
                                      ▼
                             Step 2: levels ──► Step 3: decision + alerts ──► the model explains
```

---

## 3. Step 1: fault check (new in v2)

This step runs before every decision.

| Fault | Condition | Meaning |
|---|---|---|
| `SENSOR_ERROR` | Soil index outside 0–100 | Impossible reading |
| `SENSOR_ERROR` | Soil index **2 or less** | Reads like dry air: probe out of the soil, or unplugged |
| `SENSOR_ERROR` | Soil **falls more than 15 points** since the previous row (30 min) | Soil can't dry that fast (at most about 3 points per hour) |
| `SENSOR_ERROR` | Temperature outside −10 to 60 °C | Impossible reading |
| `SENSOR_ERROR` | Humidity outside 1 to 100 % | Impossible reading |
| `SENSOR_ERROR` | Light below 0 | Impossible reading |
| `PUMP_FAULT` | Soil **rises more than 10 points** since the previous row, **while the pump was off** | The pump is stuck on, or water is coming from somewhere else |

Exception: a rise just after a reading of 2 or less doesn't count as a pump fault. That is the sensor
coming back, not the pump.

**On any fault:**
- **Do not water.**
- Drop the moisture alerts (`DRY_DANGER`, `TOO_WET`), because the soil reading can't be trusted. Keep the other alerts.
- Send a **fixed message**. The language model is not used.

| Fault | Fixed message |
|---|---|
| `SENSOR_ERROR` | "Sensor problem: {reason}. I am not watering until it is checked." |
| `PUMP_FAULT` | "Pump problem: {reason}. I have stopped watering; please check the pump." |

---

## 4. Step 2: levels

**Soil moisture** (`soil_moisture_index`)

| Level | Range |
|---|---|
| `too_wet` | **98 or above** (v1: above 100) |
| `optimal` | 90 to below 98 |
| `acceptable` | above 70 and below 90 |
| `dry` | above 25, up to 70 |
| `danger_dry` | 25 or below |

**Air temperature** (`air_temp_c`)

| Level | Range |
|---|---|
| `optimal` | 15 to 25 °C |
| `acceptable` | 4 to 36 °C, outside 15–25 |
| `danger` | below 4 or above 36 °C |

**Light** (`light_lux_hours_24h`)

| Level | Range |
|---|---|
| `optimal` | 285,000 or more |
| `acceptable` | 90,000 to 284,999 |
| `low` | below 90,000 |

**Humidity** (`humidity_rh`)

| Level | Range |
|---|---|
| `optimal` | 60 to 70 % |
| `outside_optimal` | anything else |

---

## 5. Step 3: decision and alerts

**Water:** `yes` if `soil_moisture_index` is **70 or below**, otherwise `no`.

**Alerts** (list every one that applies):

| Alert | When | Tip for the user |
|---|---|---|
| `DRY_DANGER` | Soil level is `danger_dry` (25 or below) | The soil is very dry, the plant may wilt |
| `TOO_WET` | Soil level is `too_wet` (98 or above) | The soil is soaked, the roots can rot |
| `HEAT_DANGER` | Temperature above 36 °C | It is too hot, move the pot to the shade |
| `COLD_DANGER` | Temperature below 4 °C | It is too cold, bring the pot inside |
| `LOW_LIGHT` | Light level is `low` | Not enough light today, move the pot to a brighter place |

---

## 6. Changes from v1

| | v1 (old) | v2 (new) | Why |
|---|---|---|---|
| Too wet | above 100 | **98 or above** | The calibrated sensor stops at 100, so the old alert could never fire |
| Fault check | none | **sensor and pump faults block watering** | In the simulation, an unplugged sensor (reading 0) made v1 water 8 times and flood the pot |
| Fault message | — | **fixed text, no language model** | A broken reading must not be explained as if it were real |
| Everything else | — | unchanged | Water at 70 or below; same temperature, light and humidity limits |

Note for the paper: 98 is a **design choice** based on the calibration, not a value from spearmint guidelines.

---

## 7. The same rules as code (pseudocode)

```python
def decide(row, prev, pump_was_on):
    # Step 1: faults
    faults = []
    m = row.soil
    if m < 0 or m > 100 or m <= 2:            faults.append("SENSOR_ERROR")
    if not -10 <= row.temp <= 60:              faults.append("SENSOR_ERROR")
    if not 1 <= row.humidity <= 100:           faults.append("SENSOR_ERROR")
    if row.lux_now < 0 or row.lux_hours < 0:   faults.append("SENSOR_ERROR")
    if prev:
        change = m - prev.soil
        if change < -15:                                        faults.append("SENSOR_ERROR")
        elif change > 10 and not pump_was_on and prev.soil > 2: faults.append("PUMP_FAULT")

    # Step 2 + 3: rules
    alerts = []
    if m <= 25:            alerts.append("DRY_DANGER")
    if m >= 98:            alerts.append("TOO_WET")
    if row.temp > 36:      alerts.append("HEAT_DANGER")
    if row.temp < 4:       alerts.append("COLD_DANGER")
    if row.lux_hours < 90000: alerts.append("LOW_LIGHT")
    water = m <= 70

    if faults:
        water = False
        alerts = [a for a in alerts if a not in ("DRY_DANGER", "TOO_WET")]
        return water, alerts, faults        # send the fixed fault message
    return water, alerts, []                # the language model explains
```

---

## 8. Still to check on the real pot

- **What the probe reads when it is unplugged:** measured on 17 Nov 2026. With the probe connected
  to nothing and in the air, it reads raw 16,900–17,300, which gives index **0.0**. So the
  "2 or below = broken sensor" rule works.
- **Where a freshly watered pot settles.** It should stay below 98. If it often reaches 98, the pump
  runs too long, or the threshold needs to move.
