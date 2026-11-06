# Research question options (2 weeks each)

**Owner:** Yassine Mtibaa · draft, 6 Nov 2026 · to choose at the next team meeting

Five research questions Nabta could answer, each in **14 days or less**, with **no budget** (hardware we already plan to own, free software, free models). Each one is built on the two papers the professor sent ([`paper-notes.md`](paper-notes.md)) and on our earlier reading ([`related-work.md`](related-work.md)).

Dates assume the pots run from **9 to 22 Nov 2026** (14 days), with analysis and writing until the final demo on **4 Dec**. Options 2 to 4 do not need living plants, so they can run in the same two weeks in parallel.

## Update 6 Nov 2026: the team's proposed question

The team chose architecture **option 1** (everything on the Raspberry Pi) with **Qwen3.5 0.8B** as the local model, and a teammate proposed this question:

> **How accurately can a small language model running on a Raspberry Pi make irrigation decisions from live sensor data, compared with a cloud-based LLM?**

**Has it been done?** Not as a whole. See [`related-work.md`](related-work.md) section 5. The closest study, ElAlaoui et al. (2026) [ELA26], had a *cloud* model (GPT-5) advise irrigation from live sensors in pots, but did not test a small or local model and did not score the decisions against a reference. Mimir (2026) [MIM26] varied model size for irrigation decisions, but only in simulation, and found bigger was not steadily better. LEAF (2026) [LEAF26] timed small models on a Raspberry Pi, but not on an agricultural task. No one has scored a sub-1B model on a Pi against a cloud model on the same live irrigation decisions. That is a real gap, and a good fit for a 2-week study.

**How to make it doable in 2 weeks (suggested design):**

1. **Shadow mode, so the plant is never at risk.** The rules engine keeps watering Pot A (and Pot B stays on its schedule), as in [`study-protocol.md`](study-protocol.md). At every decision cycle (for example every 30 min) the same live context is sent to **Qwen3.5 0.8B on the Pi** and to **one cloud model**. Each answers `water` / `no_water` with mL in the JSON format of `ai/assistant-spec/`. Their answers are logged, never executed. This is the "shadow mode" [PAR26] uses before trusting a new policy.
2. **Reference answer.** The rules engine's decision is the reference for each cycle. On top of that, two team members label a **held-out set of about 40 hard cases** (near the threshold, right after watering, sensor faults, tank empty) from the simulator, because live data from 14 days will be mostly easy "no water" cycles.
3. **Repeats.** Each held-out case is sent 3 times to each model to measure stability, as in [PAR26].

**Metrics:**

| Metric | Why |
|---|---|
| Accuracy and Cohen's kappa against the reference, with a 95% Wilson interval | "How accurately"; kappa corrects for the many easy "no water" cycles |
| Recall on "water" cycles (missed waterings) | The error that harms the plant |
| Unsafe proposals (over the 150 mL dose cap, inside the 2 h gap, water while waterlogged) | Shows what the safety layer must block |
| mL error on correct "water" decisions | Amount, not only yes/no |
| Valid JSON rate | A 0.8B model often breaks the format |
| Latency per decision on the Pi vs. the cloud (median, 90th percentile) | Practicality of option 1 |
| Stability over 3 repeats | Same input, same answer? |
| Decisions made while offline (Pi only) | The local model's advantage |

**Hypothesis:** the cloud model agrees with the rules more often, but Qwen3.5 0.8B on the Pi reaches at least 85% accuracy with no missed waterings that the safety layer would not catch, and answers within the 30-minute decision cycle.

**Zero-budget check:** Qwen3.5 0.8B runs free with Ollama on a Pi 5 (community reports of about 6 s per reply on a Pi 5 with 8 GB). For the cloud arm, use a free API tier or the course API key requested on 20 Nov; the held-out set can be run later if the key arrives late. The bench script `nabta_bench_llm.py` already logs latency, JSON validity and agreement with the rules.

**What this changes:** it replaces options 2 and 3 below and runs alongside option 1, the water study, on the same pots. Option 1 still gives the plant and water result, and this question adds the AI result. If the team instead wants the LLM to *actually* water Pot A, the water study then measures the model and not the rules, so it needs the safety layer finished and tested before 9 Nov.

## At a glance

| # | Question (short) | Type | Needs plants? | Main metric | Builds on |
|---|---|---|---|---|---|
| 1 | Does Nabta use less water than a fixed schedule without stressing the mint? | Plant experiment | Yes, Pot A and Pot B | mL saved, stress hours | Gap in [KAN25] (no field test) |
| 2 | Does a small local model explain Nabta's decisions as faithfully as a larger one? | Model evaluation | No (uses logged decisions) | Faithfulness 0 to 1, seconds per answer | [KAN25] Table 4 |
| 3 | Can a local model classify the mint's state (OK / WARNING / ALARM) reliably, including sensor faults? | Model evaluation | No | Accuracy, alarm recall, stability over 3 repeats | [PAR26] emergency agent test |
| 4 | Does grounding the assistant in our plant-research documents (RAG) make its spearmint answers more correct? | Model evaluation | No | Correct answers out of 40, Recall@5 | [PAR26] question set, [KAN25] retrieval metrics |
| 5 | Does Nabta keep the mint safe when the network or the model is down? | System test | Yes, Pot A | Missed or wrong waterings during outages | [PAR26] offline fallback |

