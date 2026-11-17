# Full paper structure (v3, 16 Nov 2026)

Workshop paper, about 6 pages plus references, two columns. For each section: what it must say, which figure or table goes there, which file in this kit feeds it, and an approximate length. `[ ]` = numbers that come only from `experiment/metrics.py` on real logs.

**Design used here (pending your choice on the card in the thread):** the pump is driven only by rules, as the diagram says. Pot A = C2 multi-rule, Pot B = C1 single threshold. Qwen3.5 0.8B (C3) and ChatGPT (C4) make the same watering decision on the same live data in **shadow mode** (logged, never executed) and in the **closed-loop replay**. In the real system the AI only explains, which the diagram shows.

---

## Title
Rules, a 0.8B Model on a Raspberry Pi, or a Cloud LLM? Comparing Irrigation Controllers on the Same Live Sensor Data from a Potted Spearmint Plant

Alternative, short: *Nabta: An Offline Smart Pot for Comparing Rule-Based and LLM Irrigation Decisions*

## Authors and affiliation
Yassine Mtibaa, Ahmed Hamouda, Aymen Saad, Ahmed Ridha Melayah, Youssef Ben Moussa. MedTech, CS496 AI Engineering. TODO: author order and corresponding author.

## Abstract (about 230 words) -> `abstract.md`
Five moves, one or two sentences each:
1. Context: LLMs are being proposed as decision layers in smart irrigation.
2. Gap: existing systems either keep a rule in charge with the LLM only explaining ([KAN25]) or use large cloud models behind a gate ([PAR26]); no comparison of a sub-1B offline edge model, rule baselines and a cloud LLM on the watering decision itself with the same live inputs.
3. What we built: Nabta, an offline pot on a Raspberry Pi 5 where rules water and a local model explains (Fig. 1).
4. What we did: four controllers on identical 30-min contexts for [14] days; precision, reliability, cost.
5. Results [ ] and the take-away sentence; release of code and data.

**Keywords:** smart irrigation, small language models, edge AI, Raspberry Pi, IoT, LLM evaluation.

---

## 1. Introduction (about 0.75 page)
- **P1 Problem.** Potted herbs fail mostly from wrong watering. Sensor thresholds help but are rigid and silent: the grower doesn't know why the pot did or didn't water.
- **P2 Trend.** LLMs are now being added to farm IoT for decision support and explanation ([KAN25], [PAR26]). Small models (< 1B) can run offline on a Raspberry Pi, with no cost and no privacy risk.
- **P3 Gap.** [KAN25]: a fixed rule decides, the LLM only phrases it, local models only, Q&A evaluation, no in-loop trial. [PAR26]: cloud GPT agents behind a safety gate, errors near thresholds, cloud models only. Nobody has put a rule baseline, a sub-1B edge model and a cloud LLM on the **same live decisions** and measured the watering.
- **P4 This paper.** Main RQ + RQ1 (precision), RQ2 (reliability), RQ3 (cost), in one sentence each (`docs/methods.md` section 0).
- **P5 Contributions** (bulleted):
  1. An open, low-cost, fully offline smart-pot testbed in which rules water and a 0.8B model explains, with an output validator and a question router (Fig. 1).
  2. A comparison of four controllers on identical live contexts, using shadow mode and closed-loop replay so the LLMs never touch the pump.
  3. Precision, reliability and cost results for a sub-1B edge model vs. a cloud LLM vs. rules.
  4. Released hardware list, prompts, logs and code.

