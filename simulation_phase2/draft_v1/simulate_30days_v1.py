"""Simulated (dummy) 30-day Nabta log for testing, built on the real test of 2026-11-15.

It writes the same columns as the real 30-min log (log_30min.csv), plus a key file with the
scenario of every row and the decision of the rules (labels.py).

Model of the pot (1-minute steps, then 30-min averages like the real logger):
- Indoor values copy the real test: 23-24.5 C, 52-62 % RH, light <= 75 lux.
- Balcony values follow a Tunis late-November / December day (sunrise 07:10, sunset 17:10).
- Soil dries faster with heat, light and dry air; the pump adds ~26 points when the rules say water.
- Stress scenarios (heat wave, cold snap) are deliberately extreme to trigger the danger alerts.

    python simulate_30days_v1.py       # writes this folder (rules v1 = phase 1 labels.py)
"""
import csv, datetime as dt, math, os

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "simulation_phase1", "bench"))  # phase-1 code (labels, explain_bench, run_bench)
import numpy as np

from labels import label

SEED = 2026
OUT = os.path.dirname(os.path.abspath(__file__))
START = dt.datetime(2026, 11, 15)          # day -1 = warm-up (fills the 24 h light sum)
NDAYS = 31                                  # warm-up + 30 days
RISE, SET = 7 * 60 + 10, 17 * 60 + 10       # minutes of the day

# day: (location, sky, event). Location changes take effect at 09:00 that day.
PLAN = {-1: ("indoor", "sunny", None)}
for d in range(0, 3):   PLAN[d] = ("indoor", "sunny" if d != 1 else "cloudy", None)
for d, s in zip(range(3, 8), ["sunny", "sunny", "cloudy", "sunny", "sunny"]): PLAN[d] = ("balcony", s, None)
PLAN[8] = ("balcony", "rain", "rain"); PLAN[9] = ("balcony", "rain", "rain")
for d in range(10, 13): PLAN[d] = ("balcony", "sunny", "heat_wave")
PLAN[13] = ("balcony", "sunny", "tank_empty"); PLAN[14] = ("balcony", "sunny", "tank_empty")
PLAN[15] = ("balcony", "sunny", None)
PLAN[16] = ("balcony", "sunny", "cold_snap"); PLAN[17] = ("balcony", "cloudy", "cold_snap")
PLAN[18] = ("balcony", "sunny", "cold_snap")
PLAN[19] = ("balcony", "sunny", "relay_stuck"); PLAN[20] = ("balcony", "cloudy", None)
PLAN[21] = ("balcony", "cloudy", "sensor_disconnected")
for d, s in zip(range(22, 26), ["sunny", "cloudy", "sunny", "sunny"]): PLAN[d] = ("window", s, None)
for d, s in zip(range(26, 30), ["sunny", "cloudy", "sunny", "sunny"]): PLAN[d] = ("balcony", s, None)

# outdoor (Tmin, Tmax) per sky / event
OUT_T = {"sunny": (11.5, 19.5), "cloudy": (13.0, 17.0), "rain": (12.0, 15.0)}
HEAT = [(25.5, 37.4), (27.0, 38.8), (26.0, 37.9)]
COLD = [(2.0, 10.0), (3.0, 9.5), (1.5, 11.0)]
RAIN_HOURS = {8: [(14, 20)], 9: [(3, 9), (15, 18)]}
TANK_EMPTY = (10 * 1440 + 14 * 60, 15 * 1440 + 10 * 60)     # pump cannot water (minutes from day 0)
RELAY_STUCK = (19 * 1440 + 11 * 60 + 5, 19 * 1440 + 13 * 60 + 35)
SENSOR_OFF = (21 * 1440 + 9 * 60, 21 * 1440 + 13 * 60)


