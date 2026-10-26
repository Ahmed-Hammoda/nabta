# Spearmint requirements

**Plant:** spearmint (*Mentha spicata*), family Lamiaceae · **Owner:** Yassine Mtibaa

Spearmint wants moist but never waterlogged soil, 12 to 14 hours of bright light, and 15 to 25 °C. In a Tunis winter room, light is the weak point, so each pot needs a small LED grow light.

This file is also meant as a knowledge-base document for the AI assistant. Source keys in brackets are listed in [`references.md`](references.md).

## Growing conditions

| Need | Ideal | Tolerated | Damage risk | Source |
|---|---|---|---|---|
| Air temperature | 15 to 25 °C | 10 to 30 °C | Below 4 °C or above 36 °C | [ISWS], [OMAFRA] |
| Day and night | About 25 °C by day, 15 °C at night | | | [NSW] |
| Light duration | 12 to 14 h of light (sun plus LED) | 6 to 8 h of direct sun | Under 6 h of bright light: leggy, pale growth | [UCCF], [ISWS] |
| Daily light integral (DLI) | 10 mol/m²/day or more | 6 mol/m²/day | Below 6 mol/m²/day | [PG] (tested 6 to 18) |
| Light as lux | About 14,000 lux average for 14 h | About 8,000 lux for 14 h | | Our conversion, see the note below |
| Air humidity | 40 to 70% RH | 30 to 80% RH | Over 80% for long periods or wet leaves overnight: rust and leaf spots | Our judgment; leaf wetness risk from [UCCF] |
| Soil water | Moist, close to container capacity | Short dips to about 80% of field capacity | Saturated soil (root rot); long dry spells (wilting, growth loss) | [FUM], [OMAFRA] |
| Soil pH | 6.0 to 7.5 | 5.5 to 7.5 | Below 5.5 | [NSW], [OMAFRA] |

**Lux note.** The BH1750 light sensor measures lux, not the light plants use. For white LEDs, 1,000 lux is roughly 14 µmol/m²/s; for sunlight it is roughly 18.5 µmol/m²/s. So for LED light, DLI ≈ lux × hours × 0.00005. These are approximate factors, good enough for alerts but not for light figures in the report. The BH1750 tops out at 65,535 lux, which direct sun can exceed.

## Pot and soil

- Two identical pots of 2 to 3 L, about 15 to 18 cm wide, with drainage holes. The saucer must not be shared with the float switch.
- Potting mix rich in organic matter, with about 25% perlite. NSW DPI recommends soil that is "well drained yet holds plenty of water" [NSW].
- Same mix bag, same fill weight and same plant batch for both pots. Weigh each pot when it is filled, since weight is our backup moisture check.
- No fertilizer during the run, or the same dose on the same day in both pots. NSW DPI warns against excess nitrogen [NSW].
- No harvesting during the run, or identical cuts on both pots, leaving about 2.5 cm of stem [UCCF].
- Repot by 2 Nov so the plants settle for a week before the study starts on 9 Nov.

## Signs of over- and under-watering

Under-watering shows as droop that recovers within hours of watering. Over-watering shows as yellow or brown leaves that wilt even though the soil reads wet. The assistant must never answer that second case with "water more".

| Condition | What you see on the plant | What the sensors show | Action |
|---|---|---|---|
| Under-watered, mild | Tips droop in the afternoon and recover overnight | Moisture falling toward the trigger; high light or temperature | Normal; the rules engine waters at the trigger |
| Under-watered, severe | Whole stems wilt, lower leaves dry and crisp, slow regrowth | Moisture below the low alarm for hours | Water at once, log a stress event, take a photo |
| Over-watered | Leaves turn yellow or brown and wilt; stems soft at the base [LF] | Moisture above the high alarm for over 24 h; water standing in the saucer | Block watering and check drainage; roots rot if the pot bottom stays wet |
| Leaf disease | Small raised spots under the leaves that turn orange or brown (rust) [UCCF] | High humidity; leaves wet overnight | Water at the soil, never the leaves, and water in the morning |
| Cold stress | Dark, limp leaves after a cold night | Air temperature under 10 °C | Move the pots away from the window at night |
| Low light | Long gaps between leaf pairs; small, pale leaves | Low daily lux-hours | Add LED hours or move the pots closer to the window |
