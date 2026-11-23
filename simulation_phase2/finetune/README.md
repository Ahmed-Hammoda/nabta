# Fine-tuning qwen3.5:0.8b for Nabta: step by step

Goal: the model makes the pot decision itself (levels, faults, alerts, water) and **keeps** its skill
of explaining the decision and chatting.

> **Status:** the notebook has **not been run yet**. Its install, loading and saving code follows
> Unsloth's official Qwen3.5 0.8B notebook. Do the **dry run** first: it shows in about 5 minutes
> whether every cell works.

| Step | Where | What | Status |
|---|---|---|---|
| 1 | Laptop | Upload file `train_data/colab/nabta_colab_upload.zip` | **Done** |
| 2 | Colab | `nabta_finetune_colab.ipynb`: dry run, test import, then the real run | To do (time measured in the dry run) |
| 3 | Laptop | Download the GGUF and import it into Ollama | To do (10 min) |
| 4 | Laptop | `python eval_finetuned.py --ft nabta-qwen3.5` | Base half done; fine-tuned half to do (about 15 min) |

## Step 1 (done): the upload file
`nabta_colab_upload.zip` contains:

| File | Rows | What |
|---|---|---|
| `train_mix.jsonl` | 7,493 | 5,940 decision rows + 1,553 explanation **replay** rows (21 %) |
| `val_decision.jsonl` | 660 | Decision rows not trained on |
| `val_explain.jsonl` | 150 | Explanation rows not trained on |

**Replay** rows are the base model's own explanations (prompt e3) on new readings:
- Each one was kept only if it passed every phase 1 explanation check (1,703 of 1,800 passed).
- Training on them stops the model from forgetting how to explain.

The chat questions are not used, so the chat test in step 4 stays fair.

To rebuild the file (about 13 min, Ollama running), delete `train_data/colab/replay_partial.jsonl`
and run `python make_replay_data.py`.

## Step 2: train in Google Colab
1. Go to https://colab.research.google.com, choose File > Upload notebook, and pick `nabta_finetune_colab.ipynb`.
2. Choose Runtime > Change runtime type > **T4 GPU**.
3. **Dry run:** keep `DRY_RUN = True` in cell 0 and run every cell. It trains 10 steps on 64 rows.
   - If any cell gives an error, stop and send the error.
   - The loss must be a real number, not `nan`.
   - Note the **seconds per step** that cell 9 prints. The real run is about 940 steps, so its time
     is about 940 x seconds per step.
4. **Test the import of the dry-run model:** download `MyDrive/nabta_finetune_dryrun/nabta_gguf` and
   do step 3 with it (name it `nabta-dryrun`). One `ollama run` answer is enough; it doesn't need to
   be correct yet. This is the one link that hasn't been tested yet: a trained Qwen3.5 GGUF from
   Unsloth loaded in Ollama.
5. **Real run:** set `DRY_RUN = False`, choose Runtime > Restart session, and run every cell again.
   If Colab disconnects, the checkpoints are in `MyDrive/nabta_finetune/checkpoints`.

| Cell | What it does | What to check |
|---|---|---|
| 0 | Settings | `DRY_RUN`, 2 epochs, learning rate 1e-4 |
| 1 | Installs Unsloth and transformers 5.2 (official install cell) | Prints nothing (3-5 min) |
| 2 | Checks the GPU | It must show "Tesla T4" and transformers 5.x |
| 3 | Connects Google Drive | Allow access; results are saved there |
| 4 | Upload | Choose `nabta_colab_upload.zip`; it should show 7493 / 660 / 150 lines |
| 5-6 | Loads `unsloth/Qwen3.5-0.8B` and adds LoRA to the language layers | About 1-2 % of the weights are trainable |
| 7 | Shows the chat format | It must end with `<\|im_start\|>assistant` and an empty `<think></think>` |
| 8 | Prepares the data | The model learns only the answers, not the prompts |
| 9 | **Trains**, then saves the LoRA to Drive | `eval_loss` should fall and stay low |
| 10 | Decision check on 300 unseen rows | Target: water 99 % or more, alerts 98 % or more |
| 11 | Explanation check | "AFTER" should read like "BEFORE" |
| 12 | Saves the merged model and the **GGUF** to Drive | You need the `nabta_gguf` folder |

