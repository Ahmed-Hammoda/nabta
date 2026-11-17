#!/usr/bin/env python3
"""
Nabta dummy-data generator (standard library only, runs on a Raspberry Pi or a laptop).

Simulates the two study pots from 9 Nov to 4 Dec 2026, one row every 5 minutes:
  - Pot A: watered by the Nabta rules engine (water below 60, refill toward 88,
           max 150 mL per watering, max 500 mL per day, at least 2 h between waterings,
           blocked if the tank is low)
  - Pot B: fixed schedule (every 2 days at 09:00, fixed dose)

The physics is a simple daily water balance of the kind used in FAO-56:
water leaves the pot through evapotranspiration (driven by light, temperature and
air dryness, and reduced when the soil gets dry), arrives only through the pump,
and anything above container capacity drains out of the pot. The sensor layer adds
noise, a capacitive-sensor raw value, and labelled faults (spike, stuck, dropout)
so the health checks can be tested.

All defaults come from docs/plant-research (thresholds-and-calibration.md) and the
"Sensor readings for the watering decision" doc. They are STARTING values: replace
them with the numbers measured during the calibration week (2 to 8 Nov).

Outputs (in --out, default ./sim_out):
  readings.csv            one row per pot per 5 min: what the Pi would log
  waterings.csv           every pump run with mL, reason code and moisture before/after
  daily_summary.csv       water given, drained and used per pot per day (RQ1 preview)
  decision_contexts.jsonl the context the backend would send to the LLM for each
                          Pot A decision worth explaining (watering, skip, alert),
                          with the rules engine's decision as ground truth (RQ2 tests)

Usage:
  python3 nabta_simulate.py                       # default study period, seed 42
  python3 nabta_simulate.py --seed 7 --days 10    # shorter run, other weather
  python3 nabta_simulate.py --potb-dose 250       # change the Pot B schedule dose
"""
import argparse
import csv
import json
import math
import os
import random
from datetime import datetime, timedelta

STEP_MIN = 5

# ---- plant and pot (starting values, see docstring) -------------------------
AWC_ML = 600.0          # plant-available water in a 2-3 L pot, mL (index 0 -> 100)
BASE_ET_ML_DAY = 140.0  # mint water use per day at 18 C, 50 % RH, 14 h LED (assumed)
ET_GROWTH_PER_DAY = 0.01  # plants grow, so water use rises ~1 % per day
STRESS_INDEX = 40.0     # below this the plant closes stomata, ET falls linearly

# ---- rules engine (Pot A) ----------------------------------------------------
WATER_BELOW = 60.0
REFILL_TO = 88.0
DOSE_CAP_ML = 150.0
DAY_CAP_ML = 500.0
MIN_GAP_H = 2.0
HARD_BLOCK_ABOVE = 90.0
LOW_ALARM = 40.0
HIGH_ALARM = 95.0

# ---- tank ---------------------------------------------------------------------
TANK_ML = 5000.0
TANK_LOW_ML = 500.0

# ---- capacitive sensor (raw ADC counts, 12-bit-like) ----------------------------
RAW_DRY = 3000          # sensor in dry mix (index 0)
RAW_WET = 1300          # sensor at container capacity (index 100)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


class Weather:
    """Indoor room in Tunis, Nov-Dec: cool, slowly cooling, LED grow light 06:00-20:00."""

    def __init__(self, rng, start):
        self.rng = rng
        self.start = start
        self.day_offset = 0.0     # day-to-day random walk of room temperature
        self.cloud = 0.5          # 0 sunny .. 1 overcast, changes daily
        self.last_day = None

    def at(self, t):
        day = t.date()
        if day != self.last_day:
            self.last_day = day
            self.day_offset = clamp(self.day_offset + self.rng.gauss(0, 0.8), -3, 3)
            self.cloud = clamp(self.rng.random() ** 0.7, 0, 1)
        days_in = (t - self.start).total_seconds() / 86400
        h = t.hour + t.minute / 60
        # room temperature: 18.5 C mean, cooling ~2 C over the study, peak ~15:00
        temp = 18.5 - 2.0 * days_in / 26 + self.day_offset + 2.5 * math.sin(2 * math.pi * (h - 9) / 24)
        temp += self.rng.gauss(0, 0.15)
        rh = clamp(58 - 2.0 * (temp - 18) + 8 * self.cloud + self.rng.gauss(0, 1.0), 30, 90)
        led_on = 6 <= h < 20
        lux = 14000.0 if led_on else 0.0
        # window daylight on top, 07:00-17:00, less on cloudy days
        if 7 <= h < 17:
            lux += (1 - 0.8 * self.cloud) * 3000 * math.sin(math.pi * (h - 7) / 10)
        lux = max(0.0, lux * (1 + self.rng.gauss(0, 0.03)))
        return temp, rh, lux, led_on


