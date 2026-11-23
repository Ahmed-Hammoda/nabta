# Nabta: can a 0.5B or 1.5B model make the watering decision?

## Short answer

No. Neither model is good enough to decide watering or raise alerts, even with the best prompt
we could build. The best 1.5B setup reaches 97 % on the water decision only because the code already
gives it the answer ("dry"). It still waters 6 pots that are not dry and misses most alerts.
Five lines of Python get 100 % in microseconds.

## Test set (`testset.jsonl`, 184 cases)

| Part | Cases | Why |
|---|---|---|
| Real rows from the Mendeley trace | 100 | Balanced on water / temperature / light |
| Coverage | 50 | Every moisture level × every temperature zone (cold, cool, optimal, warm, heat) |
| Boundaries | 34 | Exact thresholds: 25, 70, 70.1, 90, 100.1, 4, 36, 36.1, 90000, 285000, 60, 70... |

Water: 97 yes / 87 no. Labels come from `labels.py`, which reproduces the original
`answer_key.csv` on all 912 rows.

## Prompt designs tested (`run_bench.py`)

Each design changes one thing from the previous one.

| Config | What changes |
|---|---|
| v0_baseline | The first prompt from `test_model.py`, values sent as text |
| v1_numbers | Values sent as real numbers |
| v2_schema | JSON schema (Ollama structured outputs): allowed values only, answer order levels → alerts → water |
| v3_fewshot | + 4 solved examples |
| v4_reasoning | + a "reasoning" field written before the answer |
| v5_levels_rules | Code gives the levels, rules are written on the levels, model only outputs alerts + water |

Dataset A = numbers only, dataset B = numbers + levels computed by code.
Settings: temperature 0, fixed seed, so results are repeatable.

## Results (water decision)

| Setup | 0.5B | 1.5B |
|---|---|---|
| Always say "no" (reference) | 47 % | 47 % |
| Always say "yes" (reference) | 53 % | 53 % |
| Best prompt, numbers only (A) | 54 % (says "yes" 90 % of the time) | 57 % (v3) |
| Best prompt, numbers + levels (B) | 53 % (says "yes" 100 %) | **97 %** (v5) |
| Rule code `if moisture <= 70` | 100 % | 100 % |

Full table with 95 % intervals: `summary.csv` (`python report.py`).

## What this shows

1. **0.5B:** across 11 setups it is never better than a coin. With most prompts it gives the same
   answer for every pot (always "yes" or always "no").
2. **1.5B with numbers:** it cannot compare a number with a threshold. Example from v4:
   `"moisture 61.9 <= 70 -> acceptable ... water no because moisture > 70"`. It writes the right
   comparison, then decides the opposite.
3. **1.5B with levels (best case, v5):** 97 % water, 0 missed waterings, but:
   - **6 dangerous waterings** (soil already acceptable, optimal or too wet),
   - **alerts only 64 % correct**: it missed 44 of 49 low-light alerts, 9 of 11 cold alerts,
     8 of 12 dry-danger and 8 of 12 too-wet alerts, even though the level was in the input.
   - It adds nothing the code does not already know: the code had to compute "dry" first.
4. **Format matters more than wording** for small models: the JSON schema + answer order + examples
   moved 1.5B from 47 % to 94 %, but only when the decision was reduced to copying a word.

## Other families: gemma3:1b and qwen3.5:0.8b (thinking off)

| Setup | gemma3:1b | qwen3.5:0.8b |
|---|---|---|
| Original prompt, numbers only (v0 A) | 47 % (always "no") | **83 %** |
| Best prompt, numbers + levels | 54 % (almost always "yes") | **100 %** (v5) |
| Alerts, best setup | 60 % | 91 % |
| Danger alerts (heat, cold, dry, too wet), best setup | 5 % | 55 % |

- **gemma3:1b** behaves like qwen2.5:0.5b: the same answer for every pot.
- **qwen3.5:0.8b** (newer generation) is much better than qwen2.5:1.5b although it is half the size.
  With levels from code it got every water decision right (v5) and 90 % of cases fully correct (v3/v5).
  It still missed 8 of 11 heat-danger and 4 of 11 cold-danger alerts and invented 11 alerts,
  so it cannot be trusted to raise alerts on its own.
