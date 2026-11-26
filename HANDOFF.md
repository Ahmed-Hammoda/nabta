# Nabta: where the work stands (handoff, 26 Nov 2026)

Read this first when you continue on another computer. It holds what is not obvious from the code:
decisions, the state of the Raspberry Pi, and the open tasks.

## 1. The system today
- **Decisions:** rules v3 (`pi/rules_v3.py`, `simulation_phase2/RULES_v3.md`) decide the **pump** and the
  **grow light**, with the float switch (tank).
- **The model** (qwen3.5:0.8b in Ollama on the Pi) only **explains** each decision (prompt e3) and **chats**.
  Every explanation is checked by code (5 checks); if one fails, a code sentence is shown instead.
- **Always in code:** no 2nd watering within 3 h, max 3 a day, never on a reading older than 45 min,
  never when the tank is low.
- **Data saved every 30 min on the Pi:** `~/nabta/logs/YYYY-MM/model_io.jsonl` = the model's exact input
  (8 values) + the rules' answer (8 keys) + what the Pi did. Format: `pi/DATA_FORMAT.md`.

## 2. Hardware and wiring (tested 24 Nov 2026)
| Part | Connection | Tested |
|---|---|---|
| Raspberry Pi 4 (4 GB), official 5.1 V 3 A supply, 40 mm fan | fan on 5 V + GND | CPU 31–68 °C, never throttled |
| Soil probe → ADS1115 A0; BH1750; BME280 | I²C (pins 3, 5), 3.3 V | calibrated: air 16,700 → 0, water 7,886.8 → 100 |
| **Float switch** | **GPIO 17 (pin 11)** + **GND (pin 20)** | float UP = 1, **DOWN = 0** → `FLOAT_LOW_VALUE = 0` |
| **2-relay board** (switches ON when IN is LOW) | VCC 5 V, GND pin 14, IN1 = GPIO 23 (pin 16), IN2 = GPIO 24 (pin 18) | both click |
| **Pump** | on relay **K2 → GPIO 24** (`PUMP_PIN = 24`); powered by a bench supply at 5 V via COM/NO | runs; **25 mL/s** (6 s = 150 mL cup test) |
| Grow light (USB strip, CoThings) | planned on relay **K1 → GPIO 23** via a USB socket | not connected yet |

Wiring page: `docs/designs/nabta_wiring_3d.html` (K2 = pump, K1 = light).

## 3. Settings on the Pi now (`~/nabta/nabta_controller.py`)
`USE_MODEL = True`, `PUMP_ENABLED = False`, `LIGHT_ENABLED = False`, `PUMP_SECONDS = 3` (≈ 75 mL),
`RELAY_ACTIVE_LOW = True`, `BLOCK_WHEN_TANK_LOW = True`, `DECIDER = "rules"`, light target 225,000 lux-h.
Backups on the Pi: `~/nabta_backup_20261124_0038`, `~/nabta_backup_20261124_0123`.

## 4. Decisions made (and why)
- Rules decide, the model explains: no small model decided safely (phase 2: best 63 % both-correct and it
  watered a broken sensor; 25/35 runs below "do nothing").
- Light target 285,000 → **225,000 lux-h** (mint grows best ≈ 15 mol/m²/day) and dose 150 → **75 mL**
  (FAO-56 p = 0.40 on ≈ 0.65 L of soil): `simulation_phase2/WATER_AND_LIGHT_CHECK.md` (references W1–W16).
- Flow sensor (YF-S401) dropped: water is dosed by pump time.
- Paper removed from GitHub for now (on purpose). It is only on the old laptop: `test models/paper/`.

## 5. Model test on the Pi (24 Nov 2026, `simulation_phase2/results/pi_model_test/`)
- Explanations: **18/20 passed** the checks; the 2 failures (dry soil + low light → "bring the pot inside",
  a fake cold alert) were caught. Every answer gave the right action, no invented numbers.
- Speed: **32 s per explanation** (first load 90 s). Chat: 25–126 s per answer (slow).
- Temperature: max **68.1 °C**, no throttling.
- Script: `pi/tools/pi_model_test.py` (saves every result to `~/nabta/logs/model_tests/` as it goes).

## 6. Open tasks (in order)
1. **Fix the chat:** it says "watering now" when the pump is in WAIT/HOLD/BLOCKED or disabled. Use the
   controller's message when the pump action is WAIT/HOLD/BLOCKED; add "(pump not connected yet)" while
   `PUMP_ENABLED = False`. Re-run the 6 chat questions.
2. **Place the system:** probe in the jar's soil (it reads 6–16 now = not in moist soil), gravel layer in
   the jar, float in the tank (drops at ≈ 1 L), tube end at the soil surface, jar rim above the tank water.
3. **Field-capacity test** (1 s = 25 mL steps, 10 min apart) → set the real watering limit and dose.
4. **Enable the pump** (`PUMP_ENABLED = True`) once 2–3 are done.
5. Optional: flip the float on its stem (fail-safe: a broken wire then reads "tank low") → `FLOAT_LOW_VALUE = 1`.
6. Buy a 1N4007 diode (across the pump, stripe on +).
7. Grow light: USB socket on relay K1 (GPIO 23), then `LIGHT_ENABLED = True`; measure the LED lux at the
   plant (the simulator assumes `LED_LUX = 3000`).
8. Collect ≈ 1 week of real data → tune the simulator (drying speed, watering jump, LED lux) → rebuild the
   training data → fine-tune in Colab (dry run first; `simulation_phase2/finetune/README.md`) → test on
   real days → "model decides, rules check" mode.
9. Make the chat faster (fewer model calls per question).
10. App (`app/`): uses example data with a 40–70 % target that does not match the rules (water at ≤ 70);
    needs a small server on the Pi to show real data.
11. Report/paper: add teammates' names; the paper still says Pi 5 (it is a Pi 4).

## 7. Setting up a new laptop
1. `git clone https://github.com/Ahmed-Hammoda/nabta.git`
2. Python 3 with `numpy` (simulator); for the app: Node.js LTS, then `cd app && npm install`.
3. Ollama (for the laptop tests): `ollama pull qwen3.5:0.8b`. `nabta-base` (only for the fine-tune
   comparison): `simulation_phase2/finetune/README.md`, step 3.
4. Report: MiKTeX (pdflatex) to rebuild `docs/report/nabta_report.tex`.
5. **SSH to the Pi** (user `footsteps`, `192.168.1.27`, same Wi-Fi). The old laptop's private key is NOT in
   this repo (never put keys on GitHub). On the new laptop:
   ```
   ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\id_ed25519_nabta_pi
   type $env:USERPROFILE\.ssh\id_ed25519_nabta_pi.pub | ssh footsteps@192.168.1.27 "cat >> ~/.ssh/authorized_keys"
   ```
   (the second command asks for the Pi password once), then add to `$env:USERPROFILE\.ssh\config`:
   ```
   Host nabta-pi
       HostName 192.168.1.27
       User footsteps
       IdentityFile ~/.ssh/id_ed25519_nabta_pi
       IdentitiesOnly yes
   ```
   Test: `ssh nabta-pi`.
