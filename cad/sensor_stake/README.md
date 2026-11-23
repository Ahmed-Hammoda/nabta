# Nabta sensor stake: CAD and printing

The stake goes into the jar's soil. It holds the soil probe in the root zone, the air sensor in a vented hexagonal lantern, and the light sensor under a window in the cap, looking up.

This is the **new design** (updated 23 Nov 2026): the lantern and cap are a larger hexagon than the first version.

## Files

| File | Part | Size (mm, outer box) | Print |
|---|---|---|---|
| `parts/housing.step` | Housing: holds the soil probe's electronics, blade goes through the floor | 60 × 36 × 51 | PETG or ASA, dark |
| `parts/stem.step` | Stem between the housing and the lantern | from the first design | PETG or ASA, dark |
| `parts/lantern.step` | Vented hexagonal lantern for the air sensor | 88 × 76 × 58 | **Clear PETG** |
| `parts/cap.step` | Cap with the light-sensor window | 90 × 78 × 13 | PETG or ASA, dark |
| `parts/window_disc.step` | Clear window in the cap | from the first design | **Clear PETG**, 100 % infill |
| `print_stl/cap.stl` | Cap, ready to slice | 90 × 78 × 12 | |
| `print_stl/stem.stl`, `print_stl/window_disc.stl` | Stem and window disc, ready to slice | | |

## Printing

Bambu Studio opens `.step` files directly: **File → Import → Import 3MF/STL/STEP…**, pick the part, place it flat and slice. You don't need STL files for the housing and lantern. To make one anyway, right-click the part → **Export as one STL**.

Suggested settings: 0.2 mm layers; 4 walls and 30 % infill for the housing and stem; 2 walls and 15 % infill for the lantern; 3 walls and 20 % infill for the cap. The window disc prints best at 0.1–0.15 mm layers and 100 % infill.

## Check before you print

- The stem and window disc did not change in this update. Check that the stem still fits the new housing and lantern, and that the window disc fits the new cap, before printing all of them.
- Measure your boards with a caliper and compare them with the slots in the parts: capacitive soil sensor v1.2 (about 23 × 98 mm, electronics in the top 26 mm), BME280 breakout and GY-302 BH1750 (about 18.5 × 13.9 mm).

## Wiring

One 5-core cable leaves the stake: 3.3 V, GND, SDA, SCL and the soil signal (to ADS1115 A0). I²C addresses: BME280 0x76, BH1750 0x23 (ADDR to GND), ADS1115 0x48. Full wiring: [`docs/designs/nabta_wiring_3d.html`](../../docs/designs/nabta_wiring_3d.html).

## Design notes

- Only the probe's blade is in the soil. Its electronics stay above the soil line, inside the housing. Paint the blade's cut edges and the electronics with clear nail polish or conformal coating, or the reading drifts within weeks.
- The air sensor sits in the vented lantern, away from the Pi's heat and out of direct water, so it reads the air around the plant.
- The light sensor looks up through the cap window, so leaves and the lantern walls don't shade it.