def main():
    rng = np.random.default_rng(SEED)
    n = NDAYS * 1440
    minute = np.arange(n) - 1440            # minutes from day 0 00:00 (warm-up is negative)
    day = np.floor_divide(minute, 1440)
    mod = minute % 1440

    # location per minute (changes at 09:00)
    loc = np.array([PLAN[int(d) if m >= 540 else max(int(d) - 1, -1)][0] for d, m in zip(day, mod)])
    sky = np.array([PLAN[int(d)][1] for d in day])

    # --- outdoor temperature: cosine between daily min (06:30) and max (14:30)
    anchors = []
    heat_i = cold_i = 0
    for d in range(-1, 30):
        lo, hi = OUT_T[PLAN[d][1]]
        if PLAN[d][2] == "heat_wave": lo, hi = HEAT[heat_i]; heat_i += 1
        if PLAN[d][2] == "cold_snap": lo, hi = COLD[cold_i]; cold_i += 1
        lo += rng.normal(0, 0.6); hi += rng.normal(0, 0.6)
        anchors += [(d * 1440 + 390, lo), (d * 1440 + 870, hi)]
    anchors = [(-1440 - 570, anchors[0][1] + 0.5)] + anchors + [(30 * 1440 + 390, 12.0)]
    at = np.array([a[0] for a in anchors]); av = np.array([a[1] for a in anchors])
    k = np.searchsorted(at, minute, side="right") - 1
    f = (minute - at[k]) / (at[k + 1] - at[k])
    t_out = av[k] + (av[k + 1] - av[k]) * (1 - np.cos(np.pi * f)) / 2
    t_out += rng.normal(0, 0.05, n)

    # --- light
    sun = np.where((mod > RISE) & (mod < SET), np.sin(np.pi * (mod - RISE) / (SET - RISE)), 0.0) ** 1.4
    cloud = np.ones(n)
    c = 1.0
    for i in range(n):  # AR(1) cloud factor
        s = sky[i]
        mean, sd = {"sunny": (1.0, 0.03), "cloudy": (0.9, 0.35), "rain": (0.8, 0.3)}[s]
        c = mean + 0.97 * (c - mean) + rng.normal(0, sd * 0.25)
        cloud[i] = np.clip(c, 0.97 if s == "sunny" else 0.2, 1.03 if s == "sunny" else 1.6)
    peak_bal = np.array([{"sunny": 55000, "cloudy": 16000, "rain": 5000}[s] for s in sky], float)
    peak_bal[[PLAN[int(d)][2] == "heat_wave" for d in day]] = 66000
    peak_win = np.array([{"sunny": 4500, "cloudy": 1500, "rain": 700}[s] for s in sky], float)
    peak_in = np.array([{"sunny": 72, "cloudy": 30, "rain": 15}[s] for s in sky], float)
    lamp_on = {d: rng.random() < 0.6 for d in range(-1, 30)}
    lamp = np.array([40.0 if lamp_on[int(d)] and 1080 <= m <= 1350 else 0.0 for d, m in zip(day, mod)])
    lux = np.where(loc == "balcony", peak_bal * sun * cloud,
                   np.where(loc == "window", peak_win * sun * cloud + lamp, peak_in * sun * cloud + lamp))
    lux = np.maximum(lux + rng.normal(0, 0.3, n), 0)

    # --- indoor temperature and humidity (copy of the real test)
    t_in = 23.6 + 0.4 * np.cos(2 * np.pi * (mod - 960) / 1440) + np.cumsum(rng.normal(0, 0.004, n))
    t_in = np.clip(t_in, 22.5, 25.0)
    t_win = t_in + 2.0 * (peak_win * sun * cloud) / 4500
    temp = np.where(loc == "balcony", t_out, np.where(loc == "window", t_win, t_in))

    rh_in = np.clip(57 + np.cumsum(rng.normal(0, 0.05, n)), 50, 64)
    tmean = np.convolve(t_out, np.ones(1440) / 1440, mode="same")
    base = np.array([{"sunny": 66, "cloudy": 74, "rain": 91}[s] for s in sky], float)
    ev = np.array([PLAN[int(d)][2] for d in day])
    base[ev == "heat_wave"] = 30
    base[ev == "cold_snap"] = 76
    rh_out = np.clip(base - 2.3 * (t_out - tmean) + np.cumsum(rng.normal(0, 0.05, n)) * 0.2, 15, 98)
    hum = np.where(loc == "balcony", rh_out, rh_in) + rng.normal(0, 0.2, n)

    # --- soil moisture (true value can exceed 100 when waterlogged; the sensor stops at 100)
    m = 84.0
    true_m = np.zeros(n); reading = np.zeros(n)
    pump_queue = 0.0
    rows = []
    rain_min = set()
    for d, spans in RAIN_HOURS.items():
        for a, b in spans:
            rain_min.update(range(d * 1440 + a * 60, d * 1440 + b * 60))
    for i in range(n):
        mi = int(minute[i])
        # logging + decision every 30 min (decision on the 30-min average, like the real system)
        if mi % 30 == 0 and mi >= 0:
            sl = slice(i - 30, i)
            row = {"t": mi, "m": float(np.mean(reading[sl])), "temp": float(np.mean(temp[sl])),
                   "rh": float(np.mean(hum[sl])), "lux": float(np.mean(lux[sl])),
                   "luxh": float(np.sum(lux[i - 1440:i]) / 60), "true_m": float(true_m[i - 1])}
            key = label(round(row["m"], 1), round(row["temp"], 2), round(row["rh"], 1), round(row["luxh"], 2))
            in_relay = RELAY_STUCK[0] <= mi < RELAY_STUCK[1]
            if in_relay:
                action = "stuck_on"
            elif key["water"] == "yes":
                if TANK_EMPTY[0] <= mi < TANK_EMPTY[1]:
                    action = "no_water_in_tank"
                else:
                    action = "watered"
                    pump_queue += rng.normal(26, 3)
            else:
                action = "off"
            row["action"] = action
            row["key"] = key
            rows.append(row)
        # physics
        T, H, L = temp[i], hum[i], lux[i]
        rate = 1.4 * (0.15 + 0.012 * max(T, 0)) * (1 + L / 40000) * (1 + (60 - H) / 100)   # points per hour
        m -= rate / 60 * (0.3 + 0.7 * min(m, 100) / 100)
        if m > 97:
            m -= 0.03                                              # drainage of a soaked pot
        if mi in rain_min and loc[i] == "balcony":
            m += 4 / 60
        if pump_queue > 0:
            add = min(pump_queue, 26 / 6); m += add; pump_queue -= add
        if RELAY_STUCK[0] <= mi < RELAY_STUCK[1]:
            m += 0.1
        m = min(m, 118)
        true_m[i] = m
        r = min(max(m + rng.normal(0, 0.3), 0), 100)
        if SENSOR_OFF[0] <= mi < SENSOR_OFF[1]:
            r = 0.0
        reading[i] = r

    os.makedirs(OUT, exist_ok=True)
    tz = "+01:00"
    with open(os.path.join(OUT, "sim_sensor_30days.csv"), "w", newline="", encoding="utf-8") as fs, \
         open(os.path.join(OUT, "sim_key_30days.csv"), "w", newline="", encoding="utf-8") as fk:
        ws, wk = csv.writer(fs), csv.writer(fk)
        ws.writerow(["timestamp", "soil_moisture_index", "air_temp_c", "humidity_rh", "light_lux_now",
                     "light_lux_hours_24h"])
        wk.writerow(["timestamp", "day", "scenario", "location", "sky", "true_soil_moisture", "pump_action",
                     "moisture_level", "temp_level", "light_level", "humidity_level", "water", "alerts"])
        for r in rows:
            ts = (START + dt.timedelta(days=1, minutes=r["t"], seconds=1)).isoformat() + tz
            i = r["t"] + 1440 - 1
            d = r["t"] // 1440
            ev = PLAN[d][2]
            mi = r["t"]
            if SENSOR_OFF[0] < mi <= SENSOR_OFF[1] + 30: scen = "sensor_disconnected"
            elif RELAY_STUCK[0] < mi <= RELAY_STUCK[1] + 30: scen = "relay_stuck"
            elif r["true_m"] > 100.5: scen = "waterlogged"
            elif TANK_EMPTY[0] < mi <= TANK_EMPTY[1]: scen = "heat_wave+tank_empty" if ev == "heat_wave" else "tank_empty"
            elif ev in ("heat_wave", "cold_snap", "rain"): scen = ev
            else: scen = f"{loc[i]}_{sky[i]}"
            k = r["key"]
            ws.writerow([ts, f"{r['m']:.1f}", f"{r['temp']:.2f}", f"{r['rh']:.1f}", f"{r['lux']:.1f}",
                         f"{r['luxh']:.2f}"])
            wk.writerow([ts, d + 1, scen, loc[i], sky[i], f"{r['true_m']:.1f}", r["action"],
                         k["moisture_level"], k["temp_level"], k["light_level"], k["humidity_level"],
                         k["water"], ";".join(k["alerts"]) or "none"])
    print("wrote", len(rows), "rows to", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
