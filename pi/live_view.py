#!/usr/bin/env python3
"""Live view of the Nabta sensors (read only: writes nothing).

    cd ~/nabta
    python3 live_view.py          # one line every 2 s, Ctrl+C to stop
    python3 live_view.py 5        # one line every 5 s
"""
import sys, time
import garden_logger as g

cal = g.load_calibration()
s = g.RealSensors()
every = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
print("Soil index: 0 = dry air, 100 = water.  Ctrl+C to stop.\n")
print("%-9s%9s%12s%9s%8s%7s" % ("time", "soil raw", "soil 0-100", "lux", "temp C", "RH %"))
try:
    while True:
        raw = s.read_soil_raw(); t, h = s.read_bme(); lux = s.read_lux()
        print("%-9s%9.0f%12.1f%9.1f%8.2f%7.1f" % (time.strftime("%H:%M:%S"), raw, g.soil_index(raw, cal), lux, t, h))
        time.sleep(every)
except KeyboardInterrupt:
    print("\nstopped")
