# Nabta on the Raspberry Pi 4 (`~/nabta`)

The rules decide the watering; qwen3.5:0.8b explains the decision and answers questions.
- The **pump is OFF** (`PUMP_ENABLED = False` in `nabta_controller.py`).
- The **model is OFF** in the controller (`USE_MODEL = False`) until the Pi has cooling. Messages
  are then written by the code.

## Files
| File | What it is |
|---|---|
| `garden_logger.py` | Your friend's sensor logger: one raw row every 10 s, one averaged row every 30 min (changed only to use the monthly `logs/` folders) |
| `soil_calibration.json` | Soil calibration, 17 Nov 2026: dry air 16,700, water 7,886.8 (air = 0, water = 100) |
| `nabta_paths.py` | Where every file lives (one place for all scripts) |
| `live_view.py` | Live view of the sensors, read only |
| `rules_v2.py`, `labels.py` | Rules v2: fault check, levels, decision, alerts (see RULES_v2.md) |
| `explain_bench.py` | Tested explanation prompt e3 (phase 1), used by the controller |
| `chat_bench.py`, `chat_v3.py` | Tested chat v3.1 code (phase 1), used by the chat |
| `nabta_controller.py` | For each new 30-min row: fault check → rules decision → pump safety → message |
| `nabta_chat.py` | Chat in the terminal, answers from the latest decision |

## The logs folder
```
logs/
├── 2026-11/
│   ├── raw_log.csv        one row every 10 s (about 0.5 MB a day)
│   ├── log_30min.csv      one row every 30 min; "samples" = readings averaged (180 = a full 30 min)
│   └── decisions.csv      one decision per 30-min row
├── 2026-12/ ...           a new folder only when a new month starts
├── events.csv             every start and stop of the logger and controller (gaps = Pi off)
├── controller_state.json  controller memory: last row done, recent waterings (3-hour wait)
└── old_calibration/       your friend's logs of 15 Nov (old calibration: do not mix)
```
- **Off and on again:** no new files. The scripts append to the current month's files.
- **Raw logs older than 3 months** are compressed (`raw_log.csv.gz`). The 30-min and decision files
  are kept as they are (about 100 KB a month).
- **After a restart:**
  - The logger rebuilds the 24 h light total from the raw logs.
  - The first 30-min row is shorter: its `samples` value is below 180.
  - The controller goes on after the last row it handled.
  - A reading is compared with the previous one only if that one is at most 45 min older, so a gap
    can't cause a false sensor or pump fault.
  - A row more than 45 min old is recorded but **never** causes watering.

## Commands
```
cd ~/nabta
python3 live_view.py                         # watch the sensors (Ctrl+C to stop)
python3 nabta_chat.py                        # ask questions (needs the model)
tail -n 5 logs/$(date +%Y-%m)/decisions.csv  # the last decisions
cat logs/events.csv                          # starts and stops
```
The logger and the controller start by themselves when the Pi turns on:
```
systemctl status nabta-logger nabta-controller          # are they running?
journalctl -u nabta-controller -f                        # live controller output (Ctrl+C to stop)
sudo systemctl restart nabta-logger nabta-controller     # restart after a change
sudo systemctl stop nabta-logger nabta-controller        # stop both (for calibration or tests)
```
`live_view.py` and `garden_logger.py --calibrate` read the same sensors as the logger. Stop the logger
before you calibrate.

**Turn the Pi off with `sudo shutdown now`**, then unplug it. Every row is written to disk at once,
but pulling the plug can still damage the SD card.

## Pump safety (when the pump is connected)
- Water only if soil is 70 or below **and** there is no sensor fault.
- No second watering within 3 hours; at most 3 waterings a day; never on an old reading.
- To switch the pump on, set `PUMP_ENABLED = True` and `RELAY_PIN` (BCM number) in
  `nabta_controller.py`. Measure how many mL one run of `PUMP_SECONDS` gives, then restart the controller.
