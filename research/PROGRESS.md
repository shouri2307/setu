# SETU flood model — how it was built and validated

This is the short version of the research trail behind `research/susceptibility.csv`
(the model that `pipeline/p3_flood.py` turns into flood depths). Kept for anyone who
wants to understand or rebuild the model, not as a live task list.

## The problem with the original model

The first version of SETU calibrated two global knobs (runoff coefficient, drain
capacity) against 18 wards reported flooded in October 2020 — and was tested against
the same 18 wards. Measured honestly, it scored **AUC 0.49**, statistically no better
than flooding random wards. It looked plausible on the map; it wasn't predictive.

## What replaced it

A learned flood-susceptibility model per ward, trained on **8 real Hyderabad floods**
(Sept 2016, Oct 2020, Jul 2021, Jul 2023, and three 2025/2026 storms — see
`research/labels.csv`, ~120 ward mentions sourced from news reports, hand-mapped to
GHMC wards). Features are physical, not tuned per ward: height above nearest drainage,
low-pocket fraction, wetness index, distance to water/waterways, built-up fraction,
upstream catchment area (see `research/build_features.py`).

The model is an ensemble (logistic regression + random forest + gradient boosting,
rank-averaged) with ward area included as a covariate so it can't just learn "big
wards get named in the news more" — every ward is scored at a fixed reference size
(`research/train_final.py`).

Rainfall → depth is a separate, explicitly-stated assumption: wards are ranked by
susceptibility, then the rainfall-at-which-each-ward-floods curve is anchored to three
documented reference points (~3% of wards flood at 50mm, ~20% at 192mm/Oct-2020,
~55% at 300mm). This is not learned — it's stated as an assumption in the app's
Limitations panel.

## How it's tested

- **Leave-one-event-out**: trained on 7 floods, scored on the 8th it never saw.
  Repeated for all 8. Mean AUC **0.69** (raw), **0.67** when only comparing wards of
  similar size (rules out the area confound). One event (a June-2026 storm that
  flooded central-city junctions from choked drains, not terrain) scored near chance —
  stated honestly in the app rather than hidden.
- **Independent check**: scored against GHMC's own published list of chronic
  waterlogging wards — data never used anywhere in training. **AUC 0.79.**
- **Controls that confirm this is real**: a model trained on the same features with
  shuffled labels scores ~0.50 (chance). The old model scores 0.49 on the same tests.

## What was tried and didn't help (so it isn't tried again)

- Three DEM sources compared under the identical protocol (SRTM, Copernicus GLO-30,
  FABDEM) — SRTM already wins; newer isn't always better here.
- Extra features: road density, lake area, built-up density alone, OSM road
  underpasses — none improved the honest score.
- Point-level (colony, not ward) labels from geocoding — OSM only has neighbourhood
  centres, not colony boundaries, so points landed in the wrong ward almost half the
  time. Ward-level hand-mapping was more accurate than automated geocoding.
- A separate model trained on GHMC's 248 official "vulnerable locality" points
  (real lat/lon) — predicts *where people live near water*, not *where water actually
  rose in a flood*; the two label sets only weakly agree (Spearman 0.23–0.26).
- An intervention cost/build-time estimate feature (real ₹-crore figures per ward) —
  built and validated to a realistic scale, then deliberately removed: it was the
  least-defensible part of the app to stand behind live, against a flood model that
  has real held-out evidence.

## To rebuild the model from scratch

```
python research/build_features.py   # DEM + OpenStreetMap + satellite land cover -> features.csv
python research/train_final.py      # trains the model -> susceptibility.csv, model_card.json
python pipeline/p3_flood.py         # susceptibility -> per-ward flood depth by rainfall
python pipeline/p4_network.py       # hospital road-reachability per scenario
python pipeline/p5_recommend.py     # matches Japanese interventions to each ward
python pipeline/p6_export.py        # writes everything the web app reads
python pipeline/p7_roadgraph.py     # compact road graph for live re-routing in the browser
```

All of the above reproduce byte-identical output on a clean rerun — verified.
