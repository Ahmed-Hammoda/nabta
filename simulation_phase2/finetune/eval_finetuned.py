"""Step 4 (laptop, Ollama running): compare the base model and the fine-tuned model.

Same tests, same settings (temperature 0, seed 1, thinking off) for both models:
  1. DECISION    rules v3 (pump + grow light + tank): the v3 30-day dataset (../dataset_v3), short
                 fine-tune prompt; every fault, watering and light-switch row + up to 20 per scenario
  2. EXPLAIN     phase 1 explanation test, prompt e3, 184 cases (simulation_phase1/bench/explain_bench.py)
  3. CHAT        phase 1 chat test v2 (240 answers) and chat v3.1 (router + safety net, 240 answers)

"Skill kept" = the fine-tuned score is at most 2 points below the base score.

    python eval_finetuned.py --ft nabta-qwen3.5          # about 20-30 min for both models
    python eval_finetuned.py --ft nabta-qwen3.5 --report # only print the comparison again
"""
import argparse, csv, glob, json, os, random, subprocess, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(HERE, "..", "code")
BENCH = os.path.join(HERE, "..", "..", "simulation_phase1", "bench")
OUT = os.path.join(HERE, "..", "results", "finetune_eval")
EX_DIR, CHAT_DIR = os.path.join(OUT, "explain"), os.path.join(OUT, "chat")   # one folder per test
sys.path.insert(0, CODE)
import sim_bench_v2 as sb
import make_train_data as mtd           # v3: SYSTEM prompt, input columns and answer keys
DATA_V3 = os.path.join(HERE, "..", "dataset_v3")

EX_PASS = ["c1_same_action", "c2_no_invented_numbers", "c4_all_alerts_mentioned", "c5_no_fake_alert", "c6_short"]


def name(m):
    return m.replace(":", "_")


def load_cases_v3():
    sens = list(csv.DictReader(open(os.path.join(DATA_V3, "sim_sensor_30days.csv"), encoding="utf-8")))
    key = list(csv.DictReader(open(os.path.join(DATA_V3, "sim_key_30days.csv"), encoding="utf-8")))
    lst = lambda v: [] if v == "none" else v.split(";")
    must, by = [], defaultdict(list)
    for n, (sr, k) in enumerate(zip(sens, key)):
        inp = {c: float(sr[c]) for c in mtd.COLS[:5]}
        inp.update({c: int(sr[c]) for c in mtd.COLS[5:]})
        c = {"id": f"s{n:04d}", "time": sr["timestamp"][:16], "scenario": k["scenario"], "input": inp,
             "key": {x: (lst(k[x]) if x in ("alerts", "faults") else k[x]) for x in mtd.KEYS}}
        switch = (k["light"] == "on") != bool(inp["light_on"])
        if c["key"]["faults"] or k["water"] == "yes" or switch:
            must.append(c)
        else:
            by[k["scenario"]].append(c)
    rnd = random.Random(7)
    cases = must
    for scen in sorted(by):
        cases += rnd.sample(by[scen], min(20, len(by[scen])))
    return sorted(cases, key=lambda c: c["id"])


def run_decide_v3(model):
    path = os.path.join(OUT, f"{name(model)}__A_ft_v3.jsonl")
    if os.path.exists(path):
        print("skip (done):", path); return
    cases = load_cases_v3()
    msgs = lambda inp: [{"role": "system", "content": mtd.SYSTEM}, {"role": "user", "content": json.dumps(inp)}]
    sb.ask(model, msgs(cases[0]["input"]), "json")                    # warm-up
    with open(path, "w", encoding="utf-8") as f:
        for c in cases:
            raw, secs = sb.ask(model, msgs(c["input"]), "json")
            f.write(json.dumps({**c, "answer": raw, "seconds": round(secs, 3)}) + "\n")
    print("saved", path, len(cases), "cases")


def run_tests(model):
    for d in (OUT, EX_DIR, CHAT_DIR):
        os.makedirs(d, exist_ok=True)
    sb.OUT = OUT
    run_decide_v3(model)                                               # 1. decision (rules v3)
    py = sys.executable
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for cmd in ([py, "explain_bench.py", "--model", model, "--prompts", "e3", "--out", EX_DIR],   # 2. explain
                [py, "chat_bench.py", "--model", model, "--out", CHAT_DIR],                       # 3a. chat v2
                [py, "chat_v3.py", "--model", model, "--out", CHAT_DIR, "--answerability"]):      # 3b. chat v3.1
        print(">>", " ".join(cmd[1:3]), model)
        subprocess.run(cmd, cwd=BENCH, env=env, check=True, stdout=subprocess.DEVNULL)


