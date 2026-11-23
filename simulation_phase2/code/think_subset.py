"""30-minute thinking test: qwen3:1.7b, prompt p5, thinking on, on a fixed subset of the 255 cases.
The same rows are scored from the thinking-off run, so the two can be compared directly.

    python think_subset.py            # run (about 30 min on the laptop) and compare
    python think_subset.py --report   # compare only
    python think_subset.py --model lfm3:1.7b
"""
import json, os, sys, time
import sim_bench_v2 as sb

CFG, PER_SCEN, FAULTS = "p5", 6, 5
MODEL = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "qwen3:1.7b"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "think_subset")


def subset():
    cases = sb.load_cases()
    fault = [c for c in cases if c["faults"]]
    by = {}
    for c in cases:
        if not c["faults"]:
            by.setdefault(c["scenario"], []).append(c)
    pick = fault[::2][:FAULTS]
    for scen in sorted(by):
        rows = by[scen]
        step = max(1, len(rows) // PER_SCEN)
        pick += rows[::step][:PER_SCEN]
    return pick


def stats(rows):
    nr = [r for r in rows if not r["fault"]]
    need = [r for r in nr if r["key"]["water"] == "yes"]
    pct = lambda a, b: f"{100 * a / b:5.1f} %" if b else "  -  "
    return {
        "water correct": pct(sum(r["water_ok"] for r in nr), len(nr)),
        "waters when needed": f"{pct(sum(not r['missed_water'] for r in need), len(need))} ({sum(not r['missed_water'] for r in need)}/{len(need)})",
        "no overwater": pct(sum(not r["overwater"] for r in nr if r["key"]["water"] == "no"),
                            sum(r["key"]["water"] == "no" for r in nr)),
        "alerts correct": pct(sum(r["alerts_ok"] for r in nr), len(nr)),
        "both correct": pct(sum(r["water_ok"] and r["alerts_ok"] for r in nr), len(nr)),
        "fault rows watered": f"{sum(r['answer'] and json.loads(r['answer']).get('water') == 'yes' for r in rows if r['fault'])}/{sum(r['fault'] for r in rows)}",
        "empty answers": str(sum(not r["answer"] for r in rows)),
        "s per answer": f"{sum(r['seconds'] for r in rows) / len(rows):.1f}",
    }


def compare():
    ids = {c["id"] for c in subset()}
    on_path = os.path.join(OUT, f"{MODEL.replace(':', '_')}_think__A_{CFG}.jsonl")
    on = [json.loads(l) for l in open(on_path, encoding="utf-8")]
    off_path = os.path.join(OUT, "..", f"{MODEL.replace(':', '_')}__A_{CFG}.jsonl")
    off = [r for r in map(json.loads, open(off_path, encoding="utf-8")) if r["id"] in ids]
    a, b = stats(off), stats(on)
    lines = [f"{MODEL} prompt {CFG}, same {len(on)} cases ({sum(not r['fault'] for r in on)} normal + {sum(r['fault'] for r in on)} fault)",
             f"{'':<22}{'thinking off':>16}{'thinking on':>16}"]
    lines += [f"{k:<22}{a[k]:>16}{b[k]:>16}" for k in a]
    txt = "\n".join(lines)
    print(txt)
    open(os.path.join(OUT, f"compare_{MODEL.replace(':', '_')}.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    if "--report" not in sys.argv:
        os.makedirs(OUT, exist_ok=True)
        sb.OUT, sb.THINK = OUT, True
        cases = subset()
        print(len(cases), "cases"); t0 = time.time()
        sb.run_decide(MODEL, CFG, cases)
        print(f"done in {(time.time() - t0) / 60:.0f} min")
    compare()
