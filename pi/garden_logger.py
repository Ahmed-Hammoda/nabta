#!/usr/bin/env python3
"""
Raspberry Pi 4 sensor logger
  - BH1750  light sensor        (I2C 0x23 or 0x5C)
  - BME280  temp/humidity       (I2C 0x76 or 0x77)
  - Soil moisture sensor on ADS1115 channel A0 (I2C 0x48)

Install (once):
    sudo apt install -y python3-pip i2c-tools
    sudo raspi-config nonint do_i2c 0          # enable I2C, then reboot
    pip3 install smbus2 RPi.bme280 --break-system-packages

Usage:
    python3 garden_logger.py --calibrate       # step 1: calibrate soil sensor
    python3 garden_logger.py                   # step 2: start logging
    python3 garden_logger.py --simulate        # test without hardware

Files (created next to this script):
    soil_calibration.json   the five calibration values
    raw_log.csv             one row every 10 s
    log_30min.csv           one averaged row every 30 min (the report file)
"""

import argparse
import csv
import json
import os
import random
import signal
import statistics
import sys
import threading
import time
from collections import deque
from datetime import datetime

# ----------------------------------------------------------------- settings
BUS_NUM = 1                   # /dev/i2c-1 on the Pi 4
ADS_ADDR = 0x48               # ADS1115 (ADDR pin to GND)
SOIL_CHANNEL = 0              # soil sensor on A0 (0-3)
BH_ADDRS = (0x23, 0x5C)       # BH1750 (ADDR low / high)
BME_ADDRS = (0x76, 0x77)      # BME280 (SDO low / high)

DEFAULT_INTERVAL_S = 10       # raw log period
DEFAULT_AVG_S = 30 * 60       # averaged row period
HOURS_WINDOW_S = 24 * 3600    # light-total window

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAL_FILE = os.path.join(BASE_DIR, "soil_calibration.json")
sys.path.insert(0, BASE_DIR)
import nabta_paths as paths   # logs/<YYYY-MM>/raw_log.csv and log_30min.csv (one folder per month)

AVG_HEADER = ["timestamp", "soil_moisture_index", "air_temp_c",
              "humidity_rh", "light_lux_now", "light_lux_hours_24h", "samples"]
RAW_HEADER = ["timestamp", "soil_raw", "soil_moisture_index", "air_temp_c",
              "humidity_rh", "light_lux_now", "light_lux_hours_24h"]

CAL_STEPS = [
    ("dry_air",   "DRY AIR  - sensor held in the air, touching nothing"),
    ("water",     "WATER    - sensor dipped in a glass of water up to its "
                  "max line (keep the electronics dry)"),
    ("soil_dry",  "SOIL DRY   - sensor in our soil when it is dry"),
    ("soil_moist", "SOIL MOIST - sensor in our soil when it is moist"),
    ("soil_wet",  "SOIL WET   - sensor in our soil when it is wet"),
]

stop_event = threading.Event()


# ------------------------------------------------------------------ helpers
def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def fmt(value, digits):
    """Number -> rounded value for CSV, None -> empty cell."""
    if value is None:
        return ""
    return round(value, digits)


def mean_or_none(values):
    return sum(values) / len(values) if values else None


def append_row(path, header, row):
    new_file = (not os.path.exists(path)) or os.path.getsize(path) == 0
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(header)
        writer.writerow(row)
        f.flush()
        os.fsync(f.fileno())


def safe_read(fn, label, tries=2):
    """Call a sensor read; return None (and warn) if it keeps failing."""
    err = None
    for _ in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - any I2C problem
            err = e
            time.sleep(0.1)
    print("[warn] %s read failed: %s" % (label, err), file=sys.stderr)
    return None


def soil_index(raw, cal):
    """Raw ADC -> 0-100 using dry air (=0) and water (=100)."""
    if raw is None:
        return None
    dry, water = cal["dry_air"], cal["water"]
    if dry == water:
        return None
    idx = (raw - dry) / (water - dry) * 100.0
    return max(0.0, min(100.0, idx))