def et_ml(step_h, temp, rh, lux, index, days_in):
    """Water lost by one pot in this step (mL)."""
    light_frac = min(lux / 14000.0, 1.2)
    vpd_factor = (1 - rh / 100) / 0.5                 # 1.0 at 50 % RH
    temp_factor = 1 + 0.05 * (temp - 18)
    day_share = 0.25 + 0.75 * light_frac               # night ET is ~25 % of day ET
    stress = 1.0 if index >= STRESS_INDEX else max(index, 0) / STRESS_INDEX
    growth = 1 + ET_GROWTH_PER_DAY * days_in
    # normalise so that a standard day gives BASE_ET_ML_DAY
    per_hour = BASE_ET_ML_DAY / (14 * 1.0 + 10 * 0.25)
    return max(0.0, per_hour * step_h * day_share * vpd_factor * temp_factor * stress * growth)


class Sensor:
    """Capacitive moisture sensor with noise and labelled faults."""

    def __init__(self, rng, fault_rate):
        self.rng = rng
        self.fault_rate = fault_rate
        self.stuck_left = 0
        self.stuck_raw = None
        self.dropout_left = 0

    def read(self, true_index):
        raw = RAW_DRY - (RAW_DRY - RAW_WET) * (clamp(true_index, 0, 100) / 100) ** 0.9
        raw += self.rng.gauss(0, 12)
        fault = ""
        if self.dropout_left > 0:
            self.dropout_left -= 1
            return None, None, "dropout"
        if self.stuck_left > 0:
            self.stuck_left -= 1
            raw, fault = self.stuck_raw, "stuck"
        else:
            r = self.rng.random()
            if r < self.fault_rate:
                fault = "spike"
                raw -= 500                      # reads ~+30 index for one sample
            elif r < 2 * self.fault_rate:
                self.stuck_left, self.stuck_raw, fault = 8, raw, "stuck"   # 40 min
            elif r < 3 * self.fault_rate:
                self.dropout_left = 2
                return None, None, "dropout"
        raw = int(round(raw))
        index = 100 * ((RAW_DRY - raw) / (RAW_DRY - RAW_WET)) ** (1 / 0.9) if raw < RAW_DRY else 0.0
        return raw, round(index, 1), fault


