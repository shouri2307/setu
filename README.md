# SETU (設計) — Hyderabad Monsoon Flood & Japanese Intervention Planner

**SETU** ("bridge" in Hindi/Telugu; 設計 is Japanese for "design") predicts how each
of Hyderabad's 145 GHMC wards floods at any given rainfall, shows what that means for
hospital access, and recommends real Japanese flood-control methods matched to each
ward's actual terrain — all explained in plain language, backed by an AI advisor, and
validated the honest way: tested against floods and government data the model never
saw during training, with the results shown in the app itself, not just claimed.

This README covers what the app does, exactly how the flood model works and was
validated, and the full repo structure — everything needed to understand, run, or
rebuild the project from scratch.

---

## 1. What the app actually does

Open it and you get a live map of Hyderabad's 145 wards over a rainfall slider (25mm
to 300mm, plus the exact October 2020 storm at 192mm). Everything below updates as
you move the slider:

- **The map** colours every ward by flood severity (green → red) at the current
  rainfall, with a rain/water visual effect, hover highlighting, and zoom/pan.
- **Click any ward** to open its panel: current flood depth, nearest hospital, whether
  the road to it is cut off (computed live over the real road network — see §4), and,
  if it's in the news for a real flood, links to the actual articles.
- **Recommended Japanese interventions** — a ranked shortlist of real flood-control
  methods (Tokyo's Super Levee, Nagoya's rainwater-storage mandate, Sabo check dams,
  etc.) that structurally fit *that* ward — a small hillside ward and a huge flat
  riverside ward get different recommendations, because the matching is rule-based
  against real ward attributes, not the same list everywhere. Each entry explains
  what it is, why it fits this ward, a real-world example with its operator, and
  which other methods were excluded and why.
- **Apply an intervention** and the map re-runs the flood model with that ward's depth
  reduced, hospital road access recalculates live (a re-opened road can help
  *neighbouring* wards too), and you can undo it any time.
- **Play storm** animates the rainfall slider from 25mm to 300mm.
- **2020 reference view** colours wards by whether they match a real October 2020
  flood report — clearly labelled as *not* an independent test, since 2020 is one of
  the events the model trained on.
- **Limitations panel** shows the model's actual tested accuracy numbers (see §3),
  live, not just a claim.
- **Ask the AI advisor** anything about a ward — it answers only from that ward's own
  precomputed data (Groq-hosted LLM, proxied server-side so the API key never reaches
  the browser; the rest of the app works fully without it).
- **Guided intro**, a **Guide** replay button, and a **mobile-responsive layout**
  (works from a phone up through a full desktop/projector).

## 2. The problem this solves

A flood tool that just colours a map is a guess with nice CSS. The two things that
actually matter — *is the ranking of which wards flood first believable*, and *is
that shown honestly* — are usually skipped. SETU's first version made exactly that
mistake: it calibrated two global numbers against the 18 wards reported flooded in
Oct 2020, and was graded against those same 18 wards. Measured properly, it scored
**AUC 0.49** — statistically no better than flooding random wards. It looked
plausible; it wasn't predictive. Sections 3–4 are the rebuild.

## 3. How the flood model works

The model has two separate parts, and they're validated differently on purpose.

### 3.1 Which wards flood first — learned from real floods

`research/train_final.py` trains a **flood-susceptibility score** (0–1, 1 = most
flood-prone) for every ward from physical features computed in
`research/build_features.py`:

| Feature | What it measures |
|---|---|
| `hand_low_frac` | share of the ward that sits close to its local drainage line (height above nearest drainage, "HAND") |
| `twi_mean` | topographic wetness index — how much the terrain concentrates water |
| `sink_frac` | fraction of the ward in natural depressions/sinks in the elevation model |
| `waterway_near_frac` | how much of the ward is near a mapped stream/nala |
| `waterbody_near_frac` | how much of the ward is near a lake/tank |
| `builtup_frac` | paved/built fraction, from ESA WorldCover satellite land cover |
| `elev_rel_nbrs` | this ward's elevation relative to its neighbours |
| `upstream_km2` | catchment area draining into this ward through the ward-adjacency network |

All computed from a public 30m elevation model (SRTM) + OpenStreetMap + satellite
land cover — no private data, no per-ward hand-tuning.

**Training labels**: real flooded localities from **8 documented Hyderabad floods**
(Sept 2016, Oct 2020, Jul 2021, Jul 2023, and three 2025/2026 storms) — about 120
ward-mentions, sourced from news reports and hand-mapped to GHMC wards
(`research/labels.csv`, with source URLs for every entry).

