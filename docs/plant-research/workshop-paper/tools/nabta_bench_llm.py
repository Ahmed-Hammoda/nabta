#!/usr/bin/env python3
"""
Nabta option 1 vs option 2 benchmark (standard library only).

Sends the decision contexts made by nabta_simulate.py to any OpenAI-compatible
chat endpoint (Ollama on the Raspberry Pi, Ollama on a laptop, or a cloud API) and
asks the model to EXPLAIN the rules engine's decision. It measures what the option
choice depends on:

  - latency per explanation (seconds) and generation speed (tokens/s)
  - whether the answer is valid JSON in the expected shape
  - simple faithfulness checks: the explanation agrees with the decision
    (says water / no water), quotes the moisture value, and does not invent
    a different amount of water

Run the SAME command once on the Pi (option 1) and once against the laptop
(option 2), then compare the two summary lines.

Examples:
  # Option 1: model on the Pi (run on the Pi)
  python3 nabta_bench_llm.py --base-url http://localhost:11434/v1 --model qwen2.5:1.5b --n 30

  # Option 2: model on a laptop on the same Wi-Fi (run on the Pi, laptop runs `OLLAMA_HOST=0.0.0.0 ollama serve`)
  python3 nabta_bench_llm.py --base-url http://192.168.1.20:11434/v1 --model llama3.1:8b --n 30

  # Phase 2 cloud comparison
  OPENAI_API_KEY=... python3 nabta_bench_llm.py --base-url https://api.openai.com/v1 --model gpt-4o-mini --n 30
"""
import argparse
import csv
import json
import os
import random
import re
import time
import urllib.request

SYSTEM = (
    "You are Nabta, the assistant of a smart pot growing spearmint. A rules engine has already "
    "decided whether to water. You never change that decision; you only explain it to the owner. "
    "Reply with JSON only: {\"decision\": \"water\" or \"no_water\", \"explanation\": \"one or two "
    "short sentences in plain English that mention the soil moisture value\"}."
)


def call(base_url, model, api_key, ctx, timeout):
    user = "Decision context:\n" + json.dumps(ctx, indent=1)
    body = {"model": model, "temperature": 0.2, "max_tokens": 120,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]}
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + (api_key or "ollama")})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    dt = time.time() - t0
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    return text, dt, usage.get("prompt_tokens"), usage.get("completion_tokens")


def check(ctx, text):
    m = re.search(r"\{.*\}", text, re.S)
    try:
        out = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        out = None
    valid = isinstance(out, dict) and out.get("decision") in ("water", "no_water") and isinstance(out.get("explanation"), str)
    expl = out.get("explanation", "") if valid else text
    truth = ctx["rules_decision"]["action"]
    agrees = valid and out["decision"] == truth
    idx = ctx["latest"]["soil_index_median_15min"]
    quotes_value = idx is not None and any(s in expl for s in {str(round(idx)), str(idx), f"{idx:.1f}"})
    ml_claims = [int(x) for x in re.findall(r"(\d+)\s*m[lL]", expl)]
    invents_ml = any(abs(x - ctx["rules_decision"]["ml"]) > 5 and x not in (150, 500) for x in ml_claims)
    return valid, agrees, quotes_value, invents_ml, expl


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--contexts", default="sim_out/decision_contexts.jsonl")
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--n", type=int, default=30, help="number of contexts (balanced: waterings first)")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--label", default="", help="e.g. option1-pi5 or option2-laptop")
    ap.add_argument("--out", default="bench_results.csv")
    args = ap.parse_args()

    ctxs = [json.loads(l) for l in open(args.contexts)]
    water = [c for c in ctxs if c["rules_decision"]["action"] == "water"]
    other = [c for c in ctxs if c["rules_decision"]["action"] != "water"]
    random.Random(0).shuffle(other)
    sample = (water[: args.n // 2] + other)[: args.n]

    new = not os.path.exists(args.out)
    f = open(args.out, "a", newline="")
    w = csv.writer(f)
    if new:
        w.writerow(["label", "model", "timestamp", "truth", "reason_code", "latency_s", "prompt_tokens",
                    "completion_tokens", "tokens_per_s", "valid_json", "agrees", "quotes_value", "invents_ml",
                    "explanation"])
    lat, ok, agree, quote, invent = [], 0, 0, 0, 0
    for i, ctx in enumerate(sample, 1):
        try:
            text, dt, pt, ct = call(args.base_url, args.model, os.environ.get("OPENAI_API_KEY"), ctx, args.timeout)
        except Exception as e:  # noqa: BLE001  keep going, record the failure
            print(f"[{i}/{len(sample)}] error: {e}")
            w.writerow([args.label, args.model, ctx["timestamp"], ctx["rules_decision"]["action"],
                        ctx["rules_decision"]["reason_code"], "", "", "", "", 0, 0, 0, 0, f"ERROR {e}"])
            continue
        v, a, q, inv, expl = check(ctx, text)
        tps = round(ct / dt, 2) if ct else ""
        lat.append(dt); ok += v; agree += a; quote += q; invent += inv
        w.writerow([args.label, args.model, ctx["timestamp"], ctx["rules_decision"]["action"],
                    ctx["rules_decision"]["reason_code"], round(dt, 2), pt, ct, tps, int(v), int(a), int(q),
                    int(inv), expl.replace("\n", " ")])
        f.flush()
        print(f"[{i}/{len(sample)}] {dt:5.1f}s valid={int(v)} agrees={int(a)} :: {expl[:90]}")
    f.close()
    if lat:
        lat.sort()
        n = len(lat)
        print(f"\nSUMMARY {args.label or args.model}: n={n}  median latency {lat[n // 2]:.1f}s  "
              f"p90 {lat[min(n - 1, int(0.9 * n))]:.1f}s  valid JSON {100 * ok / n:.0f}%  "
              f"agrees with rules {100 * agree / n:.0f}%  quotes moisture {100 * quote / n:.0f}%  "
              f"invents mL {100 * invent / n:.0f}%")


if __name__ == "__main__":
    main()
