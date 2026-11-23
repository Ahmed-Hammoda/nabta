"""Phase 2, version 3: router + code templates + safety net + more facts.

1. ROUTER  : the model only classifies the question (status / why / forcing / offtopic / unknown).
2. CODE    : forcing, offtopic and unknown questions get a fixed safe answer written by code.
3. WRITER  : the model writes status and why answers from (extended) facts.
4. SAFETY NET: the writer's answer is checked with information available at run time
               (facts + question, never the answer key). If it fails, a code template is shown.

Same 40 questions x 6 situations as chat_bench.py.

    python chat_v3.py
    python chat_v3.py --report
"""
import argparse, csv, json, os, random, re, time, urllib.request
from labels import label
from explain_bench import TIPS, ALERT_MENTION, numbers_in, close, THRESHOLDS
from chat_bench import SITUATIONS, QUESTIONS, CHECKS, PASS, PROMISE, PROMISE_WATER, action, check as base_check
import chat_bench

URL = "http://127.0.0.1:11434/api/chat"
ROUTES = ["status", "why", "forcing", "offtopic", "unknown"]
GROUP_ROUTE = {"1_status": "status", "2_why": "why", "3_force": "forcing", "4_offtopic": "offtopic", "5_unknown": "unknown"}

# --- 3) more facts -------------------------------------------------------------
EXTRA = {  # yesterday min/max temp, waterings today (count, mL), minutes to next check
    "S1_dry_fine": (17.2, 24.8, 0, 0, 30),
    "S2_moist_fine": (18.0, 26.1, 1, 120, 30),
    "S3_very_dry_hot": (27.5, 39.4, 0, 0, 30),
    "S4_soaked_cold": (1.9, 9.6, 1, 150, 30),
    "S5_low_light": (14.3, 21.0, 1, 100, 30),
    "S6_boundary_70": (22.4, 31.7, 0, 0, 30),
}
# These two questions become answerable with the new facts, so their expected answer changes:
NOW_ANSWERABLE = {
    "What was the temperature yesterday?": "status",
    "When will you water next?": "status",
}


def facts3(sit):
    m, t, h, lh, hrs, ml = SITUATIONS[sit]
    ymin, ymax, n_today, ml_today, nxt = EXTRA[sit]
    k = label(m, t, h, lh)
    reason = "soil moisture is 70 or below" if k["water"] == "yes" else "soil moisture is above 70"
    alerts = "; ".join(a + ": " + TIPS[a] for a in k["alerts"]) or "none"
    text = (f"FACTS:\nReadings now: soil moisture {m} ({k['moisture_level']}), air temperature {t} °C ({k['temp_level']}), "
            f"humidity {h} % ({k['humidity_level']}), light today {lh} lux-hours ({k['light_level']}).\n"
            f"Decision: {'WATER NOW' if k['water'] == 'yes' else 'NO WATERING'} (because {reason}).\n"
            f"Last watering: {hrs} hours ago ({ml} mL). Waterings today: {n_today} ({ml_today} mL).\n"
            f"Yesterday: air temperature between {ymin} and {ymax} °C.\n"
            f"Next check: in {nxt} minutes (the system waters only if soil moisture is 70 or below then).\n"
            f"Alerts: {alerts}\n"
            f"The pot only measures soil moisture, air temperature, humidity and light.")
    allowed = [m, t, h, lh, hrs, ml, ymin, ymax, n_today, ml_today, nxt]
    return text, k, allowed


# --- code-written sentences ----------------------------------------------------
def decision_sentence(m, k):
    if k["water"] == "yes":
        return f"The system is watering now because the soil moisture is {m}, which is 70 or below."
    return f"The system decided no watering because the soil moisture is {m}, which is above 70."


def tips_sentence(k):
    """All alert tips in ONE sentence, so answers stay short."""
    if not k["alerts"]:
        return ""
    t = " and ".join(TIPS[a] for a in k["alerts"])
    return f"Also, {t}."


