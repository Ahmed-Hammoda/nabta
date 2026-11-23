#!/usr/bin/env python3
"""Live view of the Nabta sensors (read only: writes nothing).

    cd ~/nabta
    python3 live_view.py          # one line every 2 s, Ctrl+C to stop
    python3 live_view.py 5        # one line every 5 s

Float switch test (once): watch the "float" column, lift the float up, then let it drop down.
The value it shows when the float is DOWN (tank low) goes into FLOAT_LOW_VALUE in garden_logger.py.
"""
import sys, time
import garden_logger as g

cal = g.load_calibration()
s = g.RealSensors()
fl = g.FloatSwitch()
every = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
print("Soil index: 0 = dry air, 100 = water.  Float: pin value (tank: low/ok once FLOAT_LOW_VALUE is set).  Ctrl+C to stop.\n")
print("%-9s%9s%12s%9s%8s%7s%7s%6s" % ("time", "soil raw", "soil 0-100", "lux", "temp C", "RH %", "float", "tank"))
try:
    while True:
        raw = s.read_soil_raw(); t, h = s.read_bme(); lux = s.read_lux(); f = fl.read()
        tank = {None: "?", 1: "LOW", 0: "ok"}[g.tank_low_from(f)]
        print("%-9s%9.0f%12.1f%9.1f%8.2f%7.1f%7s%6s" % (time.strftime("%H:%M:%S"), raw, g.soil_index(raw, cal),
                                                        lux, t, h, "-" if f is None else f, tank))
        time.sleep(every)
except KeyboardInterrupt:
    print("\nstopped")
