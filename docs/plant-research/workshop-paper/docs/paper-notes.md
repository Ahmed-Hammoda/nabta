# Paper notes

**Owner:** Yassine Mtibaa · added 6 Nov 2026

Detailed reading notes for papers the team studies closely, one section per paper: what they built, how they evaluated it, the numbers, the limits, and what Nabta can reuse. Shorter one-row entries for every source are in [`related-work.md`](related-work.md), and the keys are in [`references.md`](references.md).

| Key | Paper | Sent by |
|---|---|---|
| [KAN25] | Kandamali et al. (2025), CottonBot | Professor, 6 Nov 2026 |
| [PAR26] | Pardo-Pina et al. (2026), Agent-based service architecture for smart greenhouses | Professor, 6 Nov 2026 |

---

## [KAN25] CottonBot: an AI-driven cotton farming assistant and irrigation advisor

Kandamali, D. F., Porter, W. M., Porter, E., McLemore, A., and Rains, G. C. (2025). CottonBot: An AI-driven cotton farming assistant and irrigation advisor using LLM-RAG and agentic AI tools. *Smart Agricultural Technology* 12, 101640. [doi:10.1016/j.atech.2025.101640](https://doi.org/10.1016/j.atech.2025.101640). Open access (CC BY).

### What they built

A chat assistant for cotton farmers in Georgia, USA, served as a Flutter mobile app with a FastAPI backend.

- **Knowledge (RAG):** the 2024 Georgia Cotton Production Guide, cut into 1,000-character chunks with 100 characters of overlap, embedded and stored in a vector database. For each question the top 5 chunks are passed to the model.
- **Model:** open-weight models run locally with **Ollama**, so there is no API cost and farm data stays on site. Llama 3.1 (8B) was chosen.
- **Live data (agentic tools):** three tools the model can call: (1) soil moisture from 12 field sensors at 3 depths, (2) a 7-day weather forecast from OpenWeatherMap, (3) an irrigation decision tool.
- **Who decides irrigation:** the irrigation tool is **deterministic**. It averages soil tension across depths with weights that change with crop age (days after planting), and says "Irrigate" when the weighted value is 45 kPa or more and no rain is forecast, otherwise "Wait". The language model then writes the recommendation and the reasons in plain words. An LSTM model forecasts soil moisture up to 7 days ahead.

### How they evaluated it

| Part | Metric | Setup |
|---|---|---|
| Retrieval | Mean reciprocal rank (MRR), Recall@5, Precision@5 | 6 embedding models × 2 vector stores (FAISS, Chroma) |
| Answers | Faithfulness (0 to 1, **scored by hand** against the retrieved text), cosine similarity to a reference answer, average generation time | 7 open-weight models in Ollama, all 4-bit quantized |
| Irrigation forecast | Mean absolute error of 1-day-ahead soil tension against the real sensor | CottonBot vs. a manual estimate |

### Main results

- Best retrieval: all-MiniLM-L6-v2 with FAISS (MRR 0.886, Recall@5 0.948, Precision@5 0.929). FAISS beat Chroma for every embedding model.
- Answer quality and speed of local models:

| Model | Size | Faithfulness | Cosine similarity | Time per answer |
|---|---|---|---|---|
| Llama 3.1 | 8B | 0.968 | 0.952 | 6.2 s |
| Llama 3 | 8B | 0.962 | 0.952 | 6.2 s |
| DeepSeek-R1 | 7.6B | 0.941 | 0.939 | 6.4 s |
| Mistral | 7.2B | 0.895 | 0.898 | 5.3 s |
| Phi-3 | 3.8B | 0.879 | 0.849 | 2.3 s |
| Gemma 3 | 4.3B | 0.853 | 0.864 | 3.4 s |
| Llama 2 | 6.7B | 0.809 | 0.798 | 4.5 s |

- Smaller models (Phi-3, Gemma 3) were about twice as fast but less faithful. The authors say they suit edge devices where speed matters.
- 1-day-ahead forecast: MAE under 1.0 kPa for CottonBot against 1.4 for the manual method. Both agreed 100% with the sensor on whether to irrigate the next day.

### Limits (stated or visible)

- **No field trial yet.** Water saving and yield gains are claimed in the abstract but only planned for the 2026 season. The irrigation logic was validated on data, not on a crop.
- Faithfulness was scored by the authors; the number of test questions and raters is not reported.
- Generation times are given without the hardware they ran on.
- Cotton in a field, with rain and deep roots; Nabta is one indoor pot with no rain.

### What Nabta reuses

1. **Same split of roles as Nabta:** a deterministic rule decides irrigation, the language model explains it. This is published support for our "rules decide, the model explains" design.
2. **Local model with Ollama** for cost and privacy, which matches option 1 and our zero-budget rule.
3. **Their evaluation metrics** (faithfulness 0 to 1, generation time, Recall@5 and MRR) can be copied for our own model and RAG tests.
4. **Their model table** is a shortlist for us: Phi-3 (3.8B) and Gemma 3 (4B) are the realistic sizes for a Raspberry Pi; Llama 3.1 8B is the quality reference.
5. **The gap we can fill:** CottonBot never tested its advice on a real crop. Nabta's Pot A vs. Pot B study does exactly that, on a small scale.

---

## [PAR26] An agent-based service architecture for smart greenhouses

Pardo-Pina, S., Germer, J., Suay-Cortés, R., Platero-Horcajadas, M., and Ferrández-Pastor, F.-J. (2026). An agent-based service architecture for smart greenhouses: Telemetry analytics and decision support with RAG-grounded LLM agents. *Smart Agricultural Technology* 13, 101872. [doi:10.1016/j.atech.2026.101872](https://doi.org/10.1016/j.atech.2026.101872). Open access (CC BY).

### What they built

A layered IoT system for a 50 m² hydroponic greenhouse growing industrial hemp in Spain, with three AI "agents" on top:

| Agent | Role | May it act? |
|---|---|---|
| S1 Chat-Agent | Answers growers' questions with RAG over crop manuals and procedures; writes daily reports | No, advice only |
| S2-IoT-Agent | Analyses exported sensor data (statistics, anomalies, daily light) and can start short irrigation cycles | Yes, within limits |
| S2-E-Agent | Classifies emergencies as OK / WARNING / ALARM and proposes the response | Yes, when the operator enables it |

- **Hardware and software:** ESP microcontrollers and sensors → a **Raspberry Pi 4 with Home Assistant and InfluxDB** at the edge → n8n workflows on a small cloud server → OpenAI models with a Pinecone vector database. Growers talk to it through Telegram, WhatsApp and a web dashboard.
- **Safety gate before any action:** (1) per-sensor checks (units, timestamps, range, rate of change); (2) when several sensors measure the same thing, take the median and drop outliers; (3) thresholds with hysteresis, and an alarm only after *k* readings in a row; (4) the model's command must match a strict schema; (5) hard limits per actuator; (6) high-impact actions need the operator's confirmation; (7) new policies run in "shadow mode" first; (8) a kill switch and a watchdog.
- **Offline fallback:** if the cloud is unreachable, the Pi and ESPs keep sensing and running basic control, show an OFFLINE state, buffer data, and on reconnection report what happened but **never act on old alarms**: they re-check the current state first.

### How they evaluated it, and the numbers

| Test | Method | Result |
|---|---|---|
| Chat answers | 40 grower questions covering 9 question types, each labelled True / Erroneous / Not found by hand; ROUGE-L, BLEU-4, BERTScore against reference answers | GPT-5.2: 38/40 correct (95%, 95% Wilson interval 0.835 to 0.986). GPT-4o-mini: 32/40 (80%). BERTScore about 0.87 for both |
| Daily light from a lux sensor | Agent converts lux to PPFD (lux ÷ 54) and integrates to daily light integral (DLI), then labels each day LOW / OK / HIGH; compared with the same calculation in Python | 13 days, MAE 0.005 mol/m²/day, 13/13 days classified right |
| Emergency agent | 36 **synthetic** cases (stage, temperature, humidity, EC, pH) with expert labels, each sent **3 times** | Accuracy 0.81; stability across the 3 repeats 0.97; all 9 ALARM cases caught; errors were borderline OK/WARNING cases |
| Speed | 10 requests to the agent | 0.37 s average response |

- GPT-4 models made arithmetic and statistics mistakes on the sensor data; GPT-5 did not.

### Limits (stated by the authors)

- One greenhouse, one crop, a short window; emergency tests used synthetic cases.
- Only OpenAI models were tested, so results may not hold for other or local models.
- Thresholds and prompts were tuned by the authors, not checked by independent growers.

### What Nabta reuses

1. **Evaluation recipe that fits two weeks and zero budget:** a small labelled test set (36 to 40 items), each case repeated 3 times, reporting **accuracy with a Wilson confidence interval, stability, and a confusion matrix**. We can run the same recipe on our simulator's labelled decision contexts and on real readings.
2. **Their 9 question types** (numeric, range, cause and effect, procedure, definition, schedule, diagnosis, optimisation, quality) give a ready structure for a spearmint question set for the assistant.
3. **Safety gate ideas** that match `ai/assistant-spec/` section 6: median of readings, *k* readings in a row before acting, strict JSON schema, hard limits, and "don't act on old alarms after an outage".
4. **Edge-first offline mode on a Raspberry Pi**, the same idea as Nabta's option 1, with a concrete rule for what happens on reconnection.
5. **Lux to DLI:** they use lux ÷ 54 for sunlight; for white LED we use about lux ÷ 71 (1,000 lux ≈ 14 µmol/m²/s, see [references](references.md)). Their method lets us check the grow light gives spearmint at least 10 mol/m²/day.
6. **The gap we can fill:** they tested only cloud models and called non-OpenAI benchmarking future work. Nabta can compare a local model with a cloud model on the same tests.

---

## What the two papers together say for Nabta

- Both keep **a deterministic rule or policy gate in charge of the water** and use the language model to explain, report and advise. Nabta's design follows the same pattern.
- Neither paper measured water saved or plant health on a real crop with the AI in the loop. That is the gap Nabta's Pot A vs. Pot B study covers.
- One paper evaluated only local models, the other only cloud models. Neither compared the two on the same task, which a short Nabta experiment can do.
- Both used small test sets (13 days, 36 cases, 40 questions) and still reported useful, honest numbers. Two weeks is enough for studies of that size.

Research questions built on these notes are in [`research-questions.md`](research-questions.md).