**Model**: an ensemble of logistic regression + random forest + gradient boosting
(rank-averaged). Ward area is included as a training covariate and then fixed at a
reference value when scoring every ward — otherwise the model would just learn "wards
that get named in the news are bigger," not "wards that flood."

### 3.2 How much rain it takes to flood — a stated assumption, not learned

Wards are ranked by susceptibility, then the rainfall at which each one starts
flooding is set by anchoring the "share of city flooded" curve to three documented
reference points: ~3% of wards at 50mm, ~20% at 192mm (the real Oct-2020 extent),
~55% at 300mm (`pipeline/p3_flood.py`). This is explicitly an assumption, stated as
one in the app's Limitations panel — it is *not* fit to data the way §3.1 is.

### 3.3 Validation — tested against floods the model never saw

- **Leave-one-event-out**: trained on 7 of the 8 floods, scored on the 8th, repeated
  for every flood. **Mean AUC 0.69** (0.5 = coin flip), **0.67** when only comparing
  wards of similar size (rules out "big wards just get named more"). One event (a
  2026 storm that flooded central-city junctions from choked drains — not visible in
  terrain data) scored near chance, and that's stated in the app rather than hidden.
- **Independent check**: scored against GHMC's own published list of chronically
  waterlogged wards — data that was never used anywhere in training.
  **AUC 0.79.**
- **Controls**: the same model trained on shuffled labels scores ~0.50 (chance), and
  the original 2020-only-calibrated model scores 0.49 on these same tests — proving
  the improvement is real signal, not a more favourable test.

### 3.4 What was tried and didn't help

Documented in full in [`research/PROGRESS.md`](research/PROGRESS.md): three DEM
sources compared head-to-head (SRTM already wins), extra features (road density, lake
area, built-up alone, OSM underpasses — none improved the honest score), point-level
geocoded labels (less accurate than hand-mapping — OSM only has neighbourhood
centres, not colony boundaries), a model trained on GHMC's 248 official
"vulnerable-locality" points (predicts who lives near water, not where water actually
rose — only weakly agrees with real flood outcomes), and a real-₹-crore
intervention-cost feature (built, scaled correctly, then deliberately removed because
it was the least defensible part of the app to stand behind live).

## 4. The intervention recommender

