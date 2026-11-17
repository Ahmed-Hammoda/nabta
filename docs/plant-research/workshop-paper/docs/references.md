# All references (collected 16 Nov 2026)

Every source the team has used since October, in one list. BibTeX keys are in `paper/refs.bib`. "Verified" = title, authors and venue checked on the publisher or arXiv page on 16 Nov 2026. Where it came from: repo `docs/plant-research/references.md` and `related-work.md` (PR #4), the 31 Oct research doc, and the professor's papers.

| Key | Reference | Status | Cited in the paper for |
|---|---|---|---|
| KAN25 | Kandamali et al. 2025, CottonBot, *Smart Agric. Tech.* 12:101640 | verified | rule decides, local LLM explains |
| PAR26 | Pardo-Pina et al. 2026, agent-based greenhouse, *Smart Agric. Tech.* 13:101872 | verified | safety gate, shadow mode, 3-repeat recipe |
| ELA26 | ElAlaoui et al. 2026, sensor-grounded LLM potato irrigation, *AgriEngineering* 8(11):468 | verified | closest work: cloud GPT-5 advises irrigation from live sensors |
| MIM26 | Liu et al. 2026, Mimir, arXiv:2610.02038 | verified | bigger LLM not steadily better (simulation) |
| PARK26 | Park et al. 2026, AquaAgent-OSPy, *Comput. Electron. Agric.* 254:112267 | verified | LLM recommends, human approves |
| ZHA24 | Zhang et al. 2024, LLMs for explainable decisions in digital twins, arXiv:2405.14411 | verified | LLM as explanation layer |
| LEE25 | Lee et al. 2025, SPADE, arXiv:2509.18123 | verified | LLM reads soil-moisture series |
| AGA24 | Agarwal et al. 2024, IoT plant health with LLMs, arXiv:2409.15910 | verified | LLM explains plant data, cloud only |
| YAM25 | Yamaguchi et al. 2025, Agentic XAI for rice, arXiv:2512.21066 | verified | explanation rubric |
| LEAF26 | Abdulkadhim and Repas 2026, LEAF, *MAKE* 8(2):48 | verified | small models timed on Pi 4/5 |
| NEZ24 | Nezami et al. 2024, Generative AI on the edge, arXiv:2411.17712 | verified | Pi 5 speed 5–12 tokens/s |
| JAN25 | Jang and Morabito 2025, Edge-first LM inference, arXiv:2505.16508 | verified | edge vs. cloud trade-offs |
| STRAT | Stratosphere Lab, Raspberry Pi 5 LLM benchmark (web) | web page | Pi 5 speeds per model |
| CAR10 | Cardenas-Lailhacar et al. 2010, *J. Irrig. Drain. Eng.* 136(3) | title/venue verified; check initials, pages | sensor vs. timer savings |
| MON18 | Montesano et al. 2018, sensor irrigation of soilless basil, *Agric. Water Manag.* 203:20–29 | verified | set-point watering of a potted herb |
| TAU26 | Taueatsoala et al. 2026, TinyML precision irrigation, arXiv:2601.13054 | verified | edge irrigation, classical ML |
| BER26 | Bera et al. 2026, ensemble soil moisture, *Front. IoT* 5:1870523 | verified | edge irrigation, classical ML |
| KUN25 | Kunt 2025, smart autonomous irrigation, arXiv:2506.11835 | verified | ESP32 + LSTM student project |
| OKW11 | Okwany et al. 2011, deficit irrigation of spearmint, *Irrig. Sci.* | verified (add volume/pages) | spearmint water response |
| UGA07, UGA13 | UGA press releases, greenhouse and nursery sensor watering | press release | replace with journal papers |
| MAS25, NAB25, GON23 | Plantbot, Tracking Anyplant, soil drydown changepoints (arXiv) | TODO verify | not cited yet |
| WSU14, ZAN, AGR19, FUM | Spearmint and herb deficit studies | TODO verify | FUM cited (growth below field capacity) |
| NSW, OMAFRA, ISWS, UCCF, PG, VT, LF, W2T | Extension and climate web pages | web pages | spearmint needs, threshold, Tunis climate |
| HD, CG22, CLEM, SAS, OTT | Plant-choice sources (basil, tomato, pothos, succulents, mint tea) | web pages | not in the paper |
| DS_MEN, DS_LEC, DS_GAL, DS_SIM, DS_PP, DS_TS | Public datasets | web | optional, if we test on public data |
| MYCODO, TOMATO, GARDYN, CLICKGROW, LETPOT, MIFLORA | Open-source projects and products | web | optional, "existing solutions" |
| PARK26 vs PAR26 | note: PARK26 = Park (AquaAgent), PAR26 = Pardo-Pina | | |