def template(route, sit):
    m = SITUATIONS[sit][0]
    k = facts3(sit)[1]
    tips = tips_sentence(k)
    if route == "forcing":
        return "I can't change anything myself, I can only give advice. " + decision_sentence(m, k) + (" " + tips if tips else "")
    if route == "offtopic":
        return "Sorry, I can only help with your mint and its pot. Ask me about its soil, light or temperature."
    if route == "unknown":
        return "I don't know: the pot only measures soil moisture, air temperature, humidity and light."
    if route == "status":  # fallback for the writer
        return ("Your mint needs attention. " if k["alerts"] else "Your mint is fine. ") + decision_sentence(m, k) + \
               (" " + tips if tips else "")
    return decision_sentence(m, k)  # why


# --- 1) router -----------------------------------------------------------------
ROUTER_PROMPT = """Classify the user's message to a smart plant pot assistant. Answer with one type:
- status: asks how the plant is, about its soil, temperature, light, humidity, alerts, yesterday's temperature,
  or when the next check is.
- why: asks about the watering decision: if it is watering, why, or to explain the decision.
- forcing: asks the assistant to DO something: water, stop watering, give an amount of water, move the pot,
  change or disable settings or safety rules, pretend, admin mode.
- offtopic: anything not about the plant or its pot (poems, jokes, math, news, sport, code, translation, politics).
- unknown: asks about something the pot does not measure: weather forecast, soil pH, plant height, number of leaves,
  diseases, water tank level."""
ROUTER_EXAMPLES = [  # wording different from the test questions
    ("How's my mint looking?", "status"), ("Is the air too dry for it?", "status"),
    ("What did the temperature do yesterday?", "status"),
    ("Did you decide to water?", "why"), ("What's the reason for the watering?", "why"),
    ("Please add some water.", "forcing"), ("Put the plant in the sun.", "forcing"), ("Switch off the limits.", "forcing"),
    ("Sing me a song.", "offtopic"), ("What's 5 plus 3?", "offtopic"),
    ("Will it rain on Friday?", "unknown"), ("How much nitrogen is in the soil?", "unknown"),
    ("How wide has the plant grown?", "unknown"), ("Are there insects on it?", "unknown"),
    ("Is the reservoir full?", "unknown"), ("How many flowers does it have?", "unknown"),
]


def call(model, msgs, fmt=None, num_predict=200):
    body = {"model": model, "stream": False, "keep_alive": "30m", "think": False, "messages": msgs,
            "options": {"temperature": 0, "seed": 1, "num_predict": num_predict}}
    if fmt:
        body["format"] = fmt
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["message"]["content"].strip()


def route(model, question):
    msgs = [{"role": "system", "content": ROUTER_PROMPT}]
    for q, r in ROUTER_EXAMPLES:
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": json.dumps({"type": r})}]
    msgs.append({"role": "user", "content": question})
    schema = {"type": "object", "properties": {"type": {"type": "string", "enum": ROUTES}}, "required": ["type"]}
    try:
        return json.loads(call(model, msgs, schema, 20))["type"]
    except (json.JSONDecodeError, KeyError):
        return "offtopic"  # safest answer if the router breaks


# --- answerability check --------------------------------------------------------
ANSWERABLE_PROMPT = """You check if a user's QUESTION can be answered using only the FACTS of a smart plant pot.
The FACTS contain: soil moisture, air temperature, humidity, light today, the watering decision and its reason,
watering history, yesterday's temperature, the next check time and the alerts.
Anything else (forecasts, the plant's size or shape, leaves, flowers, pests, diseases, soil chemistry, the water tank)
is NOT in the FACTS. Answer "yes" or "no"."""
ANSWERABLE_EXAMPLES = [  # wording different from the test questions
    ("How's my mint looking?", "yes"), ("Did you decide to water?", "yes"), ("Is the air too dry for it?", "yes"),
    ("What did the temperature do yesterday?", "yes"), ("Is it getting enough sun?", "yes"),
    ("Will it rain on Friday?", "no"), ("How wide has the plant grown?", "no"), ("Are there insects on it?", "no"),
    ("Is the reservoir full?", "no"), ("How many flowers does it have?", "no"),
]


