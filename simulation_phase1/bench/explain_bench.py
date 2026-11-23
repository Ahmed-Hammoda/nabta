"""Phase 1 validation: can the model EXPLAIN the code's decision correctly?

The code's decision (always correct) is given to the model; the model writes 1-2 sentences.
Each explanation is checked automatically, and 30 are exported for a human check.

    python explain_bench.py                         # qwen3.5:0.8b, prompts e1 and e2
    python explain_bench.py --model qwen3.5:0.8b --prompts e2 --limit 20
    python explain_bench.py --report                # only print the summary
"""
import argparse, csv, json, os, random, re, time, urllib.request

URL = "http://127.0.0.1:11434/api/chat"

SYSTEM = """You are Nabta, the friendly assistant of a smart pot growing spearmint.
The system has already decided what to do. Your only job is to explain that decision to the user.

Rules:
- Write 1 or 2 short sentences, 40 words maximum.
- Say clearly whether the system is watering now or not.
- Give the soil moisture value.
- Mention every alert in the list, with a simple tip. If the alert list is "none", do not warn about anything.
- Use only numbers from the input. Never change the decision.

Alert meanings:
- DRY_DANGER: the soil is very dry, the plant may wilt.
- TOO_WET: the soil is soaked, the roots can rot.
- HEAT_DANGER: it is too hot, move the pot to the shade.
- COLD_DANGER: it is too cold, bring the pot inside.
- LOW_LIGHT: not enough light today, move the pot to a brighter place.

Answer with the explanation only."""

# Example explanations for prompt e2 (values not in the test set)
EXAMPLES = [
    ((64.2, 22.0, 55.0, 150000, "dry", "optimal", "outside_optimal", "acceptable"), "yes", [],
     "Your soil is dry at 64.2, so I'm watering your mint now. Everything else looks fine."),
    ((83.0, 31.0, 66.0, 300000, "acceptable", "acceptable", "optimal", "optimal"), "no", [],
     "No watering needed: the soil moisture is 83.0, which is still moist enough."),
    ((18.5, 38.2, 30.0, 60000, "danger_dry", "danger", "outside_optimal", "low"), "yes",
     ["DRY_DANGER", "HEAT_DANGER", "LOW_LIGHT"],
     "The soil is very dry at 18.5, so I'm watering now. It's too hot (38.2 °C), so move the pot to the shade, "
     "and give it more light tomorrow."),
    ((102.3, 2.5, 80.0, 120000, "too_wet", "danger", "outside_optimal", "acceptable"), "no",
     ["TOO_WET", "COLD_DANGER"],
     "Not watering: the soil is soaked at 102.3 and the roots could rot. It's too cold (2.5 °C), please bring the pot inside."),
]

TIPS = {
    "DRY_DANGER": "the soil is very dry, the plant may wilt",
    "TOO_WET": "the soil is soaked, the roots can rot",
    "HEAT_DANGER": "it is too hot, move the pot to the shade",
    "COLD_DANGER": "it is too cold, bring the pot inside",
    "LOW_LIGHT": "not enough light today, move the pot to a brighter place",
}

SYSTEM_E3 = """You are Nabta, the friendly assistant of a smart pot growing spearmint.
The system has already decided what to do. Your only job is to explain that decision to the user.

Rules:
- Write 1 or 2 short sentences, 40 words maximum.
- Start by saying whether the system is watering now or not, with the soil moisture value.
- Then mention ONLY the alerts listed in "Alerts to mention", using their tip. Nothing else.
- If "Alerts to mention" is "none", end with "Everything else looks fine."
- Use only numbers from the input. Never change the decision.

Answer with the explanation only."""

# One alert per example, so the model has no combination to copy
EXAMPLES_E3 = [
    ((64.2, 22.0, 55.0, 150000, "dry", "optimal", "outside_optimal", "acceptable"), "yes", [],
     "Your soil is dry at 64.2, so I'm watering your mint now. Everything else looks fine."),
    ((83.0, 31.0, 66.0, 300000, "acceptable", "acceptable", "optimal", "optimal"), "no", [],
     "No watering needed: the soil moisture is 83.0. Everything else looks fine."),
    ((18.5, 22.0, 30.0, 200000, "danger_dry", "optimal", "outside_optimal", "acceptable"), "yes", ["DRY_DANGER"],
     "I'm watering now: the soil moisture is 18.5. The soil is very dry, so the plant may wilt."),
    ((102.3, 20.0, 80.0, 200000, "too_wet", "optimal", "outside_optimal", "acceptable"), "no", ["TOO_WET"],
     "Not watering: the soil moisture is 102.3. The soil is soaked, so the roots can rot."),
    ((75.0, 38.2, 40.0, 300000, "acceptable", "danger", "outside_optimal", "optimal"), "no", ["HEAT_DANGER"],
     "No watering needed: the soil moisture is 75.0. It is too hot (38.2 °C), please move the pot to the shade."),
    ((55.0, 2.5, 70.0, 200000, "dry", "danger", "optimal", "acceptable"), "yes", ["COLD_DANGER"],
     "I'm watering now: the soil moisture is 55.0. It is too cold (2.5 °C), please bring the pot inside."),
    ((80.0, 20.0, 50.0, 60000, "acceptable", "optimal", "outside_optimal", "low"), "no", ["LOW_LIGHT"],
     "No watering needed: the soil moisture is 80.0. There was not enough light today, so move the pot to a brighter place."),
]

