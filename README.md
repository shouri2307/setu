# SETHU — location intelligence for Hyderabad

**SETHU** (*sethu* = "bridge" in Telugu and Hindi) turns any Hyderabad address into an explainable report. Search a place,
paste a Google Maps link or click the map, and open one of three separate full-page reports built on one engine:

| Report | For | What it gives |
|---|---|---|
| 🏠 **Customer** | families buying or renting | plain-language verdict, rain-vs-water curve, neighbourhood and facilities, lakes and terrain, official drainage records, true cost of buying (duties + brokerage) with a price sanity check |
| 🏷 **Real estate agent** | real-estate professionals | sourced market band, price check against the user's own comparables, commission and deal economics, negotiation evidence, a printable listing brief |
| 🛡 **Insurer** | underwriters and claims analysts | Motor / Property / Health-access exposure tiers (A–E) with factor weights, illustrative loadings, a claim **evidence check** (rain on the claim date, terrain, official inundation list) and API-ready JSON |

Every report opens with a **Location Score** (0–100) from eight pillars: water and flood safety · health-care access ·
schools and daily needs · transit and main roads · parks and lakes · air quality (live) · fire and police reach · jobs and
lifestyle hubs. Flood safety is one pillar, not the whole product.

Prices are the proposed model; the demo has no paywall and takes no payment. Each report is a one-page summary — verdict, why the score is what it is, nearest hospital / mall / metro / school — with the
detailed report one click away as a PDF download.

> The original government **Flood Planner** (ward flood model + Japanese flood-control methods) is kept at
> `web/planner.html` and linked from the header. §4–§7 below describe it.

---

## 1. Run it

```bash
python -m venv .venv && .venv/Scripts/activate      # Windows; use source .venv/bin/activate elsewhere
pip install -r requirements.txt
cp .env.example .env                                # every key is optional — see below
python serve.py                                     # http://localhost:8000
```

No build step. The site is static HTML + vanilla JS (`web/`) plus a few small Python functions (`api/`).

**Optional keys** (`.env`; the app works without any of them):

| Variable | Adds | Cost |
|---|---|---|
| `GROQ_API_KEY` | the AI explanation box (otherwise a built-in summary is shown) | free tier |
| `TOMTOM_API_KEY` | a second address-search provider (merged with Photon and the local index) | free, no card |
| `GOOGLE_MAPS_BROWSER_KEY`, `GOOGLE_PLACES_SERVER_KEY` | Google map and live nearby places. The code is in place but dormant — Google needs a prepaid billing account | paid |
| `OPENTOPOGRAPHY_API_KEY` | only for rebuilding the flood model's terrain features | free |

Check what the server sees at `/api/health` (it reports key presence, never the keys).

## 2. Data — everything is free and public

| Layer | Source | Used for |
|---|---|---|
| Places and facilities | OpenStreetMap + Overture Maps (merged, de-duplicated) | 2,569 hospitals, 4,417 schools, 4,262 banks, 1,573 markets, 1,700 parks, 319 police and 105 ambulance points, malls, cinemas, job hubs, main roads |
| Address search | Photon (OSM), local index, optional TomTom, pasted Google Maps links | search box |
| Transit and police | TSRTC bus stops, HMRL metro stops, Hyderabad police stations (OpenCity, public domain) | transit and fire/police pillars |
| Drainage and tanks | Telangana State GIS (TGRAC public ArcGIS service) | 96 GHMC nalas with 1,162 segments (existing vs proposed width), 3,965 drain/canal lines, 847 tank outlines, 23 official inundation areas |
| Tank encroachment | HYDRAA water-body assessment (TGRAC) | 1,192 water bodies, each Live / Partially / Totally encroached for 2014 and 2023 |
| Lakes | HMDA notified-lake list | 2,980 lakes with notification dates; official FTL map PDF links for the 27 Hyderabad-district lakes |
| Government health | Telangana health GIS | government hospitals, clinics, ambulance stations |
| Live weather | Open-Meteo | rain forecast, rain on a past date, elevation, air quality |
| Market rates | property-portal asking prices, compiled and cleaned (`web/data/rates.json`) | 77 priced localities; 140 of 145 wards sit within 4 km of a priced place |

How rates are handled: ChatGPT-compiled batches go through `pipeline/p10a_clean_paste.py` (repairs the paste) and
`pipeline/p10_rates_import.py` (validates, clamps, flags outliers, labels rows "AI-compiled estimate"). Where two source
sets price the same place, the report shows the outer limits and says the sources disagree. Where no defensible price
exists the cell stays empty — nothing is invented.

