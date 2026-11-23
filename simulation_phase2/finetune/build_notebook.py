"""Writes nabta_finetune_colab.ipynb (the notebook to open in Google Colab).

Install, model loading, LoRA and saving follow Unsloth's official notebook
"Qwen3_5_(0_8B)_Vision.ipynb" (github.com/unslothai/notebooks). Our own parts: the text-only data,
answer-only masking, thinking off, the checks, and the dry run.

    python build_notebook.py
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
cells = []
md = lambda s: cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip("\n")})
code = lambda s: cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                               "source": s.strip("\n")})

md("""
# Nabta: fine-tune Qwen3.5-0.8B to make the pot decision

**Before you start:** Runtime > Change runtime type > **T4 GPU** > Save.

**Do it twice:**
1. **Dry run** (`DRY_RUN = True`, about 5 min after installing): trains 10 steps on 64 rows and runs every
   check and save. It only shows that every cell works.
2. **Real run:** set `DRY_RUN = False`, then Runtime > **Restart session**, and run all cells again
   (about 1-1.5 h).

Run the cells in order with Shift + Enter.
""")

code("""
# 0. SETTINGS
DRY_RUN = True          # True = quick test of every cell; False = the real training
EPOCHS = 2
LEARNING_RATE = 1e-4    # low, to protect the skills the model already has
""")

code("""
%%capture
# 1. Install (from Unsloth's official Qwen3.5 0.8B notebook; 3-5 min, prints nothing)
import os, importlib.util
!pip install --upgrade -qqq uv
if importlib.util.find_spec("torch") is None or "COLAB_" in "".join(os.environ.keys()):
    try: import numpy, PIL; _numpy = f"numpy=={numpy.__version__}"; _pil = f"pillow=={PIL.__version__}"
    except: _numpy = "numpy"; _pil = "pillow"
    !uv pip install -qqq \\
        "torch==2.8.0" "triton>=3.3.0" {_numpy} {_pil} torchvision "torchaudio==2.8.0" bitsandbytes xformers==0.0.32.post2 \\
        "unsloth_zoo[base] @ git+https://github.com/unslothai/unsloth-zoo" \\
        "unsloth[base] @ git+https://github.com/unslothai/unsloth"
    !uv pip install -qqq --no-deps "torchcodec==0.7.0"
elif importlib.util.find_spec("unsloth") is None:
    !uv pip install -qqq unsloth
!uv pip install --upgrade --no-deps "tokenizers>=0.22.0,<=0.23.0" trl==0.22.2 unsloth unsloth_zoo
!uv pip install transformers==5.2.0
!unsloth install-kernels
!uv pip install --no-deps --upgrade "torchao>=0.16.0"
""")

code("""
# 2. Check the GPU and versions
import torch, transformers
print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NONE")
print("transformers:", transformers.__version__)
assert torch.cuda.is_available(), "No GPU: Runtime > Change runtime type > T4 GPU"
assert int(transformers.__version__.split(".")[0]) >= 5, "Qwen3.5 needs transformers 5: run cell 1 again"
""")

code("""
# 3. Google Drive: checkpoints (every 200 steps), the LoRA and the model are saved there
from google.colab import drive
drive.mount("/content/drive")
SAVE = "/content/drive/MyDrive/nabta_finetune" + ("_dryrun" if DRY_RUN else "")
os.makedirs(SAVE, exist_ok=True)
print("results will be saved in", SAVE)
""")

code("""
# 4. Upload nabta_colab_upload.zip (simulation_phase2/train_data/colab/ on the laptop)
import os
if not os.path.exists("data/train_mix.jsonl"):
    from google.colab import files
    files.upload()
    !unzip -o nabta_colab_upload.zip -d data