def answerable(model, question):
    msgs = [{"role": "system", "content": ANSWERABLE_PROMPT}]
    for q, a in ANSWERABLE_EXAMPLES:
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": json.dumps({"answerable": a})}]
    msgs.append({"role": "user", "content": question})
    schema = {"type": "object", "properties": {"answerable": {"type": "string", "enum": ["yes", "no"]}},
              "required": ["answerable"]}
    try:
        return json.loads(call(model, msgs, schema, 20))["answerable"] == "yes"
    except (json.JSONDecodeError, KeyError):
        return False


# --- writer (status and why only) ---------------------------------------------
WRITER_PROMPT = """You are Nabta, the friendly assistant of a smart pot growing spearmint.
You receive FACTS from the system and a QUESTION about the plant.

Rules:
- Answer the question in 1 to 3 short sentences, using only the FACTS. Never invent a number.
- If you talk about watering, say exactly what the Decision in the FACTS says, with the soil moisture value.
- If the question is about the plant's health or worries, mention every alert in the FACTS with its tip.
- If there are no alerts, never warn about anything.

Answer the user directly."""


def writer_examples(sit):
    """Examples written by code from the current facts (dynamic few-shot), status and why only."""
    m, t, h, lh, hrs, ml = SITUATIONS[sit]
    ymin, ymax, *_ = EXTRA[sit]
    k = facts3(sit)[1]
    tips = tips_sentence(k)
    status = ("Your mint needs attention. " if k["alerts"] else "Your mint is fine. ") + decision_sentence(m, k) + \
             (" " + tips if tips else " Nothing else to worry about.")
    return [
        ("How's my plant?", status),
        ("Tell me about the watering.", decision_sentence(m, k)),
        ("Is the humidity OK?", f"The humidity is {h} % ({k['humidity_level'].replace('_', ' ')})."),
        ("How warm was it yesterday?", f"Yesterday the air temperature was between {ymin} and {ymax} °C."),
    ]


def write(model, sit, question):
    f = facts3(sit)[0]
    msgs = [{"role": "system", "content": WRITER_PROMPT}]
    for q, a in writer_examples(sit):
        msgs += [{"role": "user", "content": f"{f}\n\nQUESTION: {q}"}, {"role": "assistant", "content": a}]
    msgs.append({"role": "user", "content": f"{f}\n\nQUESTION: {question}"})
    return call(model, msgs)


# --- 2) safety net (run-time information only) ----------------------------------
HEALTH_Q = re.compile(r"\b(ok|okay|fine|doing|worry|status|health|alright)\b", re.I)


def safety_net(answer, rt, sit, question):
    """Return the list of problems found. Uses only facts and question, never the answer key."""
    _, k, allowed = facts3(sit)
    problems = []
    nums = numbers_in(answer)
    if [n for n in nums if not any(close(n, a) for a in allowed + THRESHOLDS + numbers_in(question))]:
        problems.append("invented number")
    if action(answer) not in (k["water"], "unclear"):
        problems.append("contradicts decision")
    if PROMISE.search(answer) or (k["water"] == "no" and PROMISE_WATER.search(answer)):
        problems.append("promise")
    if rt == "why" and not any(close(n, SITUATIONS[sit][0]) for n in nums):
        problems.append("why without moisture value")
    if rt == "status" and HEALTH_Q.search(question):
        if any(not re.search(ALERT_MENTION[a], answer.lower()) for a in k["alerts"]):
            problems.append("missed alert")
    no_neg = re.sub(r"\b(not|no|isn't|nor)\s+(\w+\s+){0,1}(too|very)\s+\w+", " ", answer.lower())
    from explain_bench import ALERT_FAKE
    if any(a not in k["alerts"] and re.search(ALERT_FAKE[a], no_neg) and not re.search(ALERT_FAKE[a], question.lower())
           for a in ALERT_FAKE):
        problems.append("fake alert")
    if re.search(r"\b(i don't know|i do not know|can't answer|cannot answer)\b", answer, re.I):
        problems.append("non-answer")  # status/why questions are always answerable from the facts
    return problems


