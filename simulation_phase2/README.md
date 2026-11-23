# Simulation phase 2: 30 days of the Nabta pot, with the new rules

Starts from the real sensor test of 15 Nov 2026 and the new calibration
(`index = (16650 - raw) / 9000 x 100`, dry air = 0, water = 100).

| Folder | Content |
|---|---|
| `real_sensor_test/` | qwen3.5:0.8b explaining the 17 rows of the real 30-min log (first check on real data, old rules) |
| `draft_v1/` | First 30-day simulation with the old rules. Superseded: the unplugged sensor flooded the pot. |
| `code/rules_v2.py` | **Rules v2**: TOO_WET at 98+, and a sensor/pump fault check before every decision |
| `code/simulate_30days_v2.py` | Builds the dataset (seed 2026) |
| `dataset/` | **The phase 2 dataset**: 1,440 rows (sensor file + answer key). See `dataset/README.md`. |
| `code/sim_bench_v2.py` | Tests the models on the dataset |
| `results/` | Model results and `summary.txt` / `summary.csv` |
| `code/think_subset.py` | Thinking-on test on 82 of the 255 cases; results in `results/think_subset/` |
| `code/make_train_data.py` | Builds the fine-tuning data |
| `train_data/` | **Fine-tuning data** for qwen3.5:0.8b: 5,940 train + 660 val rows. See `train_data/README.md`. |

## Tests

- **Test A, "AI decides":** the model gets only the raw sensor numbers and gives water + alerts.
  6 prompts: v0 (original), v3 (JSON schema + 4 examples), p1 (14 examples), p2 (water + alerts only,
  14 examples), p3 (7 true/false checks first), p4 (p3 + 8 examples), p5 (v3 + broken-sensor rule
  and example). 5 models x 7 prompts = 35 runs. Note: v0 and v3 are never told about a broken sensor.
- Test B (rules decide, model explains) was dropped from this phase; the one old run is in `results/old_test_B/`.

## Result of Test A (255 cases)

Baselines: "always no water" = 83.7 % water; "never alert + never water" = 23.7 % both correct.

| Model + prompt | Both correct | Water | Alerts | Overwater (of 205) | Missed (of 40) | Broken sensor watered |
|---|---|---|---|---|---|---|
| qwen3:1.7b v3 | 63.3 % | 86.1 % | 68.6 % | 2 | 32 | 8/10 |
| qwen3:1.7b p1 | 53.9 % | 84.1 % | 57.1 % | 4 | 35 | 0/10 |
| lfm3:1.7b v3 | 49.0 % | **98.4 %** | 49.8 % | 1 | 3 | 8/10 |
| lfm3:1.7b p5 | 47.8 % | 91.8 % | 49.4 % | 2 | 18 | 0/10 |

- qwen3:1.7b scores well on water only because it almost never waters (83.7 % = "always no").
- lfm3:1.7b v3 is the only model that really decides watering, but it waters a broken sensor.
- 25 of 35 runs score below the 23.7 % "do nothing" baseline.
- No combination is reliable enough to run the pot alone. Full ranking: `results/summary.txt`.
- Times are laptop times; the Pi 4 is still to be timed.

Models: qwen3.5:0.8b (phase 1 choice), lfm3:1.7b, granite4:1b-h, qwen3:1.7b, llama3.2:1b.
All fit a Raspberry Pi 4 with 4 GB (1.1–1.6 GB each). Thinking is turned off for every model.

Cases: 255 = up to 20 rows per scenario + all 10 fault rows. Times are measured on the laptop, not the Pi.

The code imports the phase 1 modules from `../simulation_phase1/bench` (labels, explain_bench, run_bench).