## 3. How to read the numbers (honesty rules)

Each factor in a report carries a status, and the app shows it:

* **Validated** — the ward-level flood ranking only (§5). Tested on floods it never saw.
* **Indicative** — lake distance, terrain pocket, facility reach, road/hub counts. Reasonable signals, not validated.
* **Official** — government records shown as published (nalas, tank status, inundation list). They carry no stated date.

Things the app does **not** claim:
* Prices are **asking prices**, not deal prices. Registered deals sit roughly 13–22% lower according to one secondary source.
* Tank status is a **satellite classification**, not a legal notice. FTL and buffer status must be confirmed with HMDA/GHMC.
* Tier loadings are **illustrative**, not actuarial rates.
* The flood model covers the **145 GHMC wards** (the pre-2026 map). Addresses just outside get a report without a flood
  figure, clearly marked. The 2026 GHMC reorganisation is not reflected.
* HMDA lake **boundaries** are not included — only the notification list and map links.
* The official inundation list is a weak check: 43% of its spots fall in the model's top quartile of wards (25% by chance).

## 4. The flood model (ward level, validated)

`research/train_final.py` trains a flood-susceptibility score (0–1) for every ward from terrain and land-cover features built
in `research/build_features.py`: height above nearest drainage (HAND), topographic wetness, sink fraction, nearness to
waterways and water bodies, built-up share (ESA WorldCover), relative elevation and upstream catchment. Inputs are public: a
30 m elevation model (SRTM), OpenStreetMap and satellite land cover.

**Labels:** flooded localities from 8 documented Hyderabad floods (2016, 2020, 2021, 2023 and three 2025/2026 storms), 78
flooded-ward records covering 49 distinct wards, each with source URLs (`research/labels.csv`). The model is an ensemble of logistic regression, random
forest and gradient boosting (rank-averaged). Ward area is a training covariate then held at a reference value, so the model
cannot learn "big wards get named in the news".

**Rain-to-flood depth is an assumption, not learned.** Wards are ranked by susceptibility; the rainfall at which each floods is
set by anchoring the "share of city flooded" curve to ~3% at 50 mm, ~20% at 192 mm (the real Oct-2020 extent) and ~55% at
300 mm (`pipeline/p3_flood.py`). The app says so.

**Validation (the honest way):**
* Leave-one-event-out over the 8 floods: **mean AUC 0.69** (0.5 = coin flip), 0.67 among wards of similar size. One 2026 storm
  caused by choked drains scored near chance, and the app shows that.
* GHMC's own list of chronically waterlogged wards, never used in training: **AUC 0.79**.
* Controls: shuffled labels score ~0.50; the first version of this project (calibrated and graded on the same 18 wards)
  scored **0.49** — it looked plausible and wasn't predictive. Everything here is the rebuild.