# --- automatic checks -------------------------------------------------------
# "not"/"no" at most 2 words before "water" (so "will not wilt if you water" is not a refusal)
NEG = re.compile(r"\b(not|no|don't|do not|won't|will not|isn't)\s+(\w+\s+){0,2}water|no need\b[^.]{0,25}water"
                 r"|without water|skip\w* (the )?water|hold\w* off|doesn't need (any )?water|does not need (any )?water",
                 re.I)
POS = re.compile(r"water(ing)? (it |your \w+ |the \w+ )?now|decided to water|i'm watering|i am watering|i'll water"
                 r"|i will water|watering (your|it|the)\b|giving (it |your \w+ )?water|adding water"
                 r"|(should|need to|must) water", re.I)
ALERT_MENTION = {
    "DRY_DANGER": r"very dry|extremely dry|too dry|critically dry|severely dry|wilt|danger",
    "TOO_WET": r"too wet|soak|waterlog|saturat|soggy|root rot|roots? (can|could|may|might) rot|overwater",
    "HEAT_DANGER": r"too hot|very hot|heat|shade|high temperature",
    "COLD_DANGER": r"too cold|very cold|cold|frost|freez|inside|indoors",
    "LOW_LIGHT": r"low light|more light|not enough light|lack of light|insufficient light|brighter|light is low|more sun",
}
ALERT_FAKE = {  # strong words that should not appear when the alert is absent
    "DRY_DANGER": r"very dry|extremely dry|critically dry|severely dry|wilt",
    "TOO_WET": r"too wet|soaked|waterlog|saturat|soggy|root rot|roots? (can|could|may|might) rot",
    "HEAT_DANGER": r"too hot|very hot|heat stress|extreme heat|move [^.]{0,20}shade",
    "COLD_DANGER": r"too cold|very cold|frost|freez|bring [^.]{0,20}inside",
    "LOW_LIGHT": ALERT_MENTION["LOW_LIGHT"],
}
THRESHOLDS = [4, 15, 24, 25, 36, 60, 70, 90, 100, 90000, 285000, 1, 2]
NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def stated_action(text):
    if NEG.search(text):
        return "no"
    if POS.search(text):
        return "yes"
    return "unclear"


def numbers_in(text):
    out = []
    for s in NUM.findall(text):
        try:
            out.append(float(s.replace(",", "")))
        except ValueError:
            pass
    return out


def close(x, y):
    return abs(x - y) <= max(0.15, 0.01 * abs(y)) or (round(y) == x)


def sentences(text):
    t = re.sub(r"(\d)\.(\d)", r"\1,\2", text.strip())
    return [s for s in re.split(r"[.!?]+(?:\s|$)", t) if s.strip()]


def check(text, case):
    i, k = case["input"], case["key"]
    allowed = [i["soil_moisture_index"], i["air_temp_c"], i["humidity_rh"], i["light_lux_now"],
               i["light_lux_hours_24h"]] + THRESHOLDS
    nums = numbers_in(text)
    invented = [n for n in nums if not any(close(n, a) for a in allowed)]
    low = text.lower()
    missing = [a for a in k["alerts"] if not re.search(ALERT_MENTION[a], low)]
    no_neg = re.sub(r"\b(not|no|isn't|nor)\s+(\w+\s+){0,1}(too|very)\s+\w+", " ", low)
    fake = [a for a in ALERT_FAKE if a not in k["alerts"] and re.search(ALERT_FAKE[a], no_neg)]
    action = stated_action(text)
    words = len(text.split())
    return {
        "action_stated": action,
        "c1_same_action": action == k["water"],
        "c2_no_invented_numbers": not invented, "invented": invented,
        "c3_moisture_quoted": any(close(n, i["soil_moisture_index"]) for n in nums),
        "c4_all_alerts_mentioned": not missing, "missing_alerts": missing,
        "c5_no_fake_alert": not fake, "fake_alerts": fake,
        "c6_short": len(sentences(text)) <= 2 and words <= 40, "words": words,
    }


# --- model call -------------------------------------------------------------
def user_message(vals, levels, water, alerts, with_tips=False):
    m, t, h, lh = vals
    ml, tl, hl, ll = levels
    reason = "soil moisture is 70 or below" if water == "yes" else "soil moisture is above 70"
    return (f"Readings: soil moisture {m} ({ml}), air temperature {t} °C ({tl}), humidity {h} % ({hl}), "
            f"light today {int(lh)} lux-hours ({ll}).\n"
            f"Decision: {'WATER NOW' if water == 'yes' else 'NO WATERING'} (because {reason}).\n"
            + (f"Alerts to mention: {'; '.join(a + ': ' + TIPS[a] for a in alerts) if alerts else 'none'}"
               if with_tips else f"Alerts: {', '.join(alerts) if alerts else 'none'}"))


