# Methods (v3, 16 Nov 2026: four controllers, only rules reach the pump)

v3 change: following the system diagram (`paper/figures/fig1_system_overview.png`), the pump is driven only by rules. Pot A = C2, Pot B = C1. Qwen (C3) and ChatGPT (C4) are evaluated in shadow mode and closed-loop replay. In the deployed system Qwen only explains (FACTS card, validator, question router).

Anything marked **TODO** still needs the team to confirm.

## 0. Research question and hypotheses

**Research gap.** Earlier LLM irrigation systems either keep a fixed rule in charge and use the LLM only to explain it (CottonBot [KAN25]), or use large cloud models behind a safety gate ([PAR26], whose GPT models made errors close to thresholds). No study has compared a sub-1B model running offline on edge hardware against both rule baselines and a cloud LLM on the watering itself, using the same live sensor inputs.

**Main RQ.** To what extent does the type of decision controller affect irrigation precision, decision reliability and operational cost when four controllers act on the same real-time sensor data from a potted spearmint plant?

- **RQ1 (precision).** How does the controller type affect the share of time soil moisture stays in the 60 to 90 target band, the number of under- and over-watering events, and total water use?
- **RQ2 (reliability).** How do the two LLM controllers differ from the rule-based reference in decision agreement (accuracy, Cohen's kappa), recall of needed waterings, rate of unsafe proposals blocked by the safety gate, and answer validity, on routine cycles and on near-threshold cases?
- **RQ3 (cost).** How do the controllers differ in decision latency, cost per decision and availability without internet?

**Variables.** Independent: controller (4 levels). Dependent: the RQ1 to RQ3 metrics (`metrics.md`). Controlled: same sensor context, same safety gate, and for both LLMs the same frozen prompt and settings.

**Hypotheses.**
- **H1.** C2 (multi-rule) keeps moisture in band longer and uses less water than C1 (single threshold).
- **H2.** C4 (cloud LLM) agrees with the reference more often than C3 (Qwen3.5 0.8B), especially near the thresholds.
- **H3.** C3 has lower decision accuracy than C4, but zero cost per decision and full availability offline.

## 1. System

| Part | Choice |
|---|---|
| Plant | Spearmint (*Mentha spicata*), 2 real pots, same cutting batch, soil and pot size |
| Sensors per pot | Capacitive soil moisture via ADC (ADS1115 or ESP32 over USB), read every 30 s, 5-min median = moisture index 0 to 100 |
| Shared sensors | GY-BME280 temperature/humidity, BH1750 light, YF-S401 flow meter, tank level |
| Edge computer | Raspberry Pi 5, 4 GB, everything offline |
| Actuator | 5 V relay + one pump per jar from a shared 4 L tank; dose measured by the flow meter |
| Light | LED grow light 14 h/day |
| Decision cycle | 30 min (TODO confirm) |

### The four controllers (`experiment/controllers.py`)

| ID | Controller | Logic | Runs where | How it is evaluated |
|---|---|---|---|---|
| C1 | Single threshold | index < 60 -> 150 mL. No dose sizing, no daily cap, no gap, no tank or fault check | Pi | **Real Pot B** + closed-loop replay |
| C2 | Multi-rule | index < 60 -> refill toward 88, max 150 mL per watering, 500 mL/day, 2 h gap, skip if tank low or sensor fault | Pi | **Real Pot A**; also the **reference** for RQ2 |
| C3 | Qwen3.5 0.8B | LLM reads the context and returns `{"action","ml","reason"}` | Pi, offline (Ollama) | Shadow mode + closed-loop replay |
| C4 | ChatGPT (cloud) | same prompt and settings as C3 | OpenAI API | Replay on logged contexts once the professor gives the key |

**Safety gate** (same code for all): blocks watering if the tank is low, the index is >= 90, the last watering was < 2 h ago, or the daily 500 mL is reached; clips any dose to 150 mL; invalid JSON or no answer = no water. Default: the gate is applied to C2, C3, C4, and **not** to C1, so C1 stays a true naive baseline; for C1 the gate is still evaluated and its "would block" decisions are logged. TODO(team): confirm, or set `gate.apply_to_threshold: true` in `config.json`.

### Listing 1: live context sent to every controller

```json
{
  "timestamp": "2026-11-20T14:30:00", "pot": "B",
  "plant_profile": {"water_below_index": 60, "refill_to_index": 88, "dose_cap_ml": 150, "day_cap_ml": 500, "min_gap_h": 2},
  "latest": {"soil_index_median_5min": 61.2, "air_temp_c": 21.4, "air_rh_pct": 48, "light_lux": 14000,
             "tank_low": false, "sensor_fault_flag": null},
  "history_24h_hourly_index": [80.7, 79.4, "..."],
  "last_watering": {"hours_ago": 9.5, "ml": 150},
  "given_today_ml": 150, "time_of_day": "afternoon"
}
```

## 2. Frozen LLM settings (C3 and C4 identical)

| Parameter | Value |
|---|---|
| System prompt | `experiment/prompt_system.txt`, frozen on day 0 |
| temperature / top_p | 0 / 1 |
| max_tokens | 200 |
| seed | 42 (where supported) |
| context window | 4096 |
| Output | JSON only, invalid = error, no retries |
| Local quantisation | Ollama default (Q4_K_M) |
| Timeout | 120 s = no answer |

## 3. Procedure

1. **Calibration (before day 0):** sensor dry/wet values per pot, pump flow (mL/s), pot weight at container capacity, plant-available water (mL) for the simulator.
2. **Days 1 to 14 (TODO dates):** Pot A on C2, Pot B on C1. Every cycle the Pi logs the context of both pots (`logs/contexts.jsonl`), the readings, and the waterings. Swap pot positions every 4 days. Daily by hand: pot weight, wilting score 0 to 4, photo.
3. **Open-loop decisions (RQ2, RQ3):** every logged context is given to all four controllers (`llm_decide.py --replay`). C4 runs this after the key arrives; the inputs are the same, so it stays fair.
4. **Closed-loop replay (RQ1):** `replay_sim.py` gives each controller its own simulated pot that lives through the logged room conditions (temperature, humidity, light, tank). Water balance and plant water use come from `tools/nabta_simulate.py`, calibrated in step 1. A flagged sensor glitch is injected at the same times for every controller. **Validation:** replay C1 and C2 too and compare with real Pots B and A (mean absolute error of the moisture index); report it.
5. **Hard cases (RQ2):** about 40 cases near the thresholds (index 55 to 65, just after a watering, tank low, daily cap reached, sensor glitch), from the logs and the simulator, mark `"hard_case": true`; each sent 3 times to C3 and C4 for stability ([PAR26] recipe). Two team members check the C2 label of each case.
6. **Offline test (RQ3):** one planned network cut (e.g. 6 h) during the run; count cycles each controller could answer.

## 4. Threats to validity
- One real pot per real arm: a paired case study, not a significance test.
- C1 and C4 are compared in simulation; the sim-vs-real error of C2/C3 bounds how much to trust that.
- C2 is both a controller and the RQ2 reference; RQ1 metrics do not depend on C2, so they can show a model doing better than the rules.
- The safety gate hides unsafe LLM proposals from the plant; their rate is reported, not hidden.
- ChatGPT runs after the fact on logged contexts, so its latency is measured at replay time.
