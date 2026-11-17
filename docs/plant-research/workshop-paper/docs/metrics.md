# Metrics (v2)

All produced by `experiment/metrics.py`. Target band = moisture index 60 to 90.

## RQ1 precision (`metrics.py rq1`): closed-loop replay of C1 to C4, and real Pots A/B

| Metric | Definition | Better |
|---|---|---|
| Time in band (%) | share of readings with 60 <= true index <= 90 | higher |
| Mean deviation from band | mean distance outside the band (0 inside) | lower |
| Under-watering events | times the index enters the stress zone (< 40) | lower |
| Minutes below stress | total minutes with index < 40 | lower |
| Over-watering events | waterings that push the index above 90, or start when index >= 65 | lower |
| Total water, mL/day | sum of pump volumes | lower at equal precision |
| Drained (mL) | water lost from the pot bottom (sim) or by weighing (real) | lower |
| Set-point error | index 30 min after a watering minus 88 | closer to 0 |

## RQ2 reliability (`metrics.py rq2`, add `--hard-only` for near-threshold cases)

Reference = C2. Judged on what the controller **proposed**, before the gate.

| Metric | Definition |
|---|---|
| Accuracy + 95% Wilson CI | action equals reference |
| Cohen's kappa | agreement corrected for the many "no water" cycles |
| Water recall | share of needed waterings proposed (missed = plant harm) |
| Water precision | share of proposed waterings that were needed |
| Dose MAE (mL) | when both water |
| Unsafe proposal rate | share the gate blocked or clipped (for C1: would have) |
| Valid JSON rate | parsed into the schema |
| Stability (3 repeats) | share of hard cases answered the same all 3 times |

## RQ3 cost (`metrics.py rq3`)

| Metric | Definition |
|---|---|
| Latency median / p90 (s) | per decision on its own hardware |
| Within cycle (%) | decisions answered in under 60 s |
| Cost per decision (USD) | tokens x price in `config.json` (0 for local) |
| Cost for the study (USD) | per decision x 48 cycles/day x 14 days |
| Answered (%) | decisions with an answer (no timeout or network error) |
| Works offline | yes for C1 to C3, no for C4; plus the measured share during the network cut |
