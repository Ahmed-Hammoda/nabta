#!/usr/bin/env python3
"""
Run the controllers in config.json on live or logged contexts and log one JSON line per
controller per context (open-loop: used for RQ2 decision reliability and RQ3 latency/cost).
Standard library only.

Live on the Pi, once per cycle (C3 actuates Pot B; the line it prints is read by the pump code):
  python3 llm_decide.py --context ctx.json --controllers C3 --log ../logs/decisions.jsonl

Later, ChatGPT (C4) on everything that was logged, once the API key arrives:
  OPENAI_API_KEY=... python3 llm_decide.py --replay ../logs/contexts.jsonl --controllers C4

Hard cases, 3 repeats each (stability):
  python3 llm_decide.py --replay hard_cases.jsonl --repeats 3 --controllers C3,C4

Dry run with fake LLMs:
  python3 llm_decide.py --replay ../data/sample/decision_contexts.jsonl --n 60 --mock
"""
import argparse, json, random
from pathlib import Path
import controllers as C

HERE = Path(__file__).resolve().parent


def load_config(path):
    cfg = json.loads(Path(path).read_text())
    cfg["system_prompt"] = (Path(path).parent / cfg["prompt_file"]).read_text().strip()
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HERE / "config.json"))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--context", help="one live context JSON file")
    g.add_argument("--replay", help="JSONL of logged contexts")
    ap.add_argument("--n", type=int, default=0, help="replay: random sample of n contexts (0 = all)")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--controllers", default="", help="comma list of ids, default all (C1-C4)")
    ap.add_argument("--mock", action="store_true", help="fake LLM answers, for testing")
    ap.add_argument("--log", default=str(HERE.parent / "logs" / "decisions.jsonl"))
    a = ap.parse_args()

    cfg = load_config(a.config)
    prof = cfg["plant_profile"]
    ctrls = [c for c in cfg["controllers"] if not a.controllers or c["id"] in a.controllers.split(",")]
    if a.context:
        ctxs = [json.loads(Path(a.context).read_text())]
    else:
        ctxs = [json.loads(l) for l in Path(a.replay).read_text().splitlines() if l.strip()]
        if a.n:
            ctxs = random.Random(42).sample(ctxs, min(a.n, len(ctxs)))
    rng = random.Random(7)
    Path(a.log).parent.mkdir(parents=True, exist_ok=True)
    with open(a.log, "a") as out:
        for ctx in ctxs:
            ref = C.multirule_controller(ctx, prof)  # C2 is the reference
            case = ctx.get("case_id") or f"{ctx.get('timestamp')}|{ctx.get('pot')}"
            for c in ctrls:
                for rep in range(a.repeats):
                    rec = C.decide(c, cfg, ctx, rng, a.mock)
                    rec.update(case=case, timestamp=ctx.get("timestamp"), pot=ctx.get("pot"), repeat=rep,
                               hard_case=bool(ctx.get("hard_case")),
                               ref_action=ref["action"], ref_ml=ref["ml"], params=cfg["params"])
                    out.write(json.dumps(rec) + "\n")
                    if a.context and c.get("actuates_pot"):
                        print(json.dumps({"pot": c["actuates_pot"], "action": rec["final_action"],
                                          "ml": rec["final_ml"], "gate": rec["gate"]}))
    print(f"logged {len(ctxs)} contexts x {len(ctrls)} controllers x {a.repeats} repeats -> {a.log}")


if __name__ == "__main__":
    main()