def messages(prompt, case):
    e3 = prompt == "e3"
    msgs = [{"role": "system", "content": SYSTEM_E3 if e3 else SYSTEM}]
    if e3:
        for v, w, a, txt in EXAMPLES_E3:
            msgs += [{"role": "user", "content": user_message(v[:4], v[4:], w, a, True)},
                     {"role": "assistant", "content": txt}]
    if prompt == "e2":
        for v, w, a, txt in EXAMPLES:
            msgs += [{"role": "user", "content": user_message(v[:4], v[4:], w, a)},
                     {"role": "assistant", "content": txt}]
    i, k = case["input"], case["key"]
    vals = (i["soil_moisture_index"], i["air_temp_c"], i["humidity_rh"], i["light_lux_hours_24h"])
    levels = (k["moisture_level"], k["temp_level"], k["humidity_level"], k["light_level"])
    msgs.append({"role": "user", "content": user_message(vals, levels, k["water"], k["alerts"], e3)})
    return msgs


def ask(model, msgs, think):
    body = {"model": model, "stream": False, "keep_alive": "30m", "messages": msgs,
            "options": {"temperature": 0, "seed": 1, "num_predict": 150}}
    if think is not None:
        body["think"] = think
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.loads(r.read())
    return out["message"]["content"].strip(), time.time() - t0


# --- report -----------------------------------------------------------------
CHECKS = ["c1_same_action", "c2_no_invented_numbers", "c3_moisture_quoted", "c4_all_alerts_mentioned",
          "c5_no_fake_alert", "c6_short"]
PASS = {"c1_same_action": 100, "c2_no_invented_numbers": 100, "c4_all_alerts_mentioned": 95,
        "c5_no_fake_alert": 95, "c6_short": 95}


def report(outdir):
    cases = {c["id"]: c for c in (json.loads(l) for l in open("testset.jsonl"))}
    for f in sorted(os.listdir(outdir)):
        if not f.endswith(".jsonl"):
            continue
        rows = [json.loads(l) for l in open(os.path.join(outdir, f))]
        rows = [{**r, **check(r["explanation"], cases[r["id"]])} for r in rows]  # re-score
        with open(os.path.join(outdir, f), "w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        n = len(rows)
        print(f"\n=== {f[:-6]} ({n} explanations, {sum(r['seconds'] for r in rows) / n:.2f} s each) ===")
        for c in CHECKS:
            p = 100 * sum(r[c] for r in rows) / n
            need = PASS.get(c)
            verdict = "" if need is None else ("PASS" if p >= need else f"FAIL (need {need} %)")
            print(f"  {c:<26} {p:6.1f} %  {verdict}")
        unclear = sum(r["action_stated"] == "unclear" for r in rows)
        print(f"  action unclear for the keyword check: {unclear} (read them in the human check)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3.5:0.8b")
    ap.add_argument("--prompts", nargs="+", default=["e1", "e2", "e3"])
    ap.add_argument("--think", choices=["default", "off", "on"], default="off")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="results_explain")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        return report(a.out)
    think = {"default": None, "off": False, "on": True}[a.think]
    os.makedirs(a.out, exist_ok=True)
    cases = [json.loads(l) for l in open("testset.jsonl")]
    if a.limit:
        cases = cases[:a.limit]
    for p in a.prompts:
        path = os.path.join(a.out, f"{a.model.replace(':', '_')}__{p}.jsonl")
        if os.path.exists(path):
            print("skip (done):", path)
            continue
        ask(a.model, messages(p, cases[0]), think)  # warm-up
        rows = []
        for n, c in enumerate(cases, 1):
            text, secs = ask(a.model, messages(p, c), think)
            rows.append({"id": c["id"], "kind": c["kind"], "seconds": round(secs, 3),
                         "decision": c["key"]["water"], "alerts": c["key"]["alerts"],
                         "moisture": c["input"]["soil_moisture_index"], "explanation": text, **check(text, c)})
            if n % 25 == 0:
                print(f"  {p} {n}/{len(cases)}")
        with open(path, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        # 30 random explanations for the human check
        sample = random.Random(3).sample(rows, min(30, len(rows)))
        with open(path.replace(".jsonl", "_human_check.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "moisture", "decision", "alerts", "explanation", "correct (yes/no)", "comment"])
            for r in sample:
                w.writerow([r["id"], r["moisture"], r["decision"], ";".join(r["alerts"]) or "none",
                            r["explanation"], "", ""])
        print("saved", path)
    report(a.out)


if __name__ == "__main__":
    main()