**Recommendation:** keep **option 1** as the main study (the team chose it on 2 Nov) and add **option 2 or option 3** as the AI part. Both papers the professor sent are about evaluating language-model agents, so an AI evaluation alongside the water study fits the course. Option 2 reuses the explanations Pot A produces anyway; option 3 is the closest copy of a published method.

---

## Option 1: Water saving without stress (plant experiment)

**Question:** Over 14 days, does Nabta (Pot A) use less water than a fixed schedule (Pot B) while keeping the spearmint at least as healthy?

**Why it matters:** CottonBot [KAN25] claims more efficient water use but has not run its field trial yet; the greenhouse paper [PAR26] reports no water outcome. Earlier turf studies found 16 to 83% savings with sensors, but outdoors with rain ([related work](related-work.md) section 1). No one has measured this for a potted herb indoors with an AI explanation layer.

**Hypotheses:** H1a: Pot A uses at least 20% less water. H1b: Pot A has no more stress hours or wilting than Pot B.

**Method:** as in [`study-protocol.md`](study-protocol.md), shortened to 14 days. Rules engine waters Pot A (below index 60, refill to 85 to 90); Pot B gets a frozen volume every 2 days at 9:00 set from the calibration week. Pots swap places every 4 days instead of weekly.

**Metrics:** total mL per pot; % saved; mL drained out of the pot; hours below index 40; daily wilting score 0 to 4; daily pot weight as an independent check; height and leaf count on days 0, 7 and 14.

**Zero-budget check:** needs the two pots, two sensors, one pump, a kitchen scale and the grow light already in the plan. Pot B can be watered by hand with a measuring jug.

**Risks:** n = 1 pot per method, so it is a case study, not a statistical test. Growth in 14 days is too small to compare, so health is judged by stress, not size.

---

## Option 2: Local model size vs. explanation faithfulness (model evaluation)

**Question:** Does a small local model (about 4B parameters, Pi-sized) explain Nabta's watering decisions as faithfully as a larger local model (8B), and how much slower is the larger one?

**Why it matters:** CottonBot [KAN25] found Llama 3.1 8B most faithful (0.97) and Phi-3 3.8B twice as fast but less faithful (0.88), on cotton questions on unknown hardware. Nabta needs the answer for our own task and our own device, and it decides option 1 vs. option 2 of the architecture. [PAR26] tested only cloud models and lists other models as future work.

**Hypothesis:** the 4B model reaches at least 0.85 faithfulness and answers in under 60 s on the Pi; the 8B model is more faithful but too slow on the Pi.