What was tried and did not help (extra DEMs, road density, lake area, point-level geocoded labels, a model trained on
GHMC's 248 vulnerable-locality points) is in [`research/PROGRESS.md`](research/PROGRESS.md).

## 5. Insurance tiers

Each line — water, motor, property, health — gets a tier A–E from a weighted blend of its factors (cut points in
`CUTS` in `web/platform/engine.js`, calibrated so tiers spread across the city instead of clumping). The report lists every
factor, its weight and its status, so an underwriter can see why a place is D and not B. The claim evidence check
cross-references rain on the claim date, modelled depth, terrain and the official inundation list, and returns a triage level —
not an accusation.

## 6. The Flood Planner (`web/planner.html`)

A live map of 145 wards over a rainfall slider (25–300 mm, including the 192 mm October-2020 storm): ward flood depth,
hospital road access recomputed live over the real road network, and a ranked shortlist of Japanese flood-control methods
matched by a transparent rule engine (`pipeline/p5_recommend.py`, 14 interventions in `data/interventions.json`). Applying
an intervention re-runs the depth and the hospital-access calculation in the browser; undo is one click. Estimated
reductions are modelled from published impact ratings, not hydraulically re-simulated.

## 7. Tests

```bash
node tests/engine.test.js            # ≈3,000 checks, ~seconds
node tests/engine.test.js --net      # also hits the live APIs
python tests/audit_facilities.py     # audits facility coverage against Google (needs a Google key)
```

The harness loads the engine in a Node sandbox and checks data integrity, geometry, scoring invariants, golden locations
(`tests/golden.json`), and that **every ward × every report variant** renders without errors. Printing was verified by
rendering to PDF through headless Edge.

## 8. Deploying (Vercel)

The deployed site is `web/` served as static files plus the functions in `api/` (all standard-library Python; none of the
offline pipeline runs at request time).

```
api/ask.py        Groq proxy (the key stays on the server)
api/config.py     tells the browser which optional providers are enabled
api/health.py     key-presence and provider check
api/suggest.py    TomTom address suggestions
api/places.py     Google nearby places (dormant without keys)
api/place.py      Google place details (dormant without keys)
api/_google.py    shared helpers
```

1. Import the repo at vercel.com/new (pushing to `main` redeploys automatically).
2. **Settings → Environment Variables:** add `GROQ_API_KEY` and, optionally, `TOMTOM_API_KEY`. Redeploy afterwards.
3. **Settings → Deployment Protection:** disable *Vercel Authentication* for Production, otherwise visitors (and the QR code)
   hit a Vercel login page.

`vercel.json` points the static output at `web/` and sets function time limits; `.vercelignore` keeps the pipeline, research
files and decks out of the deployment. The free Hobby plan is intended for non-commercial use.

## 9. Repo structure

```
serve.py                 local server: static files + the same /api/* routes as Vercel
vercel.json, .vercelignore, requirements.txt, .env.example

web/
  index.html             the platform: search, map, three reports
  planner.html           government Flood Planner (§6)
  platform/
    engine.js            scoring, tiers, claim check, market lookup, live APIs
    reports.js           the Customer / Agent / Insurer pages
    app.js               router, search, report tabs, info cards, print and QR
    map.js               Leaflet map (Google adapter dormant), Hyderabad-only bounds, overlays
    charts.js, styles.css
  data/                  everything the browser reads: zones, wardfeat, wardloc, geo, gov, hmda_lakes,
                         hydraa_tanks, rates, model, evidence, validation, roadgraph, …
  vendor/                Leaflet, QR library and the Inter font, vendored (no CDN dependency in the demo)

api/                     Vercel functions (§8)

pipeline/                data pipeline — run in order for the flood model, any time for the data layers
  p1–p7                  DEM and roads → ward polygons → flood depth → hospital access → interventions → exports
  p8, p11, p12, p13      OSM + Overture places, main roads and hubs → web/data/geo.json
  p9, p16                ward features and ward Location Scores
  p10a, p10              rates: clean a pasted CSV → validated rates.json
  p14, p18               Telangana GIS: nalas, drains, tanks, inundation list; HYDRAA tanks; health points
  p15, p15b              HMDA lake list and official FTL map links
  p17                    TSRTC / HMRL / police open data
  tgrac_explore.py       lists any TGRAC service and layer (for finding more data)

research/                how the flood model was built and validated (train_final.py, labels.csv, model_card.json, PROGRESS.md)
data/                    intermediate flood-planner outputs (regenerated by the pipeline)
tests/                   engine.test.js, golden.json, audit_facilities.py
docs/, PITCH.md, PROJECT_STATUS.md    status, the rates prompts and the 90-second pitch
```

Rebuild the flood model from scratch:

```bash
python research/build_features.py && python research/train_final.py
python pipeline/p3_flood.py && python pipeline/p4_network.py && python pipeline/p5_recommend.py
python pipeline/p6_export.py && python pipeline/p7_roadgraph.py
```

Refresh the data layers: `p8` → `p11` → `p13` → `p14` → `p17` → `p18` → `p12` (merge) → `node pipeline/p16_wardloc.js`.
Raw responses are cached in `research/*_cache/` (git-ignored) and calls are paced politely.

## 10. Tech stack

Vanilla JS and Leaflet on the front end (no framework, no build step, so it runs on any laptop on stage); Python standard
library for the server and functions; Python (pandas, geopandas, rasterio, scikit-learn, networkx) for the offline pipeline;
DuckDB over Overture's public Parquet for places. Data: OpenStreetMap, Overture Maps, Telangana State GIS, HMDA, OpenCity,
Open-Meteo, ESA WorldCover, SRTM, and news reports for flood labels.

## 11. Licences and credits

OpenStreetMap © OpenStreetMap contributors (ODbL) · Overture Maps (open licences) · OpenCity datasets (public domain) ·
Telangana State GIS / TGRAC and HMDA public services (shown as published, with source labels) · Open-Meteo (non-commercial
free tier) · Esri World Imagery tiles for the optional satellite view · Inter font (SIL OFL).
