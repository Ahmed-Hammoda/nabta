# Related work

**Owner:** Yassine Mtibaa · starter draft, 31 Oct 2026

Earlier studies show that soil moisture sensors save water compared with timers without harming the plant, and that language models can explain agricultural decisions and run on a Raspberry Pi. Nabta combines the two, for a potted herb indoors, and compares a local model with a cloud model. This file lists what each source shows and where Nabta differs. It feeds the report's related-work chapter.

Status: six sources read in full so far, plus a novelty check of the team's research question (section 5), including the two papers the professor sent on 6 Nov 2026 (section 4, detailed notes in [`paper-notes.md`](paper-notes.md)). The "To read next" list at the end is the remaining work.

---

## 1. Sensor-based vs. scheduled irrigation (RQ1)

| Source | What they did | What they found | How Nabta differs |
|---|---|---|---|
| Cardenas-Lailhacar et al. (2010), [Sensor-based automation of irrigation on bermudagrass during dry weather conditions](https://ascelibrary.com/doi/10.1061/%28ASCE%29IR.1943-4774.0000153), *Journal of Irrigation and Drainage Engineering* 136(3) | Field plots of turfgrass in Florida, four commercial soil moisture sensor systems against a time-based schedule | Sensor systems saved 16 to 54% of water in the first half of 2006 and 28 to 83% in the second half, for three of the four brands | Outdoor turf with rain; Nabta is one indoor pot with no rain, so all water comes from the system |
| Acclima summary of the same University of Florida work, [Sensor-based automation of irrigation of bermudagrass](https://acclima.com/sensor-based-automation-of-irrigation-of-bermudagrass/) | Same study, summarised by a sensor maker | Turf quality showed no significant difference between treatments; savings were inflated by heavy rain in the study period | Supports H1b (savings without loss of quality); written by a manufacturer, so cite the journal paper in the report |

**Gap:** these studies are on turf and field crops outdoors. We found no study yet on a potted culinary herb indoors, where rain plays no part and the pot dries faster.

---

## 2. Language models that explain agricultural decisions (RQ2)

| Source | What they did | What they found | How Nabta differs |
|---|---|---|---|
| Zhang et al. (2024), [Large language models for explainable decisions in dynamic digital twins](https://arxiv.org/abs/2405.14411v2), arXiv:2405.14411 | Used a language model as an explanation layer on top of an autonomous decision system, grounded in a domain knowledge base, with a smart-agriculture case study | Language models can turn automated decisions into natural-language explanations using domain knowledge | Same idea as Nabta's "rules decide, the model explains"; Nabta adds a local vs. cloud comparison on a real plant |
| Lee et al. (2025), [SPADE: a large language model framework for soil moisture pattern recognition and anomaly detection in precision agriculture](https://arxiv.org/pdf/2509.18123v1), arXiv:2509.18123 | Gave GPT-4.1 weekly soil moisture time series as text, with a domain prompt, to detect irrigation events and anomalies on 47 fields | Anomaly detection F1 0.91 against 0.51 for a threshold method; writes a short reason for each anomaly; about $0.007 per weekly report | Only reads past data and does not decide watering; cloud model only. Nabta explains live decisions and tests a local model too |

**Gap:** existing work uses large cloud models. We found no comparison of a small local model against a cloud model for explaining irrigation decisions.

---

## 3. Running language models on a Raspberry Pi (option 1)

| Source | What they did | What they found | How Nabta differs |
|---|---|---|---|
| Nezami et al. (2024), [Generative AI on the edge: architecture and performance evaluation](https://arxiv.org/abs/2411.17712v1), arXiv:2411.17712 | Ran lightweight models (Yi, Phi, Llama 3) CPU-only on a Raspberry Pi 5 cluster | 5 to 12 tokens per second, using under 50% of CPU and RAM | Nabta uses one Pi, not a cluster; this gives a speed range to compare our own benchmark with |
| Jang and Morabito (2025), [Edge-first language model inference: models, metrics, and tradeoffs](https://arxiv.org/abs/2505.16508v2), arXiv:2505.16508 | Compared small models on edge devices with cloud inference | Edge inference can match the cloud at lower cost in some cases; in others a cloud fallback is needed | Supports the RQ2 framing: local works offline, the cloud may answer better |

---

## 4. Language-model assistants with sensors in the loop (sent by the professor, 6 Nov 2026)

| Source | What they did | What they found | How Nabta differs |
|---|---|---|---|
| Kandamali et al. (2025), [CottonBot: an AI-driven cotton farming assistant and irrigation advisor using LLM-RAG and agentic AI tools](https://doi.org/10.1016/j.atech.2025.101640), *Smart Agricultural Technology* 12, 101640 | Local open-weight models (Ollama) with RAG over a cotton guide, plus tools for soil moisture, weather and a deterministic irrigation rule (irrigate at 45 kPa); compared 7 local models and 6 embedding models | Llama 3.1 8B most faithful (0.97, 6.2 s per answer); Phi-3 and Gemma 3 twice as fast but less faithful (0.85 to 0.88); field trial of water saving still planned, not done | Same "rule decides, model explains" split as Nabta, but never tested on a real crop. Nabta tests it on a real pot against a fixed schedule |
| Pardo-Pina et al. (2026), [An agent-based service architecture for smart greenhouses: telemetry analytics and decision support with RAG-grounded LLM agents](https://doi.org/10.1016/j.atech.2026.101872), *Smart Agricultural Technology* 13, 101872 | Raspberry Pi 4 + Home Assistant at the edge, cloud LLM agents for chat (RAG), sensor analysis and emergencies, with a safety gate and offline fallback; hydroponic hemp greenhouse | Chat 38/40 correct with GPT-5.2 vs. 32/40 with GPT-4o-mini; emergency agent 0.81 accuracy and 0.97 stability over 36 synthetic cases × 3 repeats, all alarms caught; lux-to-DLI exact over 13 days | Cloud models only, no water or plant-health outcome. Nabta can compare a local and a cloud model on the same tests and measure the plant |

**Gap:** both papers keep a rule in charge of actuation and use the model to explain or advise, like Nabta. Neither measured water use or plant health with the system in the loop, and neither compared local and cloud models on the same task. Their evaluation recipe (small labelled test set, repeats, accuracy with a confidence interval) fits a two-week student study. Options built on this are in [`research-questions.md`](research-questions.md).

---

## 5. Has the team's question been studied? (checked 6 Nov 2026)

Teammate's proposed question: *How accurately can a small language model running on a Raspberry Pi make irrigation decisions from live sensor data, compared with a cloud-based LLM?* Web search of journals (Elsevier, MDPI, Frontiers) and arXiv on 6 Nov 2026.

| Source | What they did | How close to our question |
|---|---|---|
| ElAlaoui et al. (2026), [Letting the crop speak: a proof-of-concept sensor-grounded LLM advisor for potato irrigation](https://www.mdpi.com/2624-7402/8/11/468), *AgriEngineering* 8(11), 468 | Cloud GPT-5 read live ESP32 soil moisture and advised when and how much to water 6 potted potatoes for 14 weeks; a human applied it; vs. 6 pots run by a technician | **Closest.** The LLM makes irrigation decisions from live sensors, in pots. But cloud only, no small or local model, no accuracy measured against a reference, responses not logged. Found 29.6% less water than the technician (one bench, no replication) |
| Liu et al. (2026), [Mimir: physics-grounded LLM agents for long-horizon irrigation control](https://arxiv.org/abs/2610.02038v1), arXiv:2610.02038 | LLM agents propose daily irrigation, a simulator checks and revises them; replay of historical seasons | LLM decides irrigation and model size was varied: **bigger models gave no steady gain**. Simulation only, no edge device, no live sensors |
| Park et al. (2026), [AquaAgent-OSPy](https://www.sciencedirect.com/science/article/abs/pii/S0168169926008653), *Computers and Electronics in Agriculture* 254, 112267 | LLM tool-agent recommends irrigation strategies from crop simulations for rice; a human approves | Recommends but does not actuate; simulation, no edge device, no local vs. cloud |
| Kandamali et al. (2025) [KAN25], section 4 | Local 4B to 8B models explain a rule's irrigation decision | Local models, but the **rule** decides; hardware not reported; no cloud comparison |
| Pardo-Pina et al. (2026) [PAR26], section 4 | Cloud GPT agents classify greenhouse states, can start short irrigation | Cloud only; authors list non-OpenAI models as future work |
| Abdulkadhim and Repas (2026), [LEAF: LLM edge assessment framework](https://www.mdpi.com/2504-4990/8/2/48), *Machine Learning and Knowledge Extraction* 8(2), 48 | Six 0.5B to 3B models (Ollama, 4-bit) timed on Raspberry Pi 4 and 5, Jetson Nano and GPUs | Gives Pi speed numbers (qwen2:0.5b: 1.0 s on Pi 5, 4.5 s on Pi 4) but on a generic summarising task, not agriculture; no cloud comparison |
| Taueatsoala et al. (2026), [TinyML-enabled IoT for sustainable precision irrigation](https://arxiv.org/abs/2601.13054v1), arXiv:2601.13054; Bera et al. (2026), [Ensemble learning-based soil moisture monitoring](https://www.frontiersin.org/journals/the-internet-of-things/articles/10.3389/friot.2026.1870523/full), *Frontiers in the IoT* 5 | Irrigation decisions on an ESP32 or Raspberry Pi with gradient boosting or random forest | Edge irrigation decisions, but classical ML, **not language models** |

**Verdict:** the exact question has **not** been published. Parts of it have: a cloud LLM deciding irrigation from live sensors (ElAlaoui 2026), LLM size vs. irrigation decisions in simulation (Mimir 2026), and small models timed on a Raspberry Pi on non-agricultural tasks (LEAF 2026). No study we found runs a sub-1B model on a Raspberry Pi to make irrigation decisions from live sensor data and scores it against a cloud LLM on the same decisions. That combination is Nabta's gap.

---

## To read next

- [ ] Find one study on sensor-based watering of **potted plants or herbs** (greenhouse or indoor), to close the gap in section 1.
- [ ] Find one study on how people **rate explanations** (clarity, trust), to support Ahmed Hamouda's RQ2 rubric.
- [ ] Find one source on water use of **mint under deficit irrigation**, beyond [FUM] in [references](references.md).
- [ ] Read the full Cardenas-Lailhacar et al. (2010) paper and note their method for comparing treatments, since our design copies its logic.
- [ ] Check whether the two arXiv preprints have since been published in a journal or conference, and cite that version.