!wc -l data/*.jsonl
# Expected: train_mix 7493 lines, val_decision 660, val_explain 150
""")

code("""
# 5. Load the base model in 16 bit (official notebook: FastVisionModel, load_in_4bit=False)
from unsloth import FastVisionModel
model, tokenizer = FastVisionModel.from_pretrained(
    "unsloth/Qwen3.5-0.8B",
    load_in_4bit=False,
    use_gradient_checkpointing="unsloth",
)
tok = getattr(tokenizer, "tokenizer", tokenizer)    # text tokenizer (tokenizer is the processor)
if tok.pad_token is None:
    tok.pad_token = "<|endoftext|>"
MAX_LEN = 2048
""")

code("""
# 6. LoRA add-on on the LANGUAGE layers only (the vision part stays frozen)
model = FastVisionModel.get_peft_model(
    model,
    finetune_vision_layers=False,
    finetune_language_layers=True,
    finetune_attention_modules=True,
    finetune_mlp_modules=True,
    r=16, lora_alpha=16, lora_dropout=0, bias="none",
    random_state=3407, use_rslora=False, loftq_config=None,
)
model.print_trainable_parameters()
""")

code("""
# 7. Chat format with thinking OFF (Ollama is called with think=false on the laptop and the Pi)
END = "<|im_end|>"

def _as_parts(msgs):
    return [{"role": m["role"], "content": [{"type": "text", "text": m["content"]}]} for m in msgs]

def render(msgs):
    \"\"\"The prompt text up to the start of the assistant's answer.\"\"\"
    last = None
    for t, m in ((tok, msgs), (tokenizer, msgs), (tokenizer, _as_parts(msgs))):
        try:
            return t.apply_chat_template(m, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except Exception as e:
            last = e
    raise last

demo = render([{"role": "system", "content": "SYSTEM"}, {"role": "user", "content": "USER"}])
print(demo + "<answer>")
assert "<|im_start|>assistant" in demo, "unexpected chat format: stop and send this output to Claude"
print("\\nthink block in the prompt:", "<think>" in demo)
""")

code("""
# 8. Prepare the data: the model learns ONLY the last answer of each example (the prompt is masked)
import json, random
from datasets import Dataset

def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]

train = load("data/train_mix.jsonl")
val_dec = load("data/val_decision.jsonl")
val_ex = load("data/val_explain.jsonl")
if DRY_RUN:
    train = train[:64]

def encode(ex):
    msgs = ex["messages"]
    p_ids = tok(render(msgs[:-1]), add_special_tokens=False)["input_ids"]
    a_ids = tok(msgs[-1]["content"] + END + "\\n", add_special_tokens=False)["input_ids"]
    ids = (p_ids + a_ids)[:MAX_LEN]
    labels = ([-100] * len(p_ids) + a_ids)[:MAX_LEN]
    return {"input_ids": ids, "attention_mask": [1] * len(ids), "labels": labels}

train_ds = Dataset.from_list([encode(x) for x in train]).shuffle(seed=3407)
eval_rows = random.Random(1).sample(val_dec, 200) + val_ex[:50]
eval_ds = Dataset.from_list([encode(x) for x in (eval_rows[:20] if DRY_RUN else eval_rows)])
lens = sorted(len(x) for x in train_ds["input_ids"])
print(len(train_ds), "train rows; tokens per row: median", lens[len(lens) // 2], "max", lens[-1])
""")

code("""
# 9. Train. Watch "eval_loss": it should go down and stay low.
from transformers import Trainer, TrainingArguments, DataCollatorForSeq2Seq
from unsloth import is_bfloat16_supported          # Unsloth's own check (a T4 has no bfloat16)
FastVisionModel.for_training(model)
bf16 = is_bfloat16_supported()
print("bfloat16:", bf16)
args = TrainingArguments(
    output_dir=SAVE + "/checkpoints",   # on Drive: if Colab disconnects, resume with trainer.train(resume_from_checkpoint=True)
    num_train_epochs=EPOCHS,
    max_steps=10 if DRY_RUN else -1,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,      # 16 examples per step
    learning_rate=LEARNING_RATE,
    warmup_ratio=0.03,
    lr_scheduler_type="linear",
    weight_decay=0.01,
    optim="adamw_8bit",
    logging_steps=5 if DRY_RUN else 20,
    eval_strategy="steps",
    eval_steps=5 if DRY_RUN else 100,
    save_strategy="steps",
    save_steps=200,
    save_total_limit=1,
    bf16=bf16, fp16=not bf16,
    remove_unused_columns=False,
    seed=3407,
    report_to="none",
)
trainer = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=eval_ds,
                  data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100))
import time
t0 = time.time()
stats = trainer.train()
print(stats)
print(f"seconds per step: {(time.time() - t0) / stats.global_step:.1f}")
# DRY RUN: the loss must be a real number (not nan). Real run time is about 940 steps x seconds per step.
model.save_pretrained(SAVE + "/nabta_lora"); tok.save_pretrained(SAVE + "/nabta_lora")   # backup right away
print("LoRA saved to", SAVE + "/nabta_lora")
""")

code("""
# 10. Check the DECISION on rows the model never saw (300 rows; 20 in the dry run)
FastVisionModel.for_inference(model)

def generate(msgs, max_new=120):
    enc = tok(render(msgs), return_tensors="pt", add_special_tokens=False).to("cuda")
    out = model.generate(**enc, max_new_tokens=max_new, do_sample=False)
    return tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()

keys = ["moisture_level", "temp_level", "light_level", "humidity_level", "faults", "alerts", "water"]
n = water = alerts = both = exact = bad_json = over = missed = 0
mistakes = []
for ex in random.Random(2).sample(val_dec, 20 if DRY_RUN else 300):
    want = json.loads(ex["messages"][-1]["content"])
    text = generate(ex["messages"][:-1])
    try:
        got = json.loads(text)
    except Exception:
        got, bad_json = {}, bad_json + 1
    n += 1
    w = got.get("water") == want["water"]
    a = set(got.get("alerts") or []) == set(want["alerts"])
    water += w; alerts += a; both += w and a
    exact += all(got.get(k) == want[k] for k in keys)
    over += want["water"] == "no" and got.get("water") == "yes"
    missed += want["water"] == "yes" and got.get("water") != "yes"
    if not (w and a) and len(mistakes) < 8:
        mistakes.append((ex["messages"][-2]["content"], text))
summary = (f"water {100*water/n:.1f} %  alerts {100*alerts/n:.1f} %  both {100*both/n:.1f} %  "
           f"all 7 keys {100*exact/n:.1f} %  overwater {over}  missed {missed}  bad JSON {bad_json}  (of {n})")
print(summary)
for q, t in mistakes:
    print("\\nIN :", q, "\\nOUT:", t)
open(SAVE + "/colab_decision_check.txt", "w").write(summary + "\\n")
# (In the dry run these numbers mean nothing: the model has trained for only 10 steps.)
""")

code("""
# 11. Check the EXPLANATIONS still look right (the base model's answer vs the trained model's answer)
lines = []
for ex in val_ex[:8]:
    lines += ["FACTS : " + ex["messages"][-2]["content"].replace("\\n", " | "),
              "BEFORE: " + ex["messages"][-1]["content"],
              "AFTER : " + generate(ex["messages"][:-1], 80), ""]
print("\\n".join(lines))
open(SAVE + "/colab_explain_check.txt", "w").write("\\n".join(lines))
# The full explanation and chat tests run on the laptop (README step 4).
""")

code("""
# 12. Save the full model to Google Drive (16-bit merged, and GGUF q8_0 like the Ollama base model)
try:
    model.save_pretrained_merged("nabta_merged", tokenizer)
    !cp -r nabta_merged "$SAVE/"
    print("merged model saved")
except Exception as e:
    print("merged save failed:", e)
try:
    model.save_pretrained_gguf("nabta_gguf", tokenizer)          # default = q8_0 (same as the Ollama base)
    print("GGUF saved by Unsloth")
except Exception as e:
    print("Unsloth GGUF export failed, converting with llama.cpp instead:", e)
    !git clone --depth 1 https://github.com/ggml-org/llama.cpp
    !pip install -q -r llama.cpp/requirements/requirements-convert_hf_to_gguf.txt
    !mkdir -p nabta_gguf
    !python llama.cpp/convert_hf_to_gguf.py nabta_merged --outtype q8_0 --outfile nabta_gguf/nabta-q8_0.gguf
!cp -r nabta_gguf* "$SAVE/"
!ls -la "$SAVE" "$SAVE"/nabta_gguf*
# The GGUF file is the one you need on the laptop and the Pi (Ollama cannot import safetensors on Windows).
""")

nb = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"provenance": []},
                                    "kernelspec": {"display_name": "Python 3", "name": "python3"},
                                    "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 0}
for c in nb["cells"]:
    c["source"] = [l + "\n" for l in c["source"].split("\n")]
    c["source"][-1] = c["source"][-1].rstrip("\n")
path = os.path.join(HERE, "nabta_finetune_colab.ipynb")
json.dump(nb, open(path, "w", encoding="utf-8"), indent=1)
print("wrote", path)
