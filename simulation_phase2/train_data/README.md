# Training data for fine-tuning (first model: qwen3.5:0.8b)

Built by `../code/make_train_data.py` (fixed seeds, so it can be rebuilt exactly).

## Task the model learns
- **Input:** one 30-minute reading, as JSON with numbers:
  `{"soil_moisture_index": 12.4, "air_temp_c": 18.4, "humidity_rh": 19.0, "light_lux_now": 3378.0, "light_lux_hours_24h": 430.84}`
- **Output:** JSON with 7 keys, in this order:
  `moisture_level, temp_level, light_level, humidity_level, faults, alerts, water`
- **System prompt:** one short fixed sentence (in every example). The Pi must send the same text.
- **No reasoning in the answers:** train and run the model with **thinking off**.
- **Decision only:** the data does not teach the message to the user. Whether the trained model can
  still write good explanations must be tested after training.
- **Answer key:** rules v2 (`rules_v2.decide`, one row, no previous row). The rules only label the
  data; on the Pi the trained model decides alone.

## Files
| File | Rows | Use |
|---|---|---|
| `train.jsonl` | 5,940 | Training, chat format `{"messages": [system, user, assistant]}` |
| `val.jsonl` | 660 | Checking during training (not trained on) |
| `train.csv`, `val.csv` | same | The same rows as a table, to read |
| `stats.txt` | | Counts per part, water, alerts, faults, levels |

## Where the rows come from
| Part | Rows | What |
|---|---|---|
| realistic | about 2,400 | The 30-day simulator with **other seeds** (2027–2029); rare rows (needs water, alerts, faults) kept first |
| uniform | about 2,400 | Random values over every sensor's full range |
| boundary | about 1,500 | Values on and just around every limit: soil 2/25/70/90/98, temp 4/15/25/36, humidity 60/70, light 90,000/285,000 |
| fault | 300 | Broken sensor: soil 2 or below, impossible temperature or humidity, negative light |

Balance (train): water yes 3,005 / no 2,935; LOW_LIGHT 44 %; every alert and level has hundreds of rows.

## Kept apart for testing
- The **30-day dataset** (`../dataset`, seed 2026) is not used. No training row has the same 5 numbers
  as a test row (checked; the test files' checksums did not change).
- The **real sensor log** of 15 Nov 2026 is not used either; it is a second test.

## Limits (say these in the paper)
- The training data is simulated. The realistic part uses the same scenario plan as the test set,
  with different weather, so the 30-day test is "unseen rows, same kind of data". The real log is the
  harder test.
- `val.jsonl` is a random split of rows, so neighbouring 30-minute rows can be on both sides: the
  val score will look better than the real one. Judge the model on the 30-day test and the real log.
- The 17-row real log is the only fully independent test, and it is small.
- The fault part assumes an unplugged probe reads 2 or below. This is not measured yet; if the real
  value is different, rebuild the data and train again.
- One row only: the model cannot learn the stuck-pump or "soil fell 15 points" faults, which need the
  previous row.
- If the rules change (for example the 98 limit), rebuild the data and train again.
