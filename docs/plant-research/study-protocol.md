# Study protocol: Pot A vs. Pot B

**Owner:** Yassine Mtibaa · draft for the team meeting on 2 Nov 2026

Two matching spearmint pots grow side by side from 9 Nov to 4 Dec 2026. **Pot A** is watered by Nabta when its soil needs it. **Pot B** is watered on a fixed schedule, like a typical home gardener. Everything else is kept the same, so any difference in water use or plant health comes from the watering method.

Status: draft, to approve on 2 Nov. Items marked **To agree** need a team decision.

---

## 1. Research questions and hypotheses

| | Question | Hypothesis |
|---|---|---|
| **RQ1** | How much water does sensor-based watering save compared with a fixed schedule, for the same plant health? | **H1a:** Pot A uses less water than Pot B over the study. **H1b:** Pot A's plant is not less healthy than Pot B's (same or better growth, no more stress events). |
| **RQ2** | How do explanations from a local language model compare with a cloud model? | **H2:** The cloud model's explanations score higher on correctness and clarity, and the local model answers without internet at an acceptable speed. The evaluation method is written by Ahmed Hamouda in `ai/evaluation/`. |

H1b matters as much as H1a: saving water by letting the plant suffer is not a result. Earlier field studies found that sensor-based irrigation saved water compared with timers with no loss in turf quality ([related work](related-work.md)), and this study tests whether the same holds for a potted herb indoors.

---

## 2. Design

| Item | Pot A (Nabta) | Pot B (fixed schedule) |
|---|---|---|
| Plant | Spearmint, matched in size at the start | Same |
| Pot and mix | 2 to 3 L pot with drainage, potting mix with about 25% perlite | Same |
| Light | LED grow light, 14 h per day, same timer | Same |
| Place | Side by side, same window and room | Same; the pots swap places every Sunday to cancel light and draught differences |
| Moisture sensor | Yes, drives watering | Yes, **logs only** (never drives watering) |
| Watering | Nabta rules: water below index 60, refill to 85 to 90 in pulses ([thresholds](thresholds-and-calibration.md)) | Fixed volume at fixed times (section 3) |

### Who decides Pot A's watering

For RQ1 to be a clean measurement, Pot A's watering must follow **fixed, frozen rules** for the whole study. If the language model chose the amount, the result would depend on the model's behaviour that day and could not be repeated.

**Proposal (to agree):** during the study the rules engine decides every watering, and the language model writes the explanation for each decision. Those explanations are then the material for RQ2. This matches the safety design, where the hard rules always have the final word.

---

## 3. Pot B's fixed schedule (to agree before 9 Nov)

A fair baseline is a schedule a careful gardener would follow, one that keeps the plant healthy. A schedule chosen to waste water would make Nabta look better than it is.

**Proposal:** set Pot B's schedule from the calibration week (2 to 8 Nov).

1. Measure how many mL a pot loses per day by weighing it (1 mL of water = 1 g).
2. Water Pot B **every 2 days at 9:00**, with a volume equal to 2 days of measured loss plus 20% (a common "water a little extra" habit).
3. Freeze the volume and the time on 8 Nov.
4. Water Pot B with its own pump on a timer if the hardware allows it, or by hand with a measuring jug. Either way, log every watering with its mL.

---

## 4. What we measure

| Measure | How | When | Unit |
|---|---|---|---|
| Water given | Pump run time × measured pump flow, checked against pot weight | Every watering | mL |
| Soil moisture | Capacitive sensor, raw value and per-pot index | Every 30 s, stored as 5 min averages | Index 0 to 100 |
| Pot weight | Kitchen scale, same time of day | Daily, 9:00 | g |
| Air temperature and humidity | Sensor next to the pots | Every 30 s | °C, % RH |
| Light | Light sensor at canopy height | Every 30 s | lux |
| Plant height | Ruler, soil surface to tallest growing tip | Weekly, Sunday | cm |
| Leaf count | Count of fully opened leaves | Weekly, Sunday | count |
| Wilting score | Scale below, before watering | Daily, 9:00 and 17:00 | 0 to 4 |
| Photo | Phone on a fixed mark, same distance, grow light on | Weekly, Sunday | image |
| Shoot fresh weight | Cut all shoots at soil level, weigh at once | Once, 4 Dec | g |

### Wilting score (our own scale)

| Score | What it looks like |
|---|---|
| 0 | Leaves firm, no droop |
| 1 | Top leaves slightly soft or drooping |
| 2 | Most leaves drooping, stems still upright |
| 3 | Stem tips bent over |
| 4 | Whole plant collapsed |

A score of 2 or more counts as a **stress event**, together with any period where the moisture index stays below 40 for 2 h.

---

## 5. Analysis plan

| Result | Calculation | Answers |
|---|---|---|
| Total water per pot | Sum of all waterings, 9 Nov to 4 Dec | H1a |
| Water saved | (Pot B − Pot A) ÷ Pot B × 100 | H1a |
| Water productivity | Shoot fresh weight (g) ÷ total water (L), per pot | H1a and H1b together |
| Growth | Height and leaf count over the 4 weeks, per pot | H1b |
| Stress | Number of stress events and hours below index 40, per pot | H1b |
| Waterlogging | Hours above index 95, per pot | H1b |
| Daily pattern | Daily water use of each pot plotted against temperature and light | Discussion |

### Limits we state in the report

- **One plant per method.** With n = 1 per pot, differences between plants can look like differences between methods. We report the results as a **case study**, use matched plants and swap positions weekly, and say clearly that the result is not a statistical test. If the team has a spare matching pot and plant, a second Pot A/Pot B pair would make the result stronger.
- **Four weeks in late autumn.** Water use in Tunis in Nov–Dec is lower than in summer, so the savings may differ in other seasons.
- **Sensor drift.** Capacitive sensors drift with temperature and salt build-up. Daily pot weights give an independent check.

---

## 6. Timeline

| Dates | Step |
|---|---|
| 2 Nov | Team approves this protocol, Pot B's schedule and who decides watering |
| 2 to 8 Nov | Calibration week: sensor index 0 and 100, drying test, pump flow, daily water loss |
| 8 Nov | Thresholds and Pot B's schedule frozen in [`plant-profile.json`](plant-profile.json) |
| 9 Nov | Study starts, first plant check |
| 20 Nov | Mid-study demo, check data is complete |
| 4 Dec | Last plant check, shoot harvest and weighing, final demo |

---

## 7. Data the dashboard and backend must log

For Ahmed Ridha (export format) and Ahmed Hamouda (database):

- **Readings:** timestamp, pot_id, raw moisture, moisture index, air temperature, humidity, light.
- **Waterings:** timestamp, pot_id, mL, pump seconds, trigger (rule, schedule, manual), rule that fired, explanation text, model used (local or cloud), model response time.
- **Plant checks:** date, pot_id, height, leaf count, wilting score, photo file, note.
- **Daily weights:** date, pot_id, weight in g.

Every row carries `pot_id` (`A` or `B`), so both pots fit in the same tables.