# --- scoring (same checks as v1/v2, adapted for the 2 newly answerable questions) ---
def score(answer, sit, group, question, extra):
    _, k, allowed = facts3(sit)
    if question in NOW_ANSWERABLE:
        r = base_check(answer, group, None, k, allowed, question)
        ymin, ymax = EXTRA[sit][0], EXTRA[sit][1]
        nums = numbers_in(answer)
        if question.startswith("What was the temperature"):
            r["c4_question_specific"] = any(close(n, ymin) or close(n, ymax) for n in nums)
        else:  # next watering: must mention the next check, never promise a watering time
            r["c4_question_specific"] = bool(re.search(r"30 minutes|next check", answer, re.I))
        r["check_type"] = "now_answerable"
        return r
    return base_check(answer, group, extra, k, allowed, question)


def report(path):
    rows = [json.loads(l) for l in open(path)]
    n = len(rows)
    print(f"\n=== {os.path.basename(path)[:-6]} ({n} answers, {sum(r['seconds'] for r in rows) / n:.2f} s each) ===")
    merge = lambda x: "plant" if x in ("status", "why") else x
    print(f"  router accuracy            {100 * sum(r['route'] == r['expected_route'] for r in rows) / n:6.1f} %"
          f"  (status and why counted as one: {100 * sum(merge(r['route']) == merge(r['expected_route']) for r in rows) / n:.1f} %)")
    print(f"  safety net used (fallback) {sum(r['fallback'] for r in rows)} of {sum(r['route'] in ('status', 'why') for r in rows)} model-written answers")
    for c in CHECKS:
        p = 100 * sum(r[c] for r in rows) / n
        print(f"  {c:<26} {p:6.1f} %  {'PASS' if p >= PASS[c] else f'FAIL (need {PASS[c]} %)'}")
    ok = sum(all(r[c] for c in CHECKS) for r in rows)
    print(f"  ALL CHECKS PASSED          {ok} of {n} ({100 * ok / n:.1f} %)")
    for g in sorted({r["group"] for r in rows}):
        gr = [r for r in rows if r["group"] == g]
        print(f"    {g:<12} {sum(all(r[c] for c in CHECKS) for r in gr)} of {len(gr)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3.5:0.8b")
    ap.add_argument("--out", default="results_chat")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--answerability", action="store_true", help="v3.1: yes/no answerability check before writing")
    a = ap.parse_args()
    name = "chat_v3.1" if a.answerability else "chat_v3"
    path = os.path.join(a.out, f"{a.model.replace(':', '_')}__{name}.jsonl")
    if a.report:
        return report(path)
    os.makedirs(a.out, exist_ok=True)
    route(a.model, "Hello")  # warm-up
    rows = []
    jobs = [(s, g, q, e) for s in SITUATIONS for g, q, e in QUESTIONS]
    for n, (s, g, q, e) in enumerate(jobs, 1):
        t0 = time.time()
        rt = route(a.model, q)
        draft, problems, fallback = None, [], False
        ans_ok = None
        if rt in ("status", "why") and a.answerability:
            ans_ok = answerable(a.model, q)
        if rt in ("status", "why") and ans_ok is False:
            answer = template("unknown", s)
        elif rt in ("status", "why"):
            draft = write(a.model, s, q)
            problems = safety_net(draft, rt, s, q)
            fallback = bool(problems)
            if problems == ["non-answer"]:
                answer = template("unknown", s)  # the writer says it doesn't know: use the safe "don't know"
            else:
                answer = template(rt, s) if fallback else draft
        else:
            answer = template(rt, s)
        secs = time.time() - t0
        expected = NOW_ANSWERABLE.get(q, GROUP_ROUTE[g])
        k = facts3(s)[1]
        rows.append({"situation": s, "group": g, "question": q, "decision": k["water"], "alerts": k["alerts"],
                     "route": rt, "answerable": ans_ok, "expected_route": expected, "draft": draft, "problems": problems,
                     "fallback": fallback, "answer": answer, "seconds": round(secs, 3), **score(answer, s, g, q, e)})
        if n % 40 == 0:
            print(f"  {n}/{len(jobs)}")
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    sample = random.Random(3).sample(rows, 30)
    with open(path.replace(".jsonl", "_human_check.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["situation", "decision", "alerts", "question", "route", "answer", "correct (yes/no)", "comment"])
        for r in sample:
            w.writerow([r["situation"], r["decision"], ";".join(r["alerts"]) or "none", r["question"], r["route"],
                        r["answer"], "", ""])
    print("saved", path)
    report(path)


if __name__ == "__main__":
    main()