- **Thinking mode (qwen3.5 default):** on a test case it looped ("Wait, this is confusing... if it's
  64.2, that's not dry") until it hit the 4096-token context, about 25 s, and gave no answer.
  With 8192 context and 7000 tokens allowed (20-case sample each, `results_think/`): it answered
  1 of 20 with numbers only (53 s per case) and 1 of 20 with levels (62 s per case). Thinking must stay off.

## Phase 1 validation: explanations (qwen3.5:0.8b, thinking off)

The code's decision and alerts are given to the model; it writes 1-2 sentences (`explain_bench.py`).

| Check | Pass rule | e1 instructions | e2 + 4 examples | e3 tips from code + one-alert examples |
|---|---|---|---|---|
| Same action as the code | 100 % | 70.1 % | 98.4 % | **100 %** |
| No invented numbers | 100 % | 98.9 % | 100 % | **100 %** |
| Moisture value quoted | — | 37.0 % | 100 % | 100 % |
| Every alert mentioned | 95 % | 92.9 % | 100 % | **100 %** |
| No fake alert | 95 % | 64.7 % | 89.7 % | **99.5 %** |
| Short (2 sentences, 40 words) | 95 % | 52.2 % | 97.8 % | **98.4 %** |
| Time per explanation | — | 0.47 s | 0.38 s | 0.33 s |

- **e1** often contradicts the code ("the pot is dry, you should water it" when the decision is no).
- **e2** copies its examples: after "very dry" it adds "too hot... more light" even at 11 °C.
- **e3** passes every automatic check. Manual reading found 2 real errors out of 184:
  one fake low-light warning, and one sentence claiming "I am also moving the pot to the shade"
  (the system cannot move the pot). The 3 "too long" cases have 3 alerts at once.
- Human check (`results_explain/qwen3.5_0.8b__e3_human_check.csv`, 30 random explanations): passed.
- **Phase 1 verdict: qwen3.5:0.8b passes the explanation role with prompt e3.**

## Phase 2 validation: chat (qwen3.5:0.8b, thinking off)

40 questions in 5 groups (status, why, forcing, off-topic, unknown facts) × 6 plant situations = 240 answers
(`chat_bench.py`).

| Check | Pass rule | v1 fixed examples | v2 examples built from current facts |
|---|---|---|---|
| No contradiction of the decision | 100 % | 94.2 % | **100 %** |
| No invented numbers | 100 % | 89.2 % | 99.6 % |
| No false promise (water, move, disable...) | 100 % | 100 % | **100 %** |
| Question-specific check | 95 % | 84.6 % | 85.8 % |
| Short (3 sentences, 60 words) | 95 % | 100 % | 100 % |
| No fake alert | 95 % | 96.7 % | 98.8 % |

- v1 copied numbers from its examples ("the soil is dry at 64.2" when the real value was 82.6).
- v2 fixed that, and passed all 48 "forcing" questions (never promised to water, move the pot or disable limits).
- **v2 still fails.** Reading the 38 failed answers:
  - 8 serious: invented facts ("yesterday's temperature was 21.5 °C", "about 20 cm tall"),
    1 "No" to "Is the plant getting water today?" while it was watering, 2 missed alerts on "Should I worry?".
  - 16 unhelpful: it answers "I don't know" to "Explain your decision" or "Are you watering right now?"
    (it over-uses the "I don't know" example).
  - 4 answered an off-topic request (translated "hello").
  - 8 acceptable answers that the check was too strict about ("I don't know" to "What is 12 times 7?").
- **Phase 2 verdict (free chat): not passed.**

### v3: router + code templates + safety net + more facts (`chat_v3.py`)

1. The model classifies the question (status / why / forcing / offtopic / unknown).
2. Forcing, off-topic and unknown questions get a fixed safe sentence written by code.
3. The model writes only status and why answers, with examples built from the current facts.
4. A safety net (facts + question only, never the answer key) replaces a bad answer with a template.
5. FACTS now also contain yesterday's temperature, today's waterings and the next check time.
6. v3.1 adds a yes/no "can this be answered from the FACTS?" check before writing.

| Version | All checks passed | Status | Why | Forcing | Off-topic | Unknown |
|---|---|---|---|---|---|---|
| v1 | 178 / 240 (74 %) | 26 | 34 | 40 | 41 | 37 |
| v2 | 203 / 240 (85 %) | 42 | 34 | 48 | 37 | 42 |
| v3 | 225 / 240 (94 %) | 48 | 48 | 48 | 48 | 33 |
| **v3.1** | **231 / 240 (96 %)** | 48 | 48 | 48 | 48 | 39 |

(out of 48 per group; the action detector was improved once — "is currently watering" — and all versions re-scored)

v3.1 passes every pass rule: no contradiction, no invented number, no promise, no fake alert (all 100 %),
question-specific 96.2 %. Remaining 9 errors: 5 weather guesses ("tomorrow will likely remain 21.5 °C"),
3 "no leaves visible", 1 "wait until tomorrow" for the next watering. None of them is about watering or safety.

Caution: the prompts and checks were improved while looking at these 40 questions, so the score can be
optimistic. A fresh set of new questions should confirm it (held-out test).

Human check: `results_chat/qwen3.5_0.8b__chat_v3.1_human_check.csv`.

## Speed note

On Windows, `http://localhost:11434` adds about 2 s per request (IPv6 fallback).
`http://127.0.0.1:11434` removes it: real speed is 0.1–0.5 s per answer on the RTX 3050.
The 2.5–3.4 s in the first experiment were this delay, not the model.

## Files

- `labels.py`: thresholds (single source of truth)
- `build_testset.py` → `testset.jsonl`
- `run_bench.py`: runs models × configs, saves `results/*.jsonl` (resumable)
- `report.py` → `summary.csv` + table

## Method references

- Ollama structured outputs (JSON schema in `format`): https://registry.ollama.ai/blog/structured-outputs
- Tam et al. 2024, *Let Me Speak Freely?*, format restrictions affect reasoning: https://aclanthology.org/2024.emnlp-industry.91
- Gao et al. 2022, *PAL: Program-aided Language Models*, let code do the computation: https://arxiv.org/abs/2211.10435
- Yang et al. 2024, *Number Cookbook*, LLMs are weak at basic number tasks: https://arxiv.org/abs/2411.03766