**Method:**
1. Test set: 60 decision contexts (the moisture, temperature, last watering and the rule's decision), 30 from the simulator's `decision_contexts.jsonl` and 30 logged from Pot A in the first week. Balance: 20 "water", 30 "no water", 10 with a sensor fault.
2. Ask each model to explain the rule's decision in two sentences, in the JSON format of `ai/assistant-spec/`. Same prompt for all models.
3. Two team members score each explanation blind (model names hidden): faithfulness 0 to 1 (does it state the right numbers and reason, nothing invented), clarity 1 to 5.
4. Run with the existing `nabta_bench_llm.py`, which already logs time and JSON validity.

**Metrics:** mean faithfulness (as in [KAN25]); share of explanations with a wrong number; JSON validity; median and 90th-percentile seconds per answer on the Pi and on a laptop; agreement between the two raters.

**Zero-budget check:** Ollama and the models are free (Phi-3 or Gemma 3 4B vs. Llama 3.1 8B). If the course API key arrives after 20 Nov, a cloud model can be added as a third arm.

**Risks:** hand scoring takes time (60 × 2 or 3 models × 2 raters, about 4 hours each). Keep the set at 60.

---

## Option 3: Reliable state classification, including sensor faults (model evaluation)

**Question:** How accurately and how consistently can a local model classify the plant's state as OK, WARNING or ALARM, including sensor faults, compared with Nabta's fixed rules?

**Why it matters:** this copies the [PAR26] emergency-agent test (36 labelled synthetic cases, each sent 3 times: accuracy 0.81, stability 0.97, all alarms caught) with a local model instead of a cloud one, on a soil pot instead of hydroponics. Nabta's assistant must "warn when something looks wrong" (`ai/assistant-spec/`), so we need to know how often it is right and whether it gives the same answer twice.

**Hypothesis:** the model catches every ALARM case (recall 1.0) with at least 0.80 accuracy and 0.90 stability, and its mistakes are borderline OK/WARNING cases, as in [PAR26].

**Method:**
1. Write 45 cases, 15 per class, from the spearmint thresholds in [`thresholds-and-calibration.md`](thresholds-and-calibration.md): moisture, temperature, humidity, light, tank level, last watering. Include 9 sensor faults (stuck value, sudden jump, reading out of range) taken from the simulator's labelled faults. Two members label each case before any model runs.
2. Send each case 3 times to the model with the same prompt; record status, reason and time.
3. Compare with the rules engine's own label on the same cases.

**Metrics:** accuracy with a 95% Wilson interval; recall for ALARM and for sensor faults; stability (share of cases with the same answer all 3 times); confusion matrix; seconds per case.

**Zero-budget check:** laptop or Pi with Ollama; a short Python script that reads a CSV and calls the model. No plants needed, so it can start on 9 Nov.

**Risks:** synthetic cases may be easier than real ones; add 10 real cases from Pot A's week-1 log if time allows.

---

## Option 4: Does RAG over our own plant research improve answers? (model evaluation)

**Question:** Does giving the assistant our spearmint documents through retrieval (RAG) raise the share of correct answers to growers' questions, compared with the same model without RAG?

**Why it matters:** both papers rely on RAG. [PAR26] got 38/40 correct with a large cloud model and RAG; [KAN25] found retrieval quality drives answer quality and that all-MiniLM-L6-v2 with FAISS retrieves best. We already have the knowledge base (`spearmint-requirements.md`, `thresholds-and-calibration.md`) but no test of whether it helps a small local model.

**Hypothesis:** with RAG the local model answers at least 85% of questions correctly, against under 70% without it, and most of the gain is on numeric and range questions.

**Method:**
1. Write 40 spearmint questions using the 9 question types of [PAR26] (for example "At what moisture index should Nabta water?", "Why are the lower leaves yellow?"), with a reference answer and the source paragraph for each.
2. Index our plant-research docs with all-MiniLM-L6-v2 and FAISS (the [KAN25] best pair), chunk size 1,000 characters, top 5.
3. Ask the same local model each question with and without RAG. Label each answer True / Erroneous / Not found, blind.

**Metrics:** correct answers out of 40 with a 95% Wilson interval, per arm and per question type; Recall@5 and MRR of the retriever; seconds per answer.

**Zero-budget check:** all free and runs on a laptop. Feeds directly into `ai/knowledge-base/`.

**Risks:** our documents are short, so retrieval may be easy. That is still a valid result; say so.

---

## Option 5: Safe behaviour when the network or model is down (system test)

**Question:** When the model or the network is unavailable, does Nabta still water Pot A correctly and safely, and does it avoid acting on old alarms when it comes back?

**Why it matters:** [PAR26] keeps sensing and basic control at the edge during outages, buffers data, and on reconnection re-checks the current state instead of acting on old alarms. They describe this but report no measurement of it. Offline operation is one of Nabta's stated goals.

**Hypothesis:** during outages every watering Pot A needs is still done by the fallback rules, no watering breaks the dose caps, and no old alarm triggers a watering after reconnection.

**Method:** during the 14 days of option 1, unplug the network or stop the model on a fixed timetable (for example one 6 h outage every 2 days, 7 outages in all, at different times of day). Log every decision with an "online / offline" flag. After each reconnection, check what the system did with alarms raised while offline.

**Metrics:** waterings needed vs. done during outages; any dose-cap violation; hours below index 40 during outages vs. normal hours; alarms acted on late (should be 0); time to detect the outage.

**Zero-budget check:** no extra hardware; piggybacks on Pot A in option 1.

**Risks:** only makes sense if the firmware or the Pi has a fallback rule written by then; check with Aymen and Ahmed Hamouda. It adds outages to Pot A, so agree on it before 9 Nov so option 1's results are not mixed up.

---

## How to choose

| Option | Effort | Fits the course (AI engineering) | Uses the professor's papers | Depends on hardware working by 9 Nov |
|---|---|---|---|---|
| 1 | Medium, daily checks | Partly (the AI explains, rules decide) | As the gap they leave | Yes |
| 2 | Medium, hand scoring | Strongly | [KAN25] method | No (simulator data is enough) |
| 3 | Low to medium | Strongly | [PAR26] method, almost one-to-one | No |
| 4 | Medium | Strongly | Both | No |
| 5 | Low, on top of 1 | Partly | [PAR26] design | Yes |

Options 2, 3 and 4 touch Ahmed Hamouda's `ai/evaluation/` area, so the AI option should be agreed with him.
