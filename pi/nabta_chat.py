#!/usr/bin/env python3
"""Nabta chat: ask about your mint. qwen3.5:0.8b answers from the latest decision.

Uses the tested chat v3.1 pipeline (phase 1: 96 % of 240 answers passed every check):
  router (model) -> "can it be answered from the facts?" (model) -> writer (model) -> safety net (code).
Requests to DO something, off-topic and unanswerable questions get a fixed safe answer.
If the latest decision has a sensor fault, status and why questions get the fault message.

    python3 nabta_chat.py          (type your question, empty line or Ctrl+C to quit)
"""
import csv, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rules_v2
import chat_bench, chat_v3
import nabta_paths as paths     # logs/<YYYY-MM>/decisions.csv and log_30min.csv

MODEL = "qwen3.5:0.8b"

# the chat code was written for rules v1; use rules v2 (TOO_WET at 98)
chat_bench.label = rules_v2.label
chat_v3.label = rules_v2.label


def latest():
    rows = paths.read_csv("decisions.csv", last=2)
    if not rows:
        sys.exit("No decisions yet: run  python3 nabta_controller.py --once  first.")
    return rows[-1], rows


def load_facts():
    """Put the live readings into the chat code's FACTS (situation 'LIVE')."""
    d, rows = latest()
    now = datetime.now().astimezone()
    watered = [r for r in rows if r["pump_action"].startswith(("WATERED", "WOULD WATER"))]
    if watered:
        last = datetime.fromisoformat(watered[-1]["timestamp"])
        hrs = round((now - last).total_seconds() / 3600, 1)
        ml = 150
    else:
        hrs, ml = 0, 0
    today = [r for r in watered if datetime.fromisoformat(r["timestamp"]).date() == now.date()]
    temps = []
    for r in paths.read_csv("log_30min.csv", last=2):
        try:
            t = datetime.fromisoformat(r["timestamp"])
            if (now.date() - t.date()).days == 1 and r["air_temp_c"]:
                temps.append(float(r["air_temp_c"]))
        except ValueError:
            pass
    ymin, ymax = (round(min(temps), 1), round(max(temps), 1)) if temps else (float(d["air_temp_c"] or 0),) * 2
    m, t, h, lh = (float(d[c] or 0) for c in ("soil_moisture_index", "air_temp_c", "humidity_rh", "light_lux_hours_24h"))
    chat_bench.SITUATIONS["LIVE"] = (m, t, h, lh, hrs, ml)
    chat_v3.EXTRA["LIVE"] = (ymin, ymax, len(today), ml * len(today), 30)
    return d


def answer(q, d):
    rt = chat_v3.route(MODEL, q)
    fault = d["faults"] != "none"
    if fault and rt in ("status", "why"):
        return d["message"], "fixed (sensor fault)"
    if rt in ("status", "why"):
        if chat_v3.answerable(MODEL, q) is False:
            return chat_v3.template("unknown", "LIVE"), "template (unknown)"
        draft = chat_v3.write(MODEL, "LIVE", q)
        problems = chat_v3.safety_net(draft, rt, "LIVE", q)
        if problems == ["non-answer"]:
            return chat_v3.template("unknown", "LIVE"), "template (unknown)"
        if problems:
            return chat_v3.template(rt, "LIVE"), "template (safety net: " + ", ".join(problems) + ")"
        return draft, MODEL
    return chat_v3.template(rt, "LIVE"), "template (" + rt + ")"


def main():
    d = load_facts()
    print(f"Nabta chat. Latest reading {d['timestamp']}: soil {d['soil_moisture_index']}, "
          f"{d['air_temp_c']} C, decision: water {d['water_decision']}, faults: {d['faults']}.")
    print("Ask about your mint (empty line to quit).\n")
    while True:
        try:
            q = input("you  > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        try:
            text, src = answer(q, d)
        except Exception as e:  # noqa: BLE001
            text, src = "Sorry, the assistant is not available right now.", f"error: {e}"
        print(f"nabta> {text}\n       [{src}]\n")


if __name__ == "__main__":
    main()