class Pot:
    def __init__(self, name, start_index, rng, fault_rate):
        self.name = name
        self.water = AWC_ML * start_index / 100
        self.sensor = Sensor(rng, fault_rate)
        self.pending = []           # water reaching the sensor over the next steps
        self.recent = []            # last readings for the 5-min median (30 s reads)
        self.last_water_t = None
        self.day_given = 0.0
        self.low_since = None
        self.high_since = None
        self.prev_fault = ""

    @property
    def index(self):
        return 100 * self.water / AWC_ML

    def add_water(self, ml):
        # water spreads through the pot over ~10 min: 60 % now, 40 % next step
        self.pending.append([0.4 * ml])
        return self._apply(0.6 * ml)

    def _apply(self, ml):
        self.water += ml
        drained = 0.0
        if self.water > AWC_ML:
            drained = self.water - AWC_ML
            self.water = AWC_ML
        return drained

    def settle(self):
        drained = 0.0
        for p in self.pending:
            drained += self._apply(p[0])
        self.pending = []
        return drained


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="2026-11-09")
    ap.add_argument("--days", type=int, default=26)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--potb-dose", type=float, default=300.0, help="mL per Pot B watering")
    ap.add_argument("--potb-every-days", type=int, default=2)
    ap.add_argument("--fault-rate", type=float, default=0.002, help="chance per reading of each fault type")
    ap.add_argument("--out", default="sim_out")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    start = datetime.fromisoformat(args.start)
    end = start + timedelta(days=args.days)
    os.makedirs(args.out, exist_ok=True)

    weather = Weather(rng, start)
    pots = {"A": Pot("A", 80, rng, args.fault_rate), "B": Pot("B", 80, rng, args.fault_rate)}
    tank = TANK_ML
    step_h = STEP_MIN / 60

    f_read = open(os.path.join(args.out, "readings.csv"), "w", newline="")
    f_wat = open(os.path.join(args.out, "waterings.csv"), "w", newline="")
    f_ctx = open(os.path.join(args.out, "decision_contexts.jsonl"), "w")
    w_read = csv.writer(f_read)
    w_wat = csv.writer(f_wat)
    w_read.writerow(["timestamp", "pot", "soil_raw", "soil_index", "soil_index_true", "sensor_fault",
                     "air_temp_c", "air_rh_pct", "light_lux", "led_on", "tank_ml", "tank_low"])
    w_wat.writerow(["timestamp", "pot", "ml", "reason_code", "index_before", "index_true_before"])

    daily = {}   # (date, pot) -> dict
    history = {"A": []}   # (t, median index) for the LLM context

    def day_rec(d, p):
        return daily.setdefault((d, p), {"given_ml": 0.0, "drained_ml": 0.0, "et_ml": 0.0,
                                         "min_index": 100.0, "minutes_below_40": 0})

    t = start
    last_ctx_skip = None
    while t < end:
        days_in = (t - start).total_seconds() / 86400
        temp, rh, lux, led_on = weather.at(t)
        if t.weekday() == 0 and t.hour == 10 and t.minute == 0:
            tank = TANK_ML                               # weekly manual refill (Monday 10:00)
        tank_low = tank < TANK_LOW_ML

        for name, pot in pots.items():
            rec = day_rec(t.date(), name)
            if t.hour == 0 and t.minute == 0:
                pot.day_given = 0.0
            rec["drained_ml"] += pot.settle()
            loss = et_ml(step_h, temp, rh, lux, pot.index, days_in)
            pot.water = max(0.0, pot.water - loss)
            rec["et_ml"] += loss
            raw, idx, fault = pot.sensor.read(pot.index)
            rec["min_index"] = min(rec["min_index"], pot.index)
            if pot.index < 40:
                rec["minutes_below_40"] += STEP_MIN

            w_read.writerow([t.isoformat(), name, raw if raw is not None else "", idx if idx is not None else "",
                             round(pot.index, 1), fault, round(temp, 1), round(rh, 1), int(lux),
                             int(led_on), int(tank), int(tank_low)])

            if idx is not None:
                pot.recent = (pot.recent + [idx])[-3:]
            median = sorted(pot.recent)[len(pot.recent) // 2] if pot.recent else None

            # ---------------- decisions ----------------
            give, reason = 0.0, None
            if name == "A" and median is not None:
                history["A"].append((t, median))
                gap_ok = pot.last_water_t is None or (t - pot.last_water_t) >= timedelta(hours=MIN_GAP_H)
                if median < WATER_BELOW:
                    if tank_low:
                        reason = "SKIP_TANK_LOW"
                    elif not gap_ok:
                        reason = "SKIP_MIN_GAP"
                    elif pot.day_given >= DAY_CAP_ML:
                        reason = "SKIP_DAILY_CAP"
                    else:
                        need = (REFILL_TO - median) / 100 * AWC_ML
                        give = min(need, DOSE_CAP_ML, DAY_CAP_ML - pot.day_given)
                        reason = "WATER_BELOW_THRESHOLD"
                elif median > HARD_BLOCK_ABOVE:
                    reason = "NO_WATER_WET"
                # alarms
                if median < LOW_ALARM:
                    pot.low_since = pot.low_since or t
                else:
                    pot.low_since = None
                if median > HIGH_ALARM:
                    pot.high_since = pot.high_since or t
                else:
                    pot.high_since = None
                alarm = None
                if pot.low_since and t - pot.low_since >= timedelta(hours=2):
                    alarm = "ALARM_LOW_MOISTURE"
                if pot.high_since and t - pot.high_since >= timedelta(hours=24):
                    alarm = "ALARM_HIGH_MOISTURE"
                if fault and fault != pot.prev_fault:      # flag a sensor fault once, when it starts
                    alarm = alarm or "SENSOR_SUSPECT_" + fault.upper()
                pot.prev_fault = fault
                reason = reason or "NO_WATER_OK"

                explain = give > 0 or alarm or reason.startswith("SKIP")
                # one routine "no action" explanation every 6 h, so the LLM is also tested on quiet periods
                if not explain and (last_ctx_skip is None or t - last_ctx_skip >= timedelta(hours=6)):
                    explain = True
                    last_ctx_skip = t
                if explain:
                    hist = [round(v, 1) for (ht, v) in history["A"] if t - ht <= timedelta(hours=24)][::12]
                    ctx = {
                        "timestamp": t.isoformat(), "pot": "A",
                        "plant_profile": {"plant": "spearmint (Mentha spicata)", "water_below_index": WATER_BELOW,
                                          "refill_to_index": REFILL_TO, "ideal_temp_c": [15, 25],
                                          "dose_cap_ml": DOSE_CAP_ML, "day_cap_ml": DAY_CAP_ML,
                                          "min_gap_h": MIN_GAP_H},
                        "latest": {"soil_index_median_15min": median, "air_temp_c": round(temp, 1),
                                   "air_rh_pct": round(rh, 1), "light_lux": int(lux), "tank_low": tank_low,
                                   "sensor_fault_flag": fault or None},
                        "history_24h_hourly_index": hist,
                        "last_watering": pot.last_water_t.isoformat() if pot.last_water_t else None,
                        "given_today_ml": round(pot.day_given),
                        "time_of_day": ("night" if t.hour < 6 or t.hour >= 21 else
                                        "morning" if t.hour < 12 else "afternoon" if t.hour < 17 else "evening"),
                        "rules_decision": {"action": "water" if give > 0 else "no_water",
                                           "ml": round(give), "reason_code": reason, "alarm": alarm},
                    }
                    f_ctx.write(json.dumps(ctx) + "\n")

            if name == "B":
                if (t.date() - start.date()).days % args.potb_every_days == 0 and t.hour == 9 and t.minute == 0:
                    give, reason = (0.0, "SKIP_TANK_LOW") if tank_low else (args.potb_dose, "SCHEDULE")

            if give > 0:
                give = min(give, tank)
                w_wat.writerow([t.isoformat(), name, round(give), reason, median, round(pot.index, 1)])
                rec["drained_ml"] += pot.add_water(give)
                rec["given_ml"] += give
                pot.day_given += give
                pot.last_water_t = t
                tank -= give

        t += timedelta(minutes=STEP_MIN)

    with open(os.path.join(args.out, "daily_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "pot", "given_ml", "drained_ml", "plant_used_ml", "min_true_index", "minutes_below_40"])
        for (d, p), r in sorted(daily.items()):
            w.writerow([d.isoformat(), p, round(r["given_ml"]), round(r["drained_ml"]), round(r["et_ml"]),
                        round(r["min_index"], 1), r["minutes_below_40"]])

    for f in (f_read, f_wat, f_ctx):
        f.close()

    tot = {p: {k: sum(r[k] for (d, pp), r in daily.items() if pp == p) for k in
               ("given_ml", "drained_ml", "et_ml", "minutes_below_40")} for p in pots}
    print(f"Simulated {args.days} days from {args.start}, seed {args.seed} -> {args.out}/")
    for p, r in tot.items():
        print(f"  Pot {p}: given {r['given_ml']:.0f} mL, drained {r['drained_ml']:.0f} mL, "
              f"used by plant {r['et_ml']:.0f} mL, {r['minutes_below_40'] / 60:.1f} h below index 40")
    a, b = tot["A"]["given_ml"], tot["B"]["given_ml"]
    if b:
        print(f"  Water saved by Pot A vs Pot B: {100 * (b - a) / b:.1f} %  (synthetic, not a result)")


if __name__ == "__main__":
    main()
