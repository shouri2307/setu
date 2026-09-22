# SETU — Hyderabad Monsoon Flood & Japanese Intervention Planner

Slide the rainfall, watch Hyderabad's 145 GHMC wards flood, click any ward for its
depth, hospital access, and a ranked shortlist of real Japanese flood-control
methods matched to that ward's terrain — with a live AI advisor and honest,
tested validation numbers, not a self-claimed accuracy figure.

## Run it

```
pip install -r requirements.txt
cp .env.example .env          # add GROQ_API_KEY (AI advisor) — everything else works without it
python serve.py
```

Open `http://localhost:8000`.

## What's actually validated here

The flood model doesn't guess which wards flood — it's trained on real flooded
localities from **8 documented Hyderabad floods** (2016–2026) and tested the honest
way: trained on 7, scored on the 8th it's never seen, repeated for all 8, plus a
final check against GHMC's own published flood data that was never used in training.

**Result: AUC 0.69 on held-out floods, 0.79 against independent government data**
(0.5 = coin flip). An earlier version of this model scored 0.49 — no better than
guessing — until it was rebuilt and tested properly. The full story, including what
was tried and *didn't* work, is in [`research/PROGRESS.md`](research/PROGRESS.md).
The app's own **Limitations** button shows these numbers live, along with what the
model gets wrong (it under-ranks flooding caused by choked drains, which terrain
data can't see).

## How it's built

```
pipeline/
  p1_fetch.py       downloads raw DEM + roads + hospitals + water bodies (OpenTopography, OSM)
  p2_zones.py       builds the 145 GHMC ward polygons + elevation/slope/drainage-adjacency
  p3_flood.py       turns learned ward susceptibility into flood depth per rainfall scenario
  p4_network.py     hospital reachability over the road network per scenario
  p5_recommend.py   matches Japanese flood-control interventions to each ward's terrain
  p6_export.py      packages everything into the small JSON files the web app reads
  p7_roadgraph.py   exports a compact road graph so the browser can re-route live
                     when you apply an intervention

research/
  build_features.py   DEM + OpenStreetMap + satellite land cover -> per-ward terrain features
  train_final.py      trains the flood-susceptibility model, runs all validation, writes:
  susceptibility.csv     -> per-ward flood-proneness score (what p3_flood.py reads)
  model_card.json        -> the validation numbers shown in the app
  labels.csv           the 8 real floods used to train the model, with sources
  labels_chronic.csv   GHMC's independent chronic-waterlogging list, used only to test
  PROGRESS.md          the research trail: what was tried, what worked, what didn't

web/
  index.html          the app (map, rainfall slider, ward panel, AI advisor)
  data/                the JSON files p6_export.py / p7_roadgraph.py produce

serve.py     serves web/ and proxies AI questions to Groq (key stays server-side)
config.py    paths and the DEM source used by p1_fetch.py
```

To rebuild the model and every data file from scratch:

```
python research/build_features.py
python research/train_final.py
python pipeline/p3_flood.py
python pipeline/p4_network.py
python pipeline/p5_recommend.py
python pipeline/p6_export.py
python pipeline/p7_roadgraph.py
```

Every step above reproduces byte-identical output on a clean rerun — checked, not assumed.

## Stated limitations (also shown in-app)

- Ward-resolution, not street-level — GHMC's actual stormwater drain network is private.
- Rain is modelled as uniform across the city ("what if X mm fell everywhere") — real
  storms are uneven; this is intentional scope, not an oversight.
- The rainfall-to-flood-share curve is anchored to three documented reference points,
  not learned — stated as an assumption.
- Flood records are news-reported place names — presence-only; an unnamed ward is
  unknown, not confirmed dry.