## 2. Related Work (about 0.6 page) -> `docs/related-work.md`, all keys in `refs.bib`
Draft paragraphs with citations are already in `main.tex`.
- **2.1 Sensor-based irrigation control.** Sensors vs. timers on turf [CAR10]; set-point watering of potted basil [MON18]; edge irrigation with classical ML: TinyML [TAU26], ensemble learning [BER26], ESP32 + LSTM [KUN25]. Optional: UGA greenhouse/nursery savings [UGA07, UGA13] (press releases; find the journal papers).
- **2.2 Language models for agricultural decisions.** Explain or monitor only: digital-twin explanations [ZHA24], SPADE soil-moisture anomalies [LEE25], plant-health messages [AGA24], agentic XAI for rice [YAM25]. Rule decides, LLM explains: CottonBot [KAN25]. LLM recommends water: AquaAgent-OSPy [PARK26], Mimir (bigger is not steadily better) [MIM26], cloud GPT-5 for potted potatoes [ELA26] (closest work).
- **2.3 Agentic IoT architectures with safety gates.** [PAR26].
- **2.4 Small language models on edge hardware.** Pi 5 speeds [NEZ24, STRAT], LEAF on Pi 4/5 [LEAF26], edge vs. cloud trade-offs [JAN25].
- **Gap sentence.** No sub-1B offline model on a Pi scored against rules and a cloud LLM on the same live irrigation decisions.
- Spearmint facts for section 4.4: [NSW], [OMAFRA], [ISWS], [FUM], [OKW11], [VT].
- Not cited yet but kept in `refs.bib`: other systems (Plantbot [MAS25], Tracking Anyplant [NAB25], soil drydown [GON23]), more mint studies [WSU14, ZAN, AGR19], datasets, open-source projects and products, and the plant-choice sources.

## 3. The Nabta System (about 1.25 pages) -> `docs/methods.md` section 1
**Figure 1 (full width, top of page 2): `figures/fig1_system_overview.png`**, "Anatomy of Nabta: the pot waters, senses, thinks and tells. Code decides; the AI only explains."

Walk through Fig. 1 in its own order, one short subsection per branch:
- **3.1 Waters.** LED grow strip, relay module (5 V), one pump per jar from a shared 4 L tank, YF-S401 flow meter measuring each dose in mL. *The only way to the pump runs through the rules.*
- **3.2 Senses.** Capacitive soil probe via ADS1115 ADC, BH1750 light, GY-BME280 air temperature and humidity, flow meter. Read, averaged and logged every 30 min.
- **3.3 Thinks (Raspberry Pi 5, 4 GB, offline).** The five-step pipeline in Fig. 1:
  1. *Read & log*: 30-min averages, 24 h light total, one row in `log_30min.csv`.
  2. *Rule engine*: plain thresholds, no model; alerts (dry, wet, heat, cold, low light); low tank blocks watering.
  3. *FACTS*: a fixed card built by code each cycle (soil, air, humidity, light, decision, alerts, watered, next): all the AI is allowed to know.
  4. *Small language model*: qwen3.5:0.8b in Ollama writes 1 to 3 sentences from FACTS.
  5. *Validator*: same decision as the rules, no number outside FACTS, no inactive alert, no promised action; on failure, a sentence written by code is shown instead.
  - *Question router*: the AI labels each user question; "forcing", off-topic and unknown get a fixed reply from code ("I can't control watering. The rules decide that.").
- **3.4 Tells.** Phone app on home Wi-Fi, no cloud: live readings, the checked explanation, and "Ask Nabta".
- **Listing 1:** a FACTS card and the decision context (JSON).
- **Table 1:** bill of materials with cost. TODO: prices.

## 4. Experimental Design (about 1 page) -> `docs/methods.md` sections 0, 2, 3
- **4.1 Research questions and hypotheses.** Main RQ, RQ1 to RQ3, H1 to H3 (copy from methods section 0).
- **4.2 Controllers compared.** **Table 2:** C1 single threshold, C2 multi-rule, C3 Qwen3.5 0.8B (Pi, offline), C4 ChatGPT (cloud). For C3 and C4 the model is asked for the *decision* (`{"action","ml","reason"}`), not the explanation; they sit in a shadow slot next to step 2 of Fig. 1. ChatGPT is used only in the offline evaluation on logged data, never inside the pot, so the deployed system stays "no cloud".
- **4.3 Frozen LLM settings.** **Table 3:** temperature 0, top-p 1, max 200 tokens, seed 42, 4096 context, JSON only, same prompt for both.
- **4.4 Plants and setup.** Two spearmint jars from the same batch; Pot A watered by C2, Pot B by C1; positions swapped every 4 days; [14] days; daily weight, wilting score 0 to 4, photo.
- **4.5 Three evaluation modes.**
  - *Real pots* (C1, C2): precision on real plants.
  - *Shadow mode* (all four): every logged context goes to every controller; answers logged, never executed (RQ2, RQ3).
  - *Closed-loop replay* (all four): each controller drives a simulated pot through the logged room conditions (RQ1 for C3, C4). Validated by replaying C1 and C2 against their real pots.
