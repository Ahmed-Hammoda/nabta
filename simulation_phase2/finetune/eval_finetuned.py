"""Step 4 (laptop, Ollama running): compare the base model and the fine-tuned model.

Same tests, same settings (temperature 0, seed 1, thinking off) for both models:
  1. DECISION    Test A on the 255 cases of the 30-day dataset, short fine-tune prompt ("ft")
                 (+ the base model's best earlier result, lfm3/qwen3.5 p5, for reference)
  2. EXPLAIN     phase 1 explanation test, prompt e3, 184 cases (simulation_phase1/bench/explain_bench.py)
  3. CHAT        phase 1 chat test v2 (240 answers) and chat v3.1 (router + safety net, 240 answers)

"Skill kept" = the fine-tuned score is at most 2 points below the base score.

    python eval_finetuned.py --ft nabta-qwen3.5          # about 20-30 min for both models
    python eval_finetuned.py --ft nabta-qwen3.5 --report # only print the comparison again
"""
import argparse, glob, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(HERE, "..", "code")
BENCH = os.path.join(HERE, "..", "..", "simulation_phase1", "bench")
OUT = os.path.join(HERE, "..", "results", "finetune_eval")
EX_DIR, CHAT_DIR = os.path.join(OUT, "explain"), os.path.join(OUT, "chat")   # one folder per test
sys.path.insert(0, CODE)
import sim_bench_v2 as sb

EX_PASS = ["c1_same_action", "c2_no_invented_numbers", "c4_all_alerts_mentioned", "c5_no_fake_alert", "c6_short"]


def name(m):
    return m.replace(":", "_")


def run_tests(model):
    for d in (OUT, EX_DIR, CHAT_DIR):
        os.makedirs(d, exist_ok=True)
    sb.OUT = OUT
    sb.run_decide(model, "ft", sb.load_cases())                       # 1. decision
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
    rs = [r for r in rows(os.path.join(OUT, f"{name(model)}__A_ft.jsonl")) if not r["fault"]]
    fr = [r for r in rows(os.path.join(OUT, f"{name(model)}__A_ft.jsonl")) if r["fault"]]
    if not rs: return {}
    n = len(rs)
    def ans(r):
        try:
            a = json.loads(r["answer"]); return a if isinstance(a, dict) else {}
        except Exception: return {}
    watered = lambda r: ans(r).get("water") == "yes"
    unplugged = [r for r in fr if r["scenario"] == "sensor_disconnected"]   # soil 0: visible in one row
    return {"water %": 100 * sum(r["water_ok"] for r in rs) / n,
            "alerts %": 100 * sum(r["alerts_ok"] for r in rs) / n,
            "both %": 100 * sum(r["water_ok"] and r["alerts_ok"] for r in rs) / n,
            "levels %": 100 * sum(r["all_ok"] for r in rs) / n,
            "overwater": sum(r["overwater"] for r in rs), "missed": sum(r["missed_water"] for r in rs),
            "fault rows watered": f"{sum(watered(r) for r in fr)}/{len(fr)}",
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
    parts = [("1. DECISION (255 cases, prompt ft)", decision), ("2. EXPLAIN (e3, 184 cases)", explain),
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
    lines += ["", "Reference (no fine-tuning, best prompts, same 255 cases, from results/summary.txt):",
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