def rows(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")] if os.path.exists(path) else []


def decision(model):
    allr = rows(os.path.join(OUT, f"{name(model)}__A_ft_v3.jsonl"))
    if not allr: return {}
    def ans(r):
        try:
            a = json.loads(r["answer"]); return a if isinstance(a, dict) else {}
        except Exception: return {}
    rs = [r for r in allr if not r["key"]["faults"]]
    fr = [r for r in allr if r["key"]["faults"]]
    n = len(rs)
    ok = lambda r, k: ans(r).get(k) == r["key"][k]
    al = lambda r: set(ans(r).get("alerts") or []) == set(r["key"]["alerts"])
    fa = lambda r: set(ans(r).get("faults") or []) == set(r["key"]["faults"])
    water = lambda r: ans(r).get("water") == "yes"
    tank = [r for r in allr if r["input"]["tank_low"]]
    night = [r for r in allr if not 6 <= r["input"]["hour"] < 22]
    switch = [r for r in allr if (r["key"]["light"] == "on") != bool(r["input"]["light_on"])]
    unplugged = [r for r in fr if r["scenario"] == "sensor_disconnected"]
    levels = ("moisture_level", "temp_level", "light_level", "humidity_level", "water", "light")
    return {"cases (normal + fault)": f"{n} + {len(fr)}",
            "water %": 100 * sum(ok(r, "water") for r in rs) / n,
            "light %": 100 * sum(ok(r, "light") for r in rs) / n,
            "alerts %": 100 * sum(al(r) for r in rs) / n,
            "all three %": 100 * sum(ok(r, "water") and ok(r, "light") and al(r) for r in rs) / n,
            "all 8 keys %": 100 * sum(all(ok(r, k) for k in levels) and al(r) and fa(r) for r in rs) / n,
            "overwater": sum(water(r) and r["key"]["water"] == "no" for r in rs),
            "missed": sum(not water(r) and r["key"]["water"] == "yes" for r in rs),
            "light switches right": f"{sum(ok(r, 'light') for r in switch)}/{len(switch)}",
            "light on at night": f"{sum(ans(r).get('light') == 'on' for r in night)}/{len(night)}",
            "tank low watered": f"{sum(water(r) for r in tank)}/{len(tank)}",
            "fault rows watered": f"{sum(water(r) for r in fr)}/{len(fr)}",
            "unplugged -> SENSOR_ERROR": f"{sum('SENSOR_ERROR' in (ans(r).get('faults') or []) for r in unplugged)}/{len(unplugged)}",
            "false faults (normal rows)": sum(bool(ans(r).get("faults")) for r in rs),
            "s/answer": sum(r["seconds"] for r in rs) / n}


def explain(model):
    rs = rows(os.path.join(EX_DIR, f"{name(model)}__e3.jsonl"))
    if not rs: return {}
    n = len(rs)
    out = {"all pass %": 100 * sum(all(r[c] for c in EX_PASS) for r in rs) / n}
    out.update({c.split("_", 1)[1] + " %": 100 * sum(r[c] for r in rs) / n for c in EX_PASS})
    return out


def chat(model, tag):
    rs = rows(os.path.join(CHAT_DIR, f"{name(model)}__{tag}.jsonl"))
    if not rs: return {}
    checks = [k for k in rs[0] if k.startswith("c") and k[1].isdigit() and isinstance(rs[0][k], bool)]
    return {"all pass %": 100 * sum(all(r[c] for c in checks) for r in rs) / len(rs)}


def report(base, ft):
    parts = [("1. DECISION (rules v3, v3 dataset, prompt ft)", decision), ("2. EXPLAIN (e3, 184 cases)", explain),
             ("3a. CHAT v2 (240)", lambda m: chat(m, "chat_v2")), ("3b. CHAT v3.1 (240)", lambda m: chat(m, "chat_v3.1"))]
    lines = [f"{'':<26}{base:>16}{ft:>18}   kept?"]
    for title, f in parts:
        a, b = f(base), f(ft)
        lines.append(title)
        for k in (a or b):
            x, y = a.get(k, "-"), b.get(k, "-")
            fx = f"{x:.1f}" if isinstance(x, float) else str(x)
            fy = f"{y:.1f}" if isinstance(y, float) else str(y)
            kept = ""
            if title[0] in "23" and isinstance(x, float) and isinstance(y, float):
                kept = "yes" if y >= x - 2 else "NO (lost skill)"
            lines.append(f"  {k:<24}{fx:>16}{fy:>18}   {kept}")
    lines += ["", "Reference (no fine-tuning, best prompts, rules v2 = pump only, 255 cases, results/summary.txt):",
              "  lfm3:1.7b p5      water 91.8 %  alerts 49.4 %  both 47.8 %  overwater 2  missed 18  fault rows watered 0/10",
              "  qwen3.5:0.8b p2   water 75.1 %  alerts 29.8 %  both 23.7 %  overwater 42 missed 19  fault rows watered 0/10",
              "Note: the base model with prompt 'ft' has no rules in its prompt, so its decision score is not a fair 'before'."]
    txt = "\n".join(lines)
    print(txt)
    open(os.path.join(OUT, f"compare_{name(base)}_vs_{name(ft)}.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="nabta-base", help="untrained model imported the same way (Modelfile.base)")
    ap.add_argument("--ft", required=True, help="name of the fine-tuned model in Ollama")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if not a.report:
        for m in (a.base, a.ft):
            run_tests(m)
    report(a.base, a.ft)