- **4.6 Hard cases.** About 40 near-threshold cases, each sent 3 times to C3 and C4 (stability).
- **4.7 Offline test.** One planned network cut; count answered cycles.

## 5. Metrics (about 0.4 page) -> `docs/metrics.md`
- **Table 4** (or three short lists): RQ1 precision (time in band, deviation, under/over-watering events, water, drainage); RQ2 reliability (accuracy with Wilson CI, kappa, water recall/precision, dose error, unsafe-proposal rate, valid JSON, stability); RQ3 cost (latency median/p90, cost per decision, offline availability).
- Optional, from Fig. 1's explain path: validator pass rate and code-fallback rate for C3 explanations; question-router accuracy on a small labelled set. TODO: keep or drop (adds work, but it is what the real system does).

## 6. Results (about 1.25 pages)
- **6.1 Precision (RQ1).** **Fig. 2:** moisture traces of the four controllers over the same days, band 60 to 90 shaded, waterings marked. **Table 5:** precision metrics. Sim-vs-real error for C1/C2.
- **6.2 Reliability (RQ2).** **Table 6:** routine cycles vs. hard cases, C1, C3, C4 vs. reference C2. Short error analysis: where Qwen fails (near threshold? after watering? invalid JSON?).
- **6.3 Cost (RQ3).** **Fig. 3:** kappa vs. median latency, point size = cost per decision. Offline-cut result.
- **6.4 (optional) Explanation layer.** Validator pass rate, fallback rate, router accuracy.
- Each subsection ends with the hypothesis verdict: H1/H2/H3 supported or not.

## 7. Discussion (about 0.5 page)
- What the numbers mean for a home grower: is a 0.8B model good enough to *decide*, or only to *explain*? Does this support Fig. 1's "code decides, AI explains" split?
- Cost and privacy vs. accuracy trade-off between C3 and C4.
- **Limitations:** one plant per real arm; 14 days; one species; LLMs evaluated in shadow and simulation, not on real plants; C2 is both controller and reference; simulator calibration; ChatGPT run after the fact.

## 8. Conclusion and Future Work (about 0.25 page)
- One-paragraph answer to the main RQ.
- Future: more jars (the pot holds up to six), longer runs, letting a validated model water under the gate, RAG over plant research.

## Acknowledgements
Course staff; the professor for the papers and API key. TODO.

## References -> `refs.bib`
[KAN25], [PAR26], plus 3 to 5 to add and verify.

## Appendix (if allowed)
- A: full system prompt (`experiment/prompt_system.txt`).
- B: full validator rules and question-router labels.
- C: hard-case list.

---

### Figures and tables at a glance
| # | What | Section | Source |
|---|---|---|---|
| Fig. 1 | System anatomy diagram | 3 | `figures/fig1_system_overview.png` |
| Fig. 2 | Moisture traces, 4 controllers | 6.1 | `replay_sim.py` + plot (TODO script) |
| Fig. 3 | Kappa vs. latency vs. cost | 6.3 | `metrics.py rq2/rq3` |
| Listing 1 | FACTS card + context JSON | 3.3 | logs |
| Table 1 | Bill of materials | 3 | team |
| Table 2 | Controllers | 4.2 | `config.json` |
| Table 3 | Frozen LLM settings | 4.3 | `config.json` |
| Table 4 | Metrics | 5 | `docs/metrics.md` |
| Table 5 | RQ1 results | 6.1 | `metrics.py rq1` |
| Table 6 | RQ2 results | 6.2 | `metrics.py rq2` |

### Conflicts between the diagram and the kit (to settle)
1. **Who waters.** Diagram: only rules reach the pump. 12 Nov plan: Qwen waters Pot B. This structure follows the diagram (decision card in the thread).
2. **Rule thresholds.** Diagram: soil <= 70 -> 100 mL, <= 25 -> 150 mL. Kit and plant research: < 60 -> refill toward 88, max 150 mL, 500 mL/day, 2 h gap. TODO: pick one and use it in the diagram, `config.json` and the paper.
3. **Sensors.** Diagram uses GY-BME280 (not DHT22), adds a YF-S401 flow meter, and names a Pi 5 4 GB. The paper text follows the diagram.
4. **"No cloud".** Diagram says no cloud; C4 (ChatGPT) runs only in the offline evaluation on logged data, never in the pot (stated in 4.2).
