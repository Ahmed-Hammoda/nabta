#!/usr/bin/env python3
"""
Closed-loop replay: put each controller in charge of a SIMULATED pot that lives through the
SAME logged room conditions (temperature, humidity, light, tank) as the real pots. This is how
C1 (threshold) and C4 (ChatGPT) get RQ1 precision numbers without a third and fourth real pot,
and how C2/C3 are checked: their simulated trace should match the real Pot A/B trace
(report the sim-vs-real error as a calibration check).

  python3 replay_sim.py --env ../data/sample/readings.csv --env-pot A --days 14 --mock
  python3 replay_sim.py --env ../logs/readings.csv --env-pot A --controllers C1,C2,C3,C4

Writes <out>/<id>_readings.csv and <id>_waterings.csv (same columns metrics.py rq1 reads).
Water balance and plant water use come from tools/nabta_simulate.py (assumed 600 mL available
water, 140 mL/day). TODO: replace with the calibration values measured on the real pots.
"""
import argparse, csv, json, random, statistics, sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import nabta_simulate as S  # noqa: E402
import controllers as C      # noqa: E402
from llm_decide import load_config  # noqa: E402


def load_env(path, pot):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            if r.get("pot", pot) != pot:
                continue
            rows.append((datetime.fromisoformat(r["timestamp"]), float(r["air_temp_c"]), float(r["air_rh_pct"]),
                         float(r["light_lux"]), r.get("tank_low", "0") in ("1", "True", "true")))
    return rows


def run(ctrl, cfg, env, start_index, noise_sd, fault_rate, rng, mock, outdir, log):
    prof = cfg["plant_profile"]
    awc = prof["pot_awc_ml"]
    water = awc * start_index / 100
    t0 = env[0][0]
    step_h = (env[1][0] - env[0][0]).total_seconds() / 3600
    every = max(1, round(cfg["cycle_minutes"] / 60 / step_h))
    frng = random.Random(1234)  # same fault times for every controller
    hist, last_w, day, given_today, pending = [], None, None, 0.0, 0.0
    rd = open(outdir / f"{ctrl['id']}_readings.csv", "w", newline="")
    wt = open(outdir / f"{ctrl['id']}_waterings.csv", "w", newline="")
    rw, ww = csv.writer(rd), csv.writer(wt)
    rw.writerow(["timestamp", "pot", "soil_index", "soil_index_sensed", "drained_ml"])  # soil_index = true state
    ww.writerow(["timestamp", "pot", "ml", "index_before", "gate"])
    for i, (t, temp, rh, lux, tank_low) in enumerate(env):
        if t.date() != day:
            day, given_today = t.date(), 0.0
        drained = 0.0
        water += pending; pending = 0.0
        if water > awc:
            drained, water = water - awc, awc
        idx_true = 100 * water / awc
        water = max(0.0, water - S.et_ml(step_h, temp, rh, lux, idx_true, (t - t0).total_seconds() / 86400))
        idx = round(min(100, max(0, 100 * water / awc + rng.gauss(0, noise_sd))), 1)
        fault = None
        if frng.random() < fault_rate:      # sensor glitch reading ~30 points too dry; the Pi's
            idx, fault = max(0.0, round(idx - 30, 1)), "spike"   # health check flags it
        hist.append((t, idx))
        rw.writerow([t.isoformat(), ctrl["id"], round(100 * water / awc, 1), idx, round(drained, 1)])
        if i % every:
            continue
        hourly = [v for tt, v in hist if tt >= t - timedelta(hours=24) and tt.minute == 0]
        ctx = {"timestamp": t.isoformat(), "pot": ctrl["id"],
               "plant_profile": {k: prof[k] for k in ("water_below_index", "refill_to_index", "dose_cap_ml", "day_cap_ml", "min_gap_h")},
               "latest": {"soil_index_median_5min": idx, "air_temp_c": round(temp, 1), "air_rh_pct": round(rh, 1),
                          "light_lux": int(lux), "tank_low": tank_low, "sensor_fault_flag": fault},
               "history_24h_hourly_index": hourly[-24:],
               "last_watering": ({"hours_ago": round((t - last_w[0]).total_seconds() / 3600, 2), "ml": last_w[1]} if last_w else None),
               "given_today_ml": given_today,
               "time_of_day": "night" if t.hour < 6 or t.hour >= 21 else "morning" if t.hour < 12 else "afternoon" if t.hour < 17 else "evening"}
        rec = C.decide(ctrl, cfg, ctx, rng, mock)
        rec.update(timestamp=ctx["timestamp"], mode="closed_loop")
        log.write(json.dumps(rec) + "\n")
        if rec["final_action"] == "water" and rec["final_ml"] > 0:
            ml = float(rec["final_ml"])
            water += 0.6 * ml; pending += 0.4 * ml   # same spreading as the simulator
            last_w, given_today = (t, ml), given_today + ml
            ww.writerow([t.isoformat(), ctrl["id"], ml, idx, rec["gate"] or ""])
    rd.close(); wt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--env", required=True, help="readings CSV with timestamp,air_temp_c,air_rh_pct,light_lux[,tank_low,pot]")
    ap.add_argument("--env-pot", default="A")
    ap.add_argument("--days", type=float, default=0, help="limit to the first N days (0 = all)")
    ap.add_argument("--start-index", type=float, default=80)
    ap.add_argument("--noise-sd", type=float, default=0.8, help="sensor noise, index points")
    ap.add_argument("--fault-rate", type=float, default=0.003, help="chance per reading of a flagged sensor glitch")
    ap.add_argument("--controllers", default="")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--out", default=str(HERE.parent / "results" / "replay"))
    a = ap.parse_args()
    cfg = load_config(a.config)
    env = load_env(a.env, a.env_pot)
    if a.days:
        env = [e for e in env if e[0] < env[0][0] + timedelta(days=a.days)]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    ctrls = [c for c in cfg["controllers"] if not a.controllers or c["id"] in a.controllers.split(",")]
    with open(out / "closed_loop_decisions.jsonl", "w") as log:
        for c in ctrls:
            run(c, cfg, env, a.start_index, a.noise_sd, a.fault_rate, random.Random(42), a.mock, out, log)
            print("done", c["id"])
    print("wrote", out)


if __name__ == "__main__":
    main()
