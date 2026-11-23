"""Step 1 (laptop, Ollama running): build the data to upload to Colab.

Fine-tuning on the decision only can make the model forget how to explain. To prevent that, we mix
in "replay" examples: the BASE model's own explanations (phase 1 prompt e3) on NEW readings, kept
only if they pass every phase 1 explanation check (c1, c2, c4, c5, c6). The model keeps its
explanation skill, and it learns nothing new from these rows.

The chat questions are NOT used, so the chat test stays a fair test of what was kept.

Output: ../train_data/colab/
  train_mix.jsonl     decision train rows (5,940) + explanation replay rows
  val_decision.jsonl  decision val rows (660), used in Colab to check accuracy
  val_explain.jsonl   explanation replay rows kept for checking (not trained on)
  nabta_colab_upload.zip   the three files above, upload this to Colab

    python make_replay_data.py            # about 10-15 min on the laptop
    python make_replay_data.py --n 50     # quick try
    python make_replay_data.py --mix-only # no Ollama: reuse the kept explanations, rebuild the mix and the zip
                                          # (use this after make_train_data.py changed the decision rows)
"""
import argparse, csv, json, os, random, socket, sys, time, urllib.error, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "code"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "simulation_phase1", "bench"))
import explain_bench as eb
import rules_v2
import make_train_data as mtd

TRAIN = os.path.join(HERE, "..", "train_data")
OUT = os.path.join(TRAIN, "colab")
TESTSET = os.path.join(HERE, "..", "..", "simulation_phase1", "bench", "testset.jsonl")   # phase 1 explain test
BASE = "qwen3.5:0.8b"
PARTIAL = os.path.join(OUT, "replay_partial.jsonl")      # kept answers, saved as they come (resume)


def ask(msgs, timeout=60):
    """Like explain_bench.ask (temperature 0, seed 1, thinking off), but gives up after 60 s."""
    body = {"model": BASE, "stream": False, "keep_alive": "30m", "think": False, "messages": msgs,
            "options": {"temperature": 0, "seed": 1, "num_predict": 150}}
    req = urllib.request.Request(eb.URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["message"]["content"].strip()
    except (socket.timeout, TimeoutError, urllib.error.URLError) as e:
        print("  skipped one reading:", e)
        return None


EX_CHECKS = ["c1_same_action", "c2_no_invented_numbers", "c4_all_alerts_mentioned", "c5_no_fake_alert", "c6_short"]


def new_readings(n, rnd):
    """New, valid readings (no faults: the system never asks the model to explain a fault)."""
    out = []
    while len(out) < n:
        ln, lh = mtd.lux_pair()
        r = mtd.row(rnd.uniform(3, 100), rnd.uniform(-2, 42), rnd.uniform(20, 95), ln, lh)
        r = {c: r[c] for c in mtd.COLS[:5]}           # the explanation task uses the 5 sensor values only
        if not rules_v2.decide(r)["faults"]:
            out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1800, help="readings to try (about 70-80 %% pass the checks)")
    ap.add_argument("--val", type=int, default=150)
    ap.add_argument("--mix-only", action="store_true", help="skip Ollama, reuse replay_partial.jsonl")
    a = ap.parse_args()
    rnd = random.Random(2030)
    mtd.rnd.seed(2030)

    test_inputs = set()
    if os.path.exists(TESTSET):
        for l in open(TESTSET, encoding="utf-8"):
            c = json.loads(l)
            i = c.get("input", {})
            test_inputs.add((i.get("soil_moisture_index"), i.get("air_temp_c")))

    os.makedirs(OUT, exist_ok=True)
    kept = [json.loads(l) for l in open(PARTIAL, encoding="utf-8")] if os.path.exists(PARTIAL) else []
    done = {x["messages"][-2]["content"] for x in kept}
    tried, t0 = 0, time.time()
    if kept:
        print(f"resuming: {len(kept)} already kept")
    part = open(PARTIAL, "a", encoding="utf-8")
    for r in ([] if a.mix_only else new_readings(a.n, rnd)):
        if (r["soil_moisture_index"], r["air_temp_c"]) in test_inputs:
            continue
        k = rules_v2.label(r["soil_moisture_index"], r["air_temp_c"], r["humidity_rh"], r["light_lux_hours_24h"])
        case = {"input": r, "key": k}
        msgs = eb.messages("e3", case)
        if msgs[-1]["content"] in done:
            continue
        text = ask(msgs)
        tried += 1
        if text is None:
            continue
        c = eb.check(text, case)
        if all(c[x] for x in EX_CHECKS):
            kept.append({"messages": msgs + [{"role": "assistant", "content": text}]})
            part.write(json.dumps(kept[-1]) + chr(10)); part.flush()
        if tried % 200 == 0:
            print(f"  {tried} tried, {len(kept)} kept, {time.time() - t0:.0f} s")
    part.close()
    print(f"explanations: {tried} tried now, {len(kept)} kept in total")

    rnd.shuffle(kept)
    val_ex, train_ex = kept[:a.val], kept[a.val:]
    decision = [json.loads(l) for l in open(os.path.join(TRAIN, "train.jsonl"), encoding="utf-8")]
    mix = decision + train_ex
    rnd.shuffle(mix)

    os.makedirs(OUT, exist_ok=True)
    def dump(name, rows):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            for x in rows: f.write(json.dumps(x) + "\n")
    dump("train_mix.jsonl", mix)
    dump("val_explain.jsonl", val_ex)
    with open(os.path.join(TRAIN, "val.jsonl"), encoding="utf-8") as f, \
         open(os.path.join(OUT, "val_decision.jsonl"), "w", encoding="utf-8") as g:
        g.write(f.read())
    z = os.path.join(OUT, "nabta_colab_upload.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for n in ("train_mix.jsonl", "val_decision.jsonl", "val_explain.jsonl"):
            zf.write(os.path.join(OUT, n), n)
    share = 100 * len(train_ex) / len(mix)
    info = (f"train_mix: {len(mix)} rows = {len(decision)} decision + {len(train_ex)} explanation replay ({share:.0f} %)\n"
            f"val_decision: {sum(1 for _ in open(os.path.join(OUT, 'val_decision.jsonl'), encoding='utf-8'))} rows; val_explain: {len(val_ex)} rows\nupload: {z}\n")
    print(info)
    open(os.path.join(OUT, "info.txt"), "w", encoding="utf-8").write(info)


if __name__ == "__main__":
    main()
