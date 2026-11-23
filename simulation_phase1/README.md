# Simulation phase 1: which small model, and in which role?

Test data: the public Mendeley sensor trace, plus synthetic coverage and threshold-boundary cases.
Rules: `bench/labels.py` (moisture "too wet" above 100). **Frozen**: these are the results in the paper.

**Result:** no small model decides reliably from raw numbers (best: qwen3.5:0.8b, 83 % on watering).
**qwen3.5:0.8b** was chosen as the explainer: with prompt e3, all 184 explanations agreed with the rules,
and 96 % of 240 chat answers passed every check.

| What | Where |
|---|---|
| First dataset and first test (qwen2.5 0.5B / 1.5B) | `dataset_A_numbers.csv`, `dataset_B_numbers_levels.csv`, `answer_key.csv`, `test_model.py`, `results_qwen2.5_*.csv`, `images/` |
| 184-case benchmark: models deciding | `bench/run_bench.py`, `bench/testset.jsonl`, `bench/results/`, `bench/summary.csv` |
| Thinking mode | `bench/results_think/` |
| Explanations (prompts e1–e3) | `bench/explain_bench.py`, `bench/results_explain/` |
| Chat | `bench/chat_bench.py`, `bench/chat_v3.py`, `bench/results_chat/` |
| Full write-up | `bench/README.md`, `report/Nabta_model_tests.pdf` |

Next phase: `../simulation_phase2`.