def next_boundary(t, period_s):
    """Next wall-clock multiple of period_s (e.g. :00 and :30)."""
    return (int(t // period_s) + 1) * period_s


# ------------------------------------------------------------------ sensors
class RealSensors:
    def __init__(self):
        try:
            from smbus2 import SMBus, i2c_msg
            import bme280
        except ImportError as e:
            sys.exit("Missing library (%s).\nRun: pip3 install smbus2 "
                     "RPi.bme280 --break-system-packages" % e)
        self._i2c_msg = i2c_msg
        self._bme280 = bme280
        try:
            self.bus = SMBus(BUS_NUM)
        except FileNotFoundError:
            sys.exit("I2C bus not found. Enable I2C (sudo raspi-config -> "
                     "Interface Options -> I2C), then reboot.")

        self._init_ads()
        self._init_bh1750()
        self._init_bme280()

    # --- ADS1115 -----------------------------------------------------------
    def _init_ads(self):
        try:
            self.bus.read_i2c_block_data(ADS_ADDR, 0x01, 2)
        except OSError:
            sys.exit("ADS1115 not found at 0x%02X. Check wiring and run "
                     "'i2cdetect -y 1'." % ADS_ADDR)

    def read_soil_raw(self, samples=5):
        """Average of a few single-shot conversions on SOIL_CHANNEL."""
        mux = 0x4 + SOIL_CHANNEL                 # AINx vs GND
        config = (0x8000                         # start single conversion
                  | (mux << 12)
                  | (0x1 << 9)                   # +/-4.096 V range
                  | 0x0100                       # single-shot mode
                  | (0x4 << 5)                   # 128 samples/s
                  | 0x0003)                      # comparator off
        values = []
        for _ in range(samples):
            self.bus.write_i2c_block_data(
                ADS_ADDR, 0x01, [(config >> 8) & 0xFF, config & 0xFF])
            time.sleep(0.009)
            deadline = time.monotonic() + 0.2
            while True:
                d = self.bus.read_i2c_block_data(ADS_ADDR, 0x01, 2)
                if d[0] & 0x80:                  # conversion finished
                    break
                if time.monotonic() > deadline:
                    raise IOError("ADS1115 conversion timeout")
                time.sleep(0.002)
            d = self.bus.read_i2c_block_data(ADS_ADDR, 0x00, 2)
            val = (d[0] << 8) | d[1]
            if val & 0x8000:
                val -= 65536
            values.append(val)
        return sum(values) / len(values)

    # --- BH1750 ------------------------------------------------------------
    def _init_bh1750(self):
        self.bh_addr = None
        for addr in BH_ADDRS:
            try:
                self.bus.write_byte(addr, 0x01)  # power on
                self.bh_addr = addr
                break
            except OSError:
                continue
        if self.bh_addr is None:
            sys.exit("BH1750 not found at 0x23 or 0x5C. Check wiring and "
                     "run 'i2cdetect -y 1'.")
        self._bh_start()

    def _bh_start(self):
        self.bus.write_byte(self.bh_addr, 0x01)  # power on
        self.bus.write_byte(self.bh_addr, 0x10)  # continuous high-res mode
        time.sleep(0.2)

    def read_lux(self):
        try:
            msg = self._i2c_msg.read(self.bh_addr, 2)
            self.bus.i2c_rdwr(msg)
            data = list(msg)
        except OSError:
            self._bh_start()                     # recover, then let caller retry
            raise
        raw = (data[0] << 8) | data[1]
        return raw / 1.2

    # --- BME280 ------------------------------------------------------------
    def _init_bme280(self):
        self.bme_addr = None
        for addr in BME_ADDRS:
            try:
                chip_id = self.bus.read_byte_data(addr, 0xD0)
            except OSError:
                continue
            if chip_id == 0x60:
                self.bme_addr = addr
                break
            if chip_id in (0x56, 0x57, 0x58):
                sys.exit("Chip at 0x%02X is a BMP280 (no humidity). You need "
                         "a real BME280." % addr)
        if self.bme_addr is None:
            sys.exit("BME280 not found at 0x76 or 0x77. Check wiring and "
                     "run 'i2cdetect -y 1'.")
        self.bme_params = self._bme280.load_calibration_params(
            self.bus, self.bme_addr)

    def read_bme(self):
        s = self._bme280.sample(self.bus, self.bme_addr, self.bme_params)
        return s.temperature, s.humidity


class SimSensors:
    """Fake sensors so the script can be tested without hardware."""

    def read_soil_raw(self, samples=5):
        return 14000 + random.uniform(-150, 150)

    def read_lux(self):
        return max(0.0, 300 + random.uniform(-50, 50))

    def read_bme(self):
        return 22 + random.uniform(-0.5, 0.5), 55 + random.uniform(-2, 2)


# -------------------------------------------------------------- calibration
def sample_soil(sensors, n=20, delay=0.25):
    vals = []
    for _ in range(n):
        v = safe_read(sensors.read_soil_raw, "soil")
        if v is not None:
            vals.append(v)
        time.sleep(delay)
    if len(vals) < n // 2:
        sys.exit("Too many failed soil readings. Check the ADS1115 wiring.")
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return statistics.mean(vals), sd


def calibrate(sensors):
    print("\n=== SOIL SENSOR CALIBRATION ===")
    print("For each step: place the sensor, press Enter, hold it still for "
          "about 5 seconds.\n")
    cal = {}
    for key, text in CAL_STEPS:
        while True:
            try:
                input("%s\n  Press Enter when ready... " % text)
            except EOFError:
                sys.exit("\nCalibration cancelled.")
            print("  measuring...")
            mean, sd = sample_soil(sensors)
            print("  %s = %.0f  (noise +/- %.0f)" % (key, mean, sd))
            if sd > 0.02 * max(abs(mean), 1):
                print("  Readings are unstable. Press 'r' + Enter to repeat, "
                      "or just Enter to accept.")
                try:
                    if input("  > ").strip().lower() == "r":
                        continue
                except EOFError:
                    pass
            cal[key] = round(mean, 1)
            break

    if abs(cal["dry_air"] - cal["water"]) < 500:
        sys.exit("\nDry-air and water values are almost identical (%.0f vs "
                 "%.0f). Check that the sensor is on channel A0 and wired "
                 "correctly, then calibrate again."
                 % (cal["dry_air"], cal["water"]))

    cal["saved_at"] = now_iso()
    with open(CAL_FILE, "w") as f:
        json.dump(cal, f, indent=2)

    print("\n=== RESULT (saved to %s) ===" % CAL_FILE)
    print("Raw values - send me these five:")
    for key, _ in CAL_STEPS:
        idx = soil_index(cal[key], cal)
        print("  %-11s raw = %8.1f   index = %5.1f" % (key, cal[key], idx))
    print("\nIndex: dry air = 0, water = 100.")
    print("Check the three soil indexes above against your threshold "
          "(e.g. 'water at 70 or below').")


def load_calibration():
    if not os.path.exists(CAL_FILE):
        sys.exit("No calibration found. Run first:\n"
                 "  python3 garden_logger.py --calibrate")
    with open(CAL_FILE) as f:
        cal = json.load(f)
    for key in ("dry_air", "water"):
        if key not in cal:
            sys.exit("Calibration file is incomplete. Run --calibrate again.")
    if cal["dry_air"] == cal["water"]:
        sys.exit("Calibration is invalid (dry == water). Run --calibrate "
                 "again.")
    return cal


# ------------------------------------------------------------------ logging
def rebuild_lux_history(interval_s):
    """Reload the last 24 h of lux x hours from the raw log (after restart)."""
    hist = deque()
    cutoff = time.time() - HOURS_WINDOW_S
    last_t = None
    try:
        rows = []
        for path in paths.files("raw_log.csv", last=2):   # this month and last month
            with open(path, newline="") as f:
                rows += list(csv.DictReader(f))
        if True:
            for row in rows:
                try:
                    t = datetime.fromisoformat(row["timestamp"]).timestamp()
                    lux_txt = row["light_lux_now"]
                except (KeyError, ValueError, TypeError):
                    continue
                if t < cutoff:
                    last_t = t
                    continue
                dt = interval_s if last_t is None else min(t - last_t,
                                                           2 * interval_s)
                last_t = t
                if lux_txt in ("", None):
                    continue
                try:
                    lux = float(lux_txt)
                except ValueError:
                    continue
                hist.append((t, lux * max(dt, 0) / 3600.0))
    except OSError as e:
        print("[warn] could not read old raw log: %s" % e, file=sys.stderr)
    return hist


def run(args):
    cal = load_calibration()
    sensors = SimSensors() if args.simulate else RealSensors()
    interval = args.interval
    avg_s = args.avg_seconds

    lux_hist = rebuild_lux_history(interval)
    paths.log_event("logger", "started", "raw every %ss, average every %ss, light history %.1f lux-h"
                    % (interval, avg_s, sum(c for _, c in lux_hist)))
    for gz in paths.compress_old_raw():
        print("compressed old raw log:", gz)
    month = paths.month_of()
    samples = 0
    window = {"soil": [], "temp": [], "rh": [], "lux": []}
    next_flush = next_boundary(time.time(), avg_s)
    last_t = None
    next_tick = time.monotonic()

    print("Logging started. Raw row every %ss, averaged row every %s s."
          % (interval, avg_s))
    print("Files: %s/<YYYY-MM>/raw_log.csv and log_30min.csv. Ctrl+C to stop." % paths.LOGS)

    while not stop_event.is_set():
        t = time.time()

        soil_raw = safe_read(sensors.read_soil_raw, "soil")
        lux = safe_read(sensors.read_lux, "BH1750")
        bme = safe_read(sensors.read_bme, "BME280")
        temp, rh = bme if bme else (None, None)
        idx = soil_index(soil_raw, cal)

        # 24 h light total: sum of lux x hours over the last 24 h
        if lux is not None:
            dt = interval if last_t is None else min(t - last_t, 2 * interval)
            lux_hist.append((t, lux * dt / 3600.0))
        last_t = t
        while lux_hist and lux_hist[0][0] < t - HOURS_WINDOW_S:
            lux_hist.popleft()
        lux_hours_24h = sum(c for _, c in lux_hist)

        samples += 1
        append_row(paths.raw_file(), RAW_HEADER, [
            now_iso(), fmt(soil_raw, 1), fmt(idx, 1), fmt(temp, 2),
            fmt(rh, 1), fmt(lux, 1), fmt(lux_hours_24h, 2)])

        for key, val in (("soil", idx), ("temp", temp),
                         ("rh", rh), ("lux", lux)):
            if val is not None:
                window[key].append(val)

        if t >= next_flush:
            if any(window.values()):
                append_row(paths.avg_file(), AVG_HEADER, [
                    now_iso(),
                    fmt(mean_or_none(window["soil"]), 1),
                    fmt(mean_or_none(window["temp"]), 2),
                    fmt(mean_or_none(window["rh"]), 1),
                    fmt(mean_or_none(window["lux"]), 1),
                    fmt(lux_hours_24h, 2), samples])
                print("[%s] averaged row saved (%d samples)" % (now_iso(), samples))
            window = {"soil": [], "temp": [], "rh": [], "lux": []}
            samples = 0
            if paths.month_of() != month:            # a new month: new folder, compress old raw logs
                month = paths.month_of()
                for gz in paths.compress_old_raw():
                    print("compressed old raw log:", gz)
            next_flush = next_boundary(t, avg_s)

        next_tick += interval
        delay = next_tick - time.monotonic()
        if delay < 0:                    # fell behind; resync
            next_tick = time.monotonic()
            delay = 0
        stop_event.wait(delay)

    paths.log_event("logger", "stopped")
    print("Stopped.")


def main():
    parser = argparse.ArgumentParser(description="Pi sensor logger")
    parser.add_argument("--calibrate", action="store_true",
                        help="calibrate the soil sensor")
    parser.add_argument("--simulate", action="store_true",
                        help="use fake sensors (no hardware needed)")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S,
                        help="raw log period in seconds (default 10)")
    parser.add_argument("--avg-seconds", type=float, default=DEFAULT_AVG_S,
                        help="averaged row period in seconds (default 1800)")
    args = parser.parse_args()

    if args.interval <= 0 or args.avg_seconds <= 0:
        sys.exit("--interval and --avg-seconds must be positive.")

    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())

    if args.calibrate:
        calibrate(SimSensors() if args.simulate else RealSensors())
    else:
        run(args)


if __name__ == "__main__":
    main()
