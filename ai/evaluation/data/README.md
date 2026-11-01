# Source dataset

**File:** `Edge_IoT_Predictive_Irrigation_Dataset.xlsx`

**Source:** *Environmental Sensor Dataset for LSTM-Based Predictive Irrigation in Smart Home Gardening Using Edge IoT*, Mendeley Data, version 1 (June 2026). DOI: [10.17632/jtsyb593fy.1](https://data.mendeley.com/datasets/jtsyb593fy/1)

**License:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit the dataset authors in the report.

## Content

960 readings every 30 minutes over 20 days (1–20 April 2026).

| Column | Range | Used as |
|---|---|---|
| `Timestamp` | 2026-04-01 00:00 → 2026-04-20 23:30 | `time` |
| `Temperature_C` | 25 to 35 °C | `air_temp_c` |
| `Humidity_pct` | 61 to 88 % | `humidity_rh` |
| `Soil_Moisture_pct` | 46.6 to 85 % | `moisture_index`, used directly |
| `Light_Intensity` | 0 to 949 (raw, not lux) | `light_lux` × 20 |
| `Pump_Status` | 0/1, 28 readings on | watering history, 120 mL per reading |

## Conversion choices

- **Moisture used as-is.** The dataset's own controller waters at about 55–62 % and refills to about 85 %, which matches the spearmint rules (water below 60, refill to 85–90). Using the % directly keeps the trace realistic for our thresholds.
- **Light × 20.** The column is a raw sensor value with daylight from 06:30 to 18:00. Scaling by 20 gives a peak of about 19,000 lux and about 138,000 lux-hours per day, a bright window just above the low-light warning (120,000).
- **Tank simulated.** 1 L tank, emptied by the waterings, refilled 24 h after running low.

## Things to know

- The climate is warm and humid (25–35 °C), unlike a Tunis room in November, so heat alerts are frequent and cold alerts never happen in this data. The edge cases cover the cold.
- The data looks very regular: the minimum temperature is exactly 25.0 °C every day and the daily light totals differ by less than 3 %. It may be partly simulated. That is fine for testing whether a model applies the rules, but the report should not present it as measured spearmint data.
- Moisture never drops below 46 %, so dry-stress and waterlogging situations only come from the edge cases.
