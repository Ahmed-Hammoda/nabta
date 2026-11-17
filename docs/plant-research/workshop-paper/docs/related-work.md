# Related work (draft for paper section 2)

Full reading notes: `paper-notes.md`. PDFs: `../papers/`.

## Paragraph draft

Sensor-based irrigation with fixed soil-moisture thresholds is well established and saves water compared with timers, but the thresholds are rigid and give the grower no explanation. Recent work adds LLMs on top of IoT data. **CottonBot** [KAN25] combines retrieval-augmented generation over a cotton production guide with agentic tools that read field soil-moisture sensors and weather forecasts; it runs open-weight models locally with Ollama and compares seven of them (Llama 3.1 8B most faithful at 0.968, Phi-3 3.8B about twice as fast but less faithful). Its irrigation decision itself, however, is a deterministic 45 kPa rule, and the LLM only phrases it; no field trial with the system in the loop is reported. **Pardo-Pina et al.** [PAR26] propose an agent-based service architecture for a hydroponic greenhouse: a Raspberry Pi with Home Assistant at the edge, cloud GPT agents for chat, telemetry analysis and emergency classification, and a multi-step safety gate (range checks, schema validation, hard actuator limits, shadow mode, offline fallback). They evaluate on 40 questions and 36 synthetic emergency cases sent three times each (accuracy 0.81, stability 0.97), but only with OpenAI cloud models and without measuring irrigation outcomes.

**Gap.** Earlier systems either keep a fixed rule in charge and use the LLM only to explain it [KAN25], or rely on large cloud models behind a safety gate, whose errors cluster near thresholds [PAR26]. One paper compares only local models, the other only cloud models. No study has compared a sub-1B model running offline on edge hardware against both rule baselines and a cloud LLM on the watering decision itself, using the same live sensor inputs. Nabta does this with four controllers (single threshold, multi-rule, Qwen3.5 0.8B on a Raspberry Pi, ChatGPT), reusing [PAR26]'s safety gate, shadow evaluation and repeat-based recipe and [KAN25]'s local Ollama setup.

## What we borrow

| From | What | Where in our paper |
|---|---|---|
| [KAN25] | Ollama local models, model shortlist, latency reporting | Methods 3, Results |
| [PAR26] | Safety gate steps, shadow mode, 3 repeats + Wilson CI + stability, offline fallback | Methods 1 and 4, Metrics |

TODO: three more sources are now in `refs.bib` and `references.md` ([ELA26], [LIU26], [ABD26]). Their details are verified, but only the abstracts were read. Read them, then add them to the paragraph above. Note: [ELA26] puts a cloud LLM in the loop on real pots, so the "No study has compared..." sentence must stay precise (sub-1B, offline, vs. rules and cloud, same inputs). Still missing: a classic sensor-threshold irrigation source.
