# Plant research

**Owner:** Yassine Mtibaa

Which plant Nabta grows during the study, what it needs, and the starting values the firmware, the safety rules and the AI assistant should use.

## Decision

Nabta grows **spearmint** (*Mentha spicata*, family **Lamiaceae**, Tunisian *na3na3*) in both pots. Basil is dropped for the November to December run.

- Spearmint uses a lot of water, wilts visibly within a day or two of drying out, recovers fast, and tolerates cool, unheated rooms. Those traits let a water saving show up in the four-week study.
- Basil is from the same family, but it gets chilling injury below 12 °C. Tunis averages an 8 °C low in December.
- Succulents and pothos use too little water to show any saving, and cherry tomatoes need about 9 weeks and strong grow lights to fruit.

Status: proposed on 25 Oct 2026, to be confirmed by the team at the Week 2 meeting.

## Files

| File | Content |
|---|---|
| [`plant-family-choice.md`](plant-family-choice.md) | Selection criteria, scored comparison of 5 candidates, decision and backup plan |
| [`spearmint-requirements.md`](spearmint-requirements.md) | Temperature, light, humidity, soil and pot needs; signs of over- and under-watering |
| [`thresholds-and-calibration.md`](thresholds-and-calibration.md) | Starting thresholds for the rules engine, firmware and alerts; calibration week plan (2 to 8 Nov) |
| [`plant-profile.json`](plant-profile.json) | The same values in machine-readable form for the backend and safety layer |
| [`references.md`](references.md) | All sources used, with what each one supports |

## Key numbers at a glance

| Need | Value |
|---|---|
| Air temperature | 15 to 25 °C ideal; damage below 4 °C or above 36 °C |
| Light | 12 to 14 h per day; daily light integral 10 mol/m²/day or more (about 14,000 lux for 14 h under LED) |
| Air humidity | 40 to 70% RH |
| Soil | Moist, close to container capacity, never waterlogged; pH 6.0 to 7.5 |
| Pot | 2 to 3 L with drainage, potting mix with about 25% perlite |
| Water trigger | Moisture index below 60 (0 = air-dry mix, 100 = container capacity) |
| Refill target | Index 85 to 90, in small pulses |
| Dose cap | 150 mL per watering, 500 mL per day |

## Inputs to other parts of the project

- **`ai/assistant-spec/` safety rules:** section 6 says its defaults are "to confirm with the plant research". The confirmed values are in [`thresholds-and-calibration.md`](thresholds-and-calibration.md). The main change is to express the pump limits in mL (150 mL per watering, 500 mL per day) once the pump is calibrated, instead of 15 s and 60 s.
- **`ai/knowledge-base/`:** [`spearmint-requirements.md`](spearmint-requirements.md) is written so it can be used directly as a knowledge-base document for the assistant.
- **`hardware/components/`:** each pot needs a small LED grow light, because a Tunis window in winter gives about 10 h of daylight.