`pipeline/p5_recommend.py` is deliberately **not** an LLM — it's a transparent
rule engine. Each of the 14 real Japanese interventions in `data/interventions.json`
carries hard requirements (needs an arterial road nearby / max slope / minimum ward
size / needs open land / minimum density), checked against each ward's actual
attributes. A method only appears if it structurally fits; the ones that don't are
shown too, with the specific reason they were excluded — which is what proves two
different wards don't just get the same canned list. What passes is then ranked by a
weighted blend of impact / cost / speed (impact weighted highest, so a cheap warning
system can't outrank real flood reduction in a severely flooded ward). Every
intervention names its real-world example and operating agency (e.g. Arakawa Super
Levee, Tokyo — MLIT Kanto Regional Bureau).

## 5. Hospital access under flooding

`pipeline/p4_network.py` builds the real major-road network from OpenStreetMap and
computes, per rainfall scenario, whether each ward's road to its nearest hospital
survives (a road through a ward flooded past the threshold is treated as
impassable). `pipeline/p7_roadgraph.py` exports a compact version of that same graph
so the **browser can re-run this live** (in ~7ms) when you apply an intervention —
reopening a road can help wards other than the one you fixed.

## 6. Repo structure

```
README.md              this file
requirements.txt       Python dependencies
config.py              paths + the DEM source used by p1_fetch.py
serve.py               serves web/ and proxies AI questions to Groq (key stays server-side)
.env.example            copy to .env and fill in GROQ_API_KEY / OPENTOPOGRAPHY_API_KEY

pipeline/                        the production data pipeline, run in order
  p1_fetch.py                    downloads raw DEM + roads + hospitals + water bodies
  p2_zones.py                    builds the 145 ward polygons + elevation/slope/adjacency
  p3_flood.py                    susceptibility -> flood depth per ward per rainfall scenario
  p4_network.py                  hospital road-reachability per scenario
  p5_recommend.py                matches Japanese interventions to each ward (§4)
  p6_export.py                   packages everything into the small JSON files the app reads
  p7_roadgraph.py                exports the compact road graph for live browser re-routing

research/                        how the flood model itself was built and validated
  build_features.py              DEM + OpenStreetMap + satellite land cover -> features.csv
  water_utils.py                 shared helper (water-body geometry) used by build_features.py
  train_final.py                 trains the model, runs all validation, writes the two files below
  susceptibility.csv               -> per-ward flood-proneness score (p3_flood.py reads this)
  model_card.json                  -> the validation numbers shown in the app's Limitations panel
  labels.csv                     the 8 real floods used to train the model, with source URLs
  labels_chronic.csv             GHMC's independent chronic-waterlogging list — used only to test
  osm_waterways.json             raw OpenStreetMap waterway data (input to build_features.py)
  external/vulnerable_localities.geojson   GHMC's official 248-point flood-vulnerability list,
                                            used only as an independent check, never for training
  PROGRESS.md                    the research trail — what was tried, what worked, what didn't

data/                             intermediate pipeline outputs (regenerated by pipeline/*.py)
  zones.geojson, zones_enriched.geojson    ward geometry + terrain attributes
  scenarios.json                 flood depth per ward per rainfall scenario
  network.json                   hospital reachability per scenario
  recommendations.json           full (non-slimmed) intervention matching per ward
  interventions.json             the 14 Japanese intervention definitions
  intervention_explain.json      plain-language "what it is" text per intervention
  validation_2020.json           source facts for the Oct-2020 reference view
  raw/                            downloaded source data (DEM, OSM extracts) — gitignored, regenerable

web/
  index.html                     the entire frontend — map, panel, AI advisor, everything in §1
  data/                          the small JSON files p6_export.py / p7_roadgraph.py produce
                                  (this is ALL the browser ever reads — no server-side logic
                                  except the AI proxy)
```

## 7. Setup & running

```bash
pip install -r requirements.txt
cp .env.example .env          # add GROQ_API_KEY for the AI advisor — everything else works without it
python serve.py
```

Open `http://localhost:8000`.

### Rebuilding the model and every data file from scratch

```bash
python research/build_features.py   # terrain features from DEM + OSM + satellite land cover
python research/train_final.py      # trains the model, writes susceptibility.csv + model_card.json
python pipeline/p3_flood.py         # susceptibility -> flood depth per rainfall scenario
python pipeline/p4_network.py       # hospital road-reachability per scenario
python pipeline/p5_recommend.py     # matches interventions to each ward
python pipeline/p6_export.py        # writes everything web/data/*.json
python pipeline/p7_roadgraph.py     # compact road graph for live browser re-routing
```

Every step above has been verified to reproduce **byte-identical output** on a clean
rerun — checked, not assumed. `pipeline/p1_fetch.py` and `pipeline/p2_zones.py` only
need to run once, from `data/raw/` — see their docstrings for the API keys they need.

## 8. Tech stack

- **Frontend**: a single static HTML file — vanilla JS, no build step, no framework.
  Chosen deliberately so it works reliably on any laptop during a live demo.
- **Backend**: Python's built-in `http.server`, serving static files and proxying one
  endpoint (`/api/ask`) to Groq so the API key never reaches the browser.
- **Model pipeline**: Python (pandas, geopandas, rasterio, scikit-learn, networkx).
- **Data**: OpenTopography (DEM), OpenStreetMap (roads/water/hospitals), ESA
  WorldCover (land cover), GHMC's own published flood data, and news reports for
  training labels — all public.

## 9. Stated limitations (also shown live in the app's Limitations panel)

- Modelled at ward resolution, not street level — GHMC's actual stormwater drain
  network is private and unavailable.
- Rain is modelled as uniform across the city ("what if X mm fell everywhere") —
  real storms are uneven (Oct 2020: ~197mm at Begumpet vs ~320mm at Ghatkesar). This
  is the app's intended scope, not an oversight — it answers "what would this
  rainfall do to every ward," not "what did this exact storm do."
- The rainfall-to-flood-share curve (§3.2) is anchored to three documented points,
  not learned.
- Flood training records are news-reported place names — presence-only; a ward with
  no report is *unknown*, not confirmed dry.
- The model under-ranks flooding caused by choked drains and street-level chokepoints
  (invisible to terrain data) — the one held-out event dominated by this scored near
  chance, and that's shown rather than hidden.
- Intervention "after" effects are a modelled estimate from published impact ratings,
  not a hydraulic re-simulation.
