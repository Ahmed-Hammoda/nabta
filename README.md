# Nabta: an AI smart pot for spearmint

Nabta looks after one jar of spearmint. Sensors measure the soil, light, air temperature and humidity. A Raspberry Pi 4 decides when to water and which alerts to raise using fixed rules. A small local language model (qwen3.5:0.8b in Ollama) explains each decision in plain words and answers questions in a chat. Nothing needs the internet.

**The rules decide; the model only explains.** In our tests the rules were right in every case. The best small model deciding on its own was not reliable enough to control the pump.

## What is in this repo

| Folder | What it holds |
|---|---|
| [`pi/`](pi/) | The code that runs on the Raspberry Pi: sensor logger, rules, controller, chat, systemd services, soil calibration. Start with [`pi/README.md`](pi/README.md). |
| [`app/`](app/) | The phone app (Expo / React Native). Sensor data is simulated until the Pi server is ready. See [`app/README.md`](app/README.md). |
| [`cad/sensor_stake/`](cad/sensor_stake/) | 3D-printed sensor stake, new hexagon design (STEP parts, print notes). |
| [`cad/plexiglass_hexagon/`](cad/plexiglass_hexagon/) | Laser-cut plexiglass hexagon (DXF, SVG). |
| [`docs/diagrams/`](docs/diagrams/) | System diagram (PNG + PSD source, with photo credits) and the interactive system map. |
| [`docs/designs/`](docs/designs/) | Interactive 3D pages: the breadboard wiring and the prototype box with the printed light holder (all sizes in mm). |
| [`docs/project_overview/`](docs/project_overview/) | Bills of materials and the early build simulators. |
| [`docs/team_notes/`](docs/team_notes/) | Notes for team members (app, sensors). |
| [`paper/`](paper/) | The paper (coming soon). |
| [`simulation_phase1/`](simulation_phase1/) | First model tests: decision, explanation and chat benchmarks. |
| [`simulation_phase2/`](simulation_phase2/) | Rules v2, the 30-day simulated dataset, the 35-run model comparison, thinking-mode tests, training data and the fine-tuning notebook. |

Open the `.html` pages in `docs/` with any browser. The 3D pages need an internet connection to load their 3D library.

## How it works

```
Soil probe ─► ADS1115 ─┐
BH1750 (light) ────────┼─ I²C ─► Raspberry Pi 4
BME280 (air) ──────────┘          │
                                  ├─ garden_logger.py   one reading every 10 s, one averaged row every 30 min
                                  ├─ nabta_controller.py rules v2: faults → water yes/no → alerts → pump safety
                                  │                      the model writes the explanation (code text if it is off)
                                  ├─ nabta_chat.py       questions answered from the latest decision
                                  └─ relay ─► pump (K1, GPIO 23) and grow light (K2, GPIO 24)
Float switch (tank low) ─► GPIO 17
```

The relay, pump, grow light and float switch wiring is planned (see `docs/designs/nabta_wiring_3d.html`) and not yet in the Pi code.

- Water when the soil index is 70 or below, with no sensor fault. At most one watering every 3 hours and 3 a day.
- Soil index: `(16700 − raw) / (16700 − 7886.8) × 100`, limited to 0–100 (air = 0, water = 100).
- All readings and decisions are saved in monthly folders on the Pi: `logs/YYYY-MM/`.

## Quick start

**Raspberry Pi** (Raspberry Pi OS, I²C on):

```
scp -r pi/ <user>@<pi-address>:~/nabta
ssh <user>@<pi-address>
cd ~/nabta && python3 live_view.py        # check the sensors
```

The systemd service files are in `pi/services/`. Details and safety settings: [`pi/README.md`](pi/README.md).

**Phone app:**

```
cd app
npm install
npx expo start
```

## Status

- Working on the Pi: sensor logging, calibration, rules, decisions, monthly logs that survive power cuts.
- The model stays off on the Pi (`USE_MODEL = False`) until the fan and the 5 V 3 A supply are fitted. It overheated during the first test.
- The pump stays off (`PUMP_ENABLED = False`) until the relay and pump are wired and the dose time is measured.
- Fine-tuning qwen3.5:0.8b is prepared (`simulation_phase2/finetune/`) but not run yet.
- The app uses simulated data until the Pi serves real data.
