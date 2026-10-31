# Related work

**Owner:** Yassine Mtibaa · starter draft, 31 Oct 2026

Earlier studies show that soil moisture sensors save water compared with timers without harming the plant, and that language models can explain agricultural decisions and run on a Raspberry Pi. Nabta combines the two, for a potted herb indoors, and compares a local model with a cloud model. This file lists what each source shows and where Nabta differs. It feeds the report's related-work chapter.

Status: four sources read so far. The "To read next" list at the end is the remaining work.

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

## To read next

- [ ] Find one study on sensor-based watering of **potted plants or herbs** (greenhouse or indoor), to close the gap in section 1.
- [ ] Find one study on how people **rate explanations** (clarity, trust), to support Ahmed Hamouda's RQ2 rubric.
- [ ] Find one source on water use of **mint under deficit irrigation**, beyond [FUM] in [references](references.md).
- [ ] Read the full Cardenas-Lailhacar et al. (2010) paper and note their method for comparing treatments, since our design copies its logic.
- [ ] Check whether the two arXiv preprints have since been published in a journal or conference, and cite that version.
