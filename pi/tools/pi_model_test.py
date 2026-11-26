"""Full model test on the Pi (20 explanations + 6 chat questions) with a temperature watchdog.

Every result is written to its own JSON line the moment it is done (flushed to disk), so nothing is
lost if the test stops. File: ~/nabta/logs/model_tests/test_<date>_<time>.jsonl
Stops and unloads the model if the CPU reaches STOP_C or the Pi throttles.
"""
import json, os, subprocess, sys, threading, time
sys.path.insert(0, os.path.expanduser("~/nabta"))
os.chdir(os.path.expanduser("~/nabta"))
import nabta_controller as c
import explain_bench as eb
import rules_v3
import nabta_chat as ch

STOP_C = 75.0
OUTDIR = os.path.expanduser("~/nabta/logs/model_tests")
os.makedirs(OUTDIR, exist_ok=True)
OUT = os.path.join(OUTDIR, time.strftime("test_%Y%m%d_%H%M.jsonl"))
stop = threading.Event()
temps = []


def temp():
    out = subprocess.run(["vcgencmd", "measure_temp"], capture_output=True, text=True).stdout
    return float(out.split("=")[1].split("'")[0])


def throttled():
    out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True).stdout
    return int(out.strip().split("=")[1], 16)


def save(rec):
    rec["time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + chr(10))
        f.flush()
        os.fsync(f.fileno())


def watchdog():
    while not stop.is_set():
        t, th = temp(), throttled()
        temps.append(t)
        if t >= STOP_C or th & 0xF:
            print(f"!!! STOP: CPU {t:.1f} C, throttled=0x{th:x} -> unloading the model", flush=True)
            save({"type": "STOP", "cpu_c": t, "throttled": hex(th)})
            subprocess.run(["ollama", "stop", c.MODEL], capture_output=True)
            stop.set()
            return
        time.sleep(2)


def ts():
    return time.strftime("%H:%M:%S")


t_start, th_start = temp(), throttled()
print(f"{ts()} start: CPU {t_start:.1f} C, throttled=0x{th_start:x}, results -> {OUT}", flush=True)
save({"type": "START", "cpu_c": t_start, "throttled": hex(th_start), "model": c.MODEL})
threading.Thread(target=watchdog, daemon=True).start()

# 20 readings (no faults and no low tank: those get a fixed message, not the model)
R = [(55, 22, 55, 50, 40000, 10), (85, 22, 55, 0, 40000, 23), (85, 22, 65, 20000, 150000, 12),
     (40, 26, 50, 3000, 120000, 16), (20, 24, 45, 800, 60000, 9), (75, 38, 30, 30000, 300000, 14),
     (90, 18, 62, 5000, 230000, 11), (65, 3, 80, 0, 100000, 6), (99, 21, 70, 1200, 95000, 15),
     (70, 25, 60, 2500, 80000, 8), (71, 15, 66, 300, 50000, 19), (30, 30, 40, 40000, 400000, 13),
     (88, 20, 58, 0, 20000, 2), (60, 35, 35, 25000, 260000, 15), (24, 5, 90, 100, 30000, 7),
     (95, 23, 64, 3000, 180000, 17), (50, 19, 72, 10000, 200000, 10), (80, 37, 25, 60000, 500000, 13),
     (66, 16, 68, 500, 88000, 20), (45, 28, 52, 15000, 226000, 11)]
COLS = ["soil_moisture_index", "air_temp_c", "humidity_rh", "light_lux_now", "light_lux_hours_24h"]
for n, (m, t, h, ln, lh, hr) in enumerate(R, 1):
    if stop.is_set():
        break
    x = {"soil_moisture_index": float(m), "air_temp_c": float(t), "humidity_rh": float(h),
         "light_lux_now": float(ln), "light_lux_hours_24h": float(lh), "hour": hr, "light_on": 0, "tank_low": 0}
    k = rules_v3.decide(x)
    case = {"input": {cc: x[cc] for cc in COLS}, "key": k}
    cpu_before = temp()
    try:
        text, secs = eb.ask(c.MODEL, eb.messages("e3", case), False)
        err = ""
    except Exception as e:  # noqa: BLE001
        text, secs, err = "", 0.0, str(e)
    chk = eb.check(text, case) if text else {}
    failed = [cc for cc in c.EXPLAIN_CHECKS if not chk.get(cc)] if text else ["no answer"]
    final = (" ".join(p for p in (text, c.light_sentence(k)) if p) if not failed else c.code_sentence(x, k))
    rec = {"type": "explain", "n": n, "input": x,
           "rules": {kk: k[kk] for kk in ("moisture_level", "temp_level", "light_level", "humidity_level",
                                          "alerts", "water", "light")},
           "model_answer": text, "error": err, "passed": not failed, "failed_checks": failed,
           "invented_numbers": chk.get("invented", []), "missing_alerts": chk.get("missing_alerts", []),
           "fake_alerts": chk.get("fake_alerts", []), "shown_message": final,
           "message_source": c.MODEL if not failed else "code (check failed)",
           "seconds": round(secs, 1), "cpu_before_c": cpu_before, "cpu_after_c": temp(),
           "throttled": hex(throttled())}
    save(rec)
    print(f"{ts()} explain #{n:2d} {secs:5.1f} s  CPU {rec['cpu_after_c']:.1f} C  "
          f"{'PASS' if not failed else 'FAIL ' + ','.join(failed)} | {text[:120]}", flush=True)

QUESTIONS = ["Is my plant okay?", "Why did you water?", "Water it now!", "What is the capital of France?",
             "Is the tank empty?", "Why is the light on?"]
if not stop.is_set():
    d = ch.load_facts()
    for n, q in enumerate(QUESTIONS, 1):
        if stop.is_set():
            break
        cpu_before = temp()
        t0 = time.time()
        try:
            text, src = ch.answer(q, d)
            err = ""
        except Exception as e:  # noqa: BLE001
            text, src, err = "", "error", str(e)
        secs = time.time() - t0
        save({"type": "chat", "n": n, "question": q, "answer": text, "source": src, "error": err,
              "seconds": round(secs, 1), "cpu_before_c": cpu_before, "cpu_after_c": temp(),
              "throttled": hex(throttled()), "facts_from": d.get("timestamp", "")})
        print(f"{ts()} chat #{n} {secs:5.1f} s  CPU {temp():.1f} C  Q: {q}  A [{src}]: {text[:120]}", flush=True)

stop.set()
rows = [json.loads(l) for l in open(OUT, encoding="utf-8")]
ex = [r for r in rows if r["type"] == "explain"]
cht = [r for r in rows if r["type"] == "chat"]
warm = [r["seconds"] for r in ex[1:]]
summary = {"type": "SUMMARY", "explanations_done": len(ex), "explanations_passed": sum(r["passed"] for r in ex),
           "explain_mean_s": round(sum(warm) / len(warm), 1) if warm else None,
           "explain_max_s": max(warm) if warm else None, "chat_done": len(cht),
           "chat_mean_s": round(sum(r["seconds"] for r in cht) / len(cht), 1) if cht else None,
           "cpu_start_c": t_start, "cpu_max_c": max(temps) if temps else None, "cpu_end_c": temp(),
           "throttled_end": hex(throttled()), "stopped_by_watchdog": any(r["type"] == "STOP" for r in rows)}
save(summary)
print(f"{ts()} SUMMARY {json.dumps(summary)}", flush=True)
