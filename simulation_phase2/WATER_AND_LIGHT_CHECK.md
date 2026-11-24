# Nabta: water amount and rule check against sources (24 Nov 2026)

Plant: spearmint (*Mentha spicata*), the mint used for tea in Tunisia ("Moroccan mint" is a spearmint
variety). This adds to `LIMITS_CHECK_and_REFERENCES.txt` (16 Nov 2026, references R1–R13), which
already checked the temperature, light, humidity and soil limits.

Each number is tagged:
- **[S]** from a source (reference number in brackets)
- **[STD]** a standard textbook value, not checked in the sources below
- **[EST]** our own estimate or calculation; it must be measured on the real jar

---

## 1. Rule check (rules v3)

| Rule | What the sources say | Verdict |
|---|---|---|
| Temperature optimal 15–25 °C, alerts below 4 / above 36 °C | FAO ECOCROP gives the same numbers [R1] | Confirmed |
| Water when soil index ≤ 70 | Water before about 40 % of the available water is used (p = 0.40) [R7, W2]; more frequent watering gave more fresh leaves and oil [W2]; at 40 % soil water, height and biomass dropped strongly [W5]; no loss above about 57–63 % of field capacity [W6] | Right idea; the number 70 must be matched to the jar (field-capacity test, section 3) |
| DRY_DANGER ≤ 25 | 6 days without water cut shoot dry weight by about 38 % [W4] | Sensible alarm |
| Dose and frequency | No source gives mL for a pot. Grower guides: water when the top 2–3 cm is dry, about every 3–5 days indoors, less in winter; check the soil, not a calendar [W8, W9] | Sensor-based watering matches; dose: see section 2 |
| Glass jar without drainage | Guides: moist, not waterlogged; standing water rots roots [W8, W9]. Peppermint is sensitive to waterlogging; another mint is more tolerant [W10] | Main risk: gravel layer, watch for standing water |
| Grow light 16 h (06:00–22:00) | Spearmint LED studies used 16 h [W11]; Moroccan mint with extra LED light in a 16 h day: +13–19 % leaves and weight [W12]; grower guide 14–16 h [W13] | Confirmed |
| Light "optimal" ≥ 285,000 lux-h (≈ 19 mol/m²/day) | Mint grows best at about 15–16 mol/day [R3, R4]; herb guides 10–14 mol/day for mint [W14, W15] | Too high: suggest 225,000 lux-h (≈ 15 mol). Not changed yet (team decision) |
| LOW_LIGHT < 90,000 lux-h (≈ 6 mol) | Lowest values recommended for mint about 6–10 mol/day [W15] | Reasonable |
| Humidity 60–70 % | Only a study on another mint species [R5] | Weak, low risk (no watering depends on it) |
| How to water | Overhead sprinklers can damage the leaves' oil glands; water the soil [W3] | Our tube waters the soil: correct |

Mild water stress: oil (aroma) stayed the same or rose, but leaf mass fell [W1, W3, W4, W5]. For tea we
want many leaves, so the soil is kept moist; it is not dried on purpose.

---

## 2. How much water per watering (calculation)

| Step | Value | Tag |
|---|---|---|
| Jar inner diameter | about 10.5 cm → surface about 87 cm² | [EST] measure the real jar |
| Soil depth above the gravel | about 7–8 cm → about 0.65 L of soil | [EST] |
| Water the plant can use in potting mix | about 25–35 % of the soil volume → about 160–230 mL (≈ 200 mL) | [STD] typical potting-mix value, to be measured |
| Allowed use before watering | p = 0.40 for mint | [S] FAO-56 Table 22 [R7] |
| **Dose per watering** | 0.40 × 200 mL ≈ **80 mL** | [EST] |
| Pump flow | 6 s = 150 mL → 25 mL/s (cup test 24 Nov 2026) | measured |
| **Pump time** | **3 s ≈ 75 mL** (now set to 6 s = 150 mL; probably too much for this jar) | [EST] |

### Water used per day
Water use = Kc × ET₀ × jar surface (1 mm of water over 87 cm² = 8.7 mL).

| Place | ET₀ (mm/day) | Use per day (Kc = 1.15) | 80 mL lasts |
|---|---|---|---|
| Indoors, winter | 1–2 [EST] | 10–20 mL | 4–8 days |
| Sunny window / balcony, spring–autumn | 3–4 [EST] | 30–40 mL | 2–3 days |
| Balcony, Tunis summer | 6–7 [EST] | 60–70 mL | about 1 day |

