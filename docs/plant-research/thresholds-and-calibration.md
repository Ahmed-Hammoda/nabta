# Starting thresholds and calibration

**Owner:** Yassine Mtibaa · values to freeze on 8 Nov 2026

Start with a watering trigger at 60 on a 0 to 100 moisture index and refill to about 85, then tune these values during the calibration week (2 to 8 Nov).

## Moisture index

The index is calculated **per pot**:

- **0** = the raw sensor reading in air-dry potting mix.
- **100** = the reading 30 minutes after watering until water drains from the bottom (container capacity).

Raw capacitive readings differ between sensors and between mixes, so never share raw numbers between pots. Store both the raw value and the index.

## Thresholds

| Signal | Starting value | Used by | Why |
|---|---|---|---|
| Water trigger | Moisture index below 60 | Rules engine | Spearmint growth drops below field capacity [FUM]; water-sensitive crops are watered after about 30% of available water is used [VT] |
| Refill target | Index 85 to 90, in small pulses with a 10 min soak between them | Rules engine | Water spreads slowly through the mix; pulsing avoids overshoot and runoff |
| Low alarm (stress) | Index below 40 for 2 h | Rules engine, app alert, AI reason code | Wilting zone; log as a stress event |
| High alarm (waterlogging) | Index above 95 for 24 h | Rules engine, app alert | Mint does not survive saturated soil [OMAFRA] |
| Hard block | No pumping above index 80, or when the tank float is low | Pump controller firmware | Safety limit that holds offline and overrides the server |
| Dose cap | At most 150 mL per watering and 500 mL per day for a 2 to 3 L pot | Pump controller firmware | Stops a stuck sensor from flooding the pot; tune after calibration |
| Heat warning | Air above 30 °C | App alert | Above the comfort band |
| Heat critical | Air above 36 °C | App alert, AI reason code | Absolute maximum for spearmint [ISWS] |
| Cold warning | Air below 10 °C | App alert | Below the comfort band |
| Cold critical | Air below 4 °C | App alert, AI reason code | Absolute minimum [ISWS] |
| Humidity warning | Above 80% RH for 12 h | App alert | Leaf disease risk |
| Low light warning | Under 120,000 lux-hours in a day | App alert | About 6 mol/m²/day under LED light |

### Mapping to the safety rules in `ai/assistant-spec/`

| Safety rule | Current default | Plant research value |
|---|---|---|
| 1. Max pump time per watering | 15 s | 150 mL; convert to seconds with the measured pump flow |
| 2. Min time between waterings | 2 h | Not set by the plant research; 2 h is compatible with pulsed refills (10 min soaks happen inside one watering) |
| 3. Max total watering per day | 60 s | 500 mL; convert with the measured pump flow |
| 4. Upper moisture limit | From plant profile | Index 80 |
| Ideal moisture range (spec example "40–60%") | 40 to 60% | Water below index 60, refill to 85 to 90 |

## Calibration week, 2 to 8 Nov

1. Fill both pots with the same mix, plant, and water until water drains. After 30 minutes, record each sensor's raw value as index 100 and weigh each pot.
2. Record each sensor in a cup of dry mix as index 0.
3. Let both pots dry without watering, and log raw values, pot weight and plant photos twice a day until the first afternoon droop. The index at the first droop sets the low alarm; move the trigger to about 20 points above it.
4. Check that the pump pulse matches the dose cap by measuring mL per second of pump time.
5. Freeze all thresholds on 8 Nov and record them in [`plant-profile.json`](plant-profile.json), so Pot A runs the same rules for the whole study.

## Open questions

- [ ] Price and availability in Tunis of potted spearmint (2 matching plants plus 1 spare), potting mix, perlite and two small LED grow lights.
- [ ] Where the pots will sit: which window, and does that room drop below 10 °C at night?
- [ ] Pot B's fixed schedule: volume and interval, to agree before 9 Nov.

Source keys in brackets are listed in [`references.md`](references.md).