The chat format was checked on the laptop with the real Qwen3.5 template:
- With thinking off, the prompt ends in `<|im_start|>assistant\n<think>\n\n</think>\n\n`, which is
  the same text the notebook trains on.
- Ollama's chat call (think=false) gave the same answers as this template sent raw, on 10 of 10
  cases. So Colab and Ollama see the same text.

## Step 3: import into Ollama (laptop)
1. Download the `nabta_gguf` folder from Google Drive (`MyDrive/nabta_finetune/`) into this folder.
2. In `Modelfile.gguf`, change the `FROM` line to the `.gguf` file name inside `nabta_gguf`.
3. Run:
   ```
   ollama create nabta-qwen3.5 -f Modelfile.gguf
   ollama run nabta-qwen3.5 "{\"soil_moisture_index\": 18.0, \"air_temp_c\": 22.0, \"humidity_rh\": 60.0, \"light_lux_now\": 0.0, \"light_lux_hours_24h\": 150000.0}"
   ```

What was tested on 16 Nov 2026 (Ollama 0.40.16):
- Importing a Qwen3.5-0.8B **GGUF** works.
- Importing **safetensors** does not work on Windows, because Ollama needs the MLX runtime for it.
- The untrained GGUF, imported this way as `nabta-base`, gave the same explanations as the official
  `qwen3.5:0.8b` on 20 of 20 cases, and the same decisions on 8 of 10.

**Control model:** `nabta-base` is the untrained model imported the same way. It already exists in
Ollama on this laptop. To make it again, download `Qwen3.5-0.8B-Q8_0.gguf` from
https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF and run `ollama create nabta-base -f Modelfile.base`.

## Step 4: compare before and after (laptop)
```
python eval_finetuned.py --ft nabta-qwen3.5          # base = nabta-base
```
Both models get the same tests and settings: temperature 0, seed 1, thinking off.

| Test | Cases | What it shows |
|---|---|---|
| Decision (prompt `ft`) | 255 (30-day dataset) | Water, alerts, levels, overwatering, missed watering, broken sensor (watered? SENSOR_ERROR?), false faults |
| Explanation e3 | 184 (phase 1) | Same action, no invented numbers, all alerts, no fake alert, short |
| Chat v2 | 240 | Phase 1 free chat |
| Chat v3.1 | 240 | Phase 1 router + safety net (96 % before) |

Results go to `../results/finetune_eval/compare_*.txt`.

**Before scores (already measured, `nabta-base`, 16 Nov 2026):**

| Test | Score |
|---|---|
| Explanation e3, all pass | 97.8 % (the official qwen3.5:0.8b scores the same 97.8 % with this rule) |
| Chat v2 | 85.8 % |
| Chat v3.1 | 96.2 % |
| Decision, prompt `ft` | 0 % water (the untrained model invents its own JSON format, which is expected) |

**"Skill kept"** means the fine-tuned model scores at most 2 points below `nabta-base` on the
explanation and chat tests. If a skill is lost:
- make more replay (`--n 3000`), or
- train for 1 epoch, or
- lower the learning rate to 5e-5.

**Comparing the scores:**
- If cell 10 in Colab scores high but step 4 scores much lower, the cause is a chat-format
  mismatch between Colab and Ollama, not a bad model.
- The base model with prompt `ft` has no rules in its prompt, so it is not a fair "before" for the
  decision. Compare with the earlier best results printed under the table: lfm3:1.7b p5, 47.8 %
  both correct.

## Limits
- The training **bakes in the rules v2 limits**, including 285,000 lux-hours (flagged in
  `../LIMITS_CHECK_and_REFERENCES.txt`) and "soil 2 or below = broken sensor" (not measured yet).
  If either changes, rebuild the data and train again.
- The training data is simulated. The real 17-row log is still to be tested.
- Stuck-pump faults cannot be learned from one row (the model needs the previous reading).