- Kc = 1.15 for mint at full growth (0.60 at the start, 1.10 at the end): [STD] FAO-56 Table 12 [W16].
- In the field mint uses more than 1,000 mm of water a year [W3].
- The ET₀ values are rough estimates for indoor and Tunis conditions; our collected data will give
  the real daily use.

**Safety in code:** at most 3 waterings a day (3 × 75 mL = 225 mL), 3 h apart, never when the tank is low.

---

## 3. Field-capacity test (sets the real numbers for our jar)
1. Start with dry soil (gravel layer at the bottom of the jar).
2. Give 25 mL at a time (1 s of pump), wait 10 minutes after each.
3. Stop when the soil index stops rising, or just before water appears at the bottom of the glass.
4. Total mL = water the soil holds. **Dose = 0.4 × total.**
5. The soil index at that point = field capacity (FC). Watering limit = FC − 0.4 × (FC − dry reading).

---

## References (new; R1–R13 are in LIMITS_CHECK_and_REFERENCES.txt)
- [W1] Impact of sustained deficit irrigation on spearmint (*Mentha spicata* L.) biomass production, oil yield, and oil quality. https://www.researchgate.net/publication/225777708
- [W2] Evaluation of the effect of irrigation on biometric growth, physiological response, and essential oil of *Mentha spicata* (L.) (field study, Southern Italy). https://www.researchgate.net/publication/338571479
- [W3] Organic cultivation and deficit irrigation practices to improve chemical and biological activity of *Mentha spicata* plants. Agronomy 2021, 11(3), 599. https://doi.org/10.3390/agronomy11030599 (also: Spearmint overview, ScienceDirect Topics, https://www.sciencedirect.com/topics/food-science/spearmint)
- [W4] Growth, gas exchange and essential oil production of *Mentha spicata* L. under water deficiency. Pesquisa Agropecuária Tropical. http://www.scielo.br/j/pat/a/VchGsKG6Krb3hfwkRzMfXSJ/?lang=en
- [W5] Effects of soil water content on *Mentha spicata* L. Aristotle University of Thessaloniki. http://ikee.lib.auth.gr/record/226325/?ln=en
- [W6] Impact of cyclic-mild-drought stress on the metabolism of *Mentha spicata* L. https://www.researchgate.net/publication/377816172
- [W7] Effect of deficit irrigation on yield, quality, and costs of the production of native spearmint. J. Irrig. Drain. Eng. https://doi.org/10.1061/(ASCE)IR.1943-4774.0000719
- [W8] Epic Gardening: how to grow mint indoors. https://www.epicgardening.com/growing-mint-indoors/ (grower guide)
- [W9] Savvy Gardening: how to grow mint indoors. https://savvygardening.com/how-to-grow-mint-indoors/ (grower guide)
- [W10] Effect of salinity and waterlogging on growth, anatomical and antioxidative responses in *Mentha aquatica* L. https://agris.fao.org/search/en/records/65e00fde63b8185d9cb10688
- [W11] Effect of UV-B elicitation on spearmint's (*Mentha spicata* L.) morpho-physiological traits and secondary metabolites production. Plant Growth Regulation. https://link.springer.com/article/10.1007/s10725-023-01028-7
- [W12] Impact of sub-radiation with LED light during cultivation of *Mentha spicata* on growth responses and leaf coloring. Acta Horticulturae 1296. https://www.actahort.org/books/1296/1296_83.htm
- [W13] Rootless Farm: how to grow spearmint hydroponically. https://rootlessfarm.com/plants/spearmint (grower guide)
- [W14] FYTech: herb lighting guide for vertical farming. https://www.fytechsystems.com/herb-lighting-guide-for-vertical-farming/ (vendor guide)
- [W15] Grow With Hydroponics: low-light hydroponic herb gardening. https://growwithhydroponics.com/low-light-hydroponic-herb-gardening/ (blog; its DLI arithmetic is partly wrong)
- [W16] Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). FAO Irrigation and Drainage Paper 56, Chapter 6, Table 12 (single crop coefficients Kc). https://www.fao.org/4/x0490e/x0490e0b.htm

Grower guides and vendor pages ([W8], [W9], [W13]–[W15]) are practical advice, not research. In the
paper, cite the research papers first.
