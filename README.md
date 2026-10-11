# SETHU — the credit score for any address in Hyderabad

> **Type an address. In two seconds SETHU tells you whether to buy it, how to price it, or how to insure it — and shows its working.**
>
> *Sethu* means **bridge** (Telugu / Hindi): one engine that gives home buyers, real-estate agents and insurers the same
> facts about a place, so all three negotiate from the same truth.

**What SETHU is:** an *address intelligence* product — a due-diligence report for any place in Hyderabad that combines flood
and lake exposure, official drainage and tank records, nearby hospitals / malls / metro / schools, live air quality and
local price bands into one explainable **Location Score (0–100)**.

**What SETHU is not:** a flood-detection or flood-prediction model. Flooding is **one of eight factors** (22% of the score).
The original flood-planning work still lives in this repo (`web/planner.html`, `research/`) as the engine's validated
water-risk layer and as a government view — it is the foundation, not the product.

---

## 1. Who it is for, and what each report gives them

Every report opens as a **one-page summary** (verdict, *why the score is what it is*, the nearest hospital / mall / metro /
school, plus the calculators), with a **Download full report (PDF)** button for the detailed version. Hover the **ⓘ** next
to each report to see what it shows and why it helps.

| Report | For | The summary page | Why it is useful |
|---|---|---|---|
| 🏠 **Customer** | families buying or renting | verdict ("High caution / Proceed carefully / Looks reasonable"), three key numbers (water in a 2020-size storm, nearest lake, air quality), the Location Score dial, *why the score is X* (8 factor bars), nearest hospital / mall / metro / school / market, and a **true-cost calculator** (price + 6% duties + brokerage = total) with a **price meter** showing the quoted ₹/sq ft against the area's asking band | spots a flood- or lake-risk problem and an over-priced quote **before** the advance is paid |
| 🏷 **Real estate agent** | agents and brokers | listing verdict, the area's **market price band**, nearest hospital / metro / mall / school, **selling points** and **what buyers will push back on**, a **price check** against the band and the agent's own comparables, and **commission / deal economics** | prices a listing with evidence and answers the lake / flood question before the buyer asks it |
| 🛡 **Insurer** | underwriters and claims teams | **Motor, Property and Health-access risk tiers (A–E)** with the biggest drivers, the **claim evidence check** (was there rain at that place on the claim date? is the location susceptible? is it on the official inundation list?), a 7-day rain outlook, nearest care / fire / police | prices risk by location and fast-tracks genuine claims; doubtful ones go to review with reasons (triage, never an accusation) |

The full PDF adds: rain-versus-water curve, every flag, checklist, official drainage and tank records, trade routes and demand
drivers, every facility nearby, API-ready JSON (insurer), and the limits.

---

## 2. How a score is built

An address goes through five steps, all in `web/platform/engine.js`:

1. **Locate** — point-in-polygon against the 145 GHMC wards (or the nearest ward within ~22 km, flagged "outside the flood model").
2. **Pull precomputed ward facts** — flood-susceptibility percentile, modelled depth at 100 / 192 / 300 mm of rain, whether the road to the nearest hospital is cut.
3. **Measure the address itself** — haversine distance to the nearest facility of each type and counts within 1 / 2 / 3 km; distance to the nearest lake / tank polygon; distance to GHMC nalas and the official inundation list; terrain pocket from live elevation (pin vs the average of points ~600 m around).
4. **Turn each measurement into 0–1** with simple piecewise-linear curves (for example a hospital at ≤ 300 m scores 1.0, falling to 0 at 3 km).
5. **Weight and add.** Every factor shows its weight and a status badge — **validated**, **modelled**, **indicative** or **official** — so nothing is a black box.

### The Location Score (headline number) — eight pillars

| Pillar | Weight | Built from |
|---|---|---|
| Water & flood safety | 22% | the water-risk score below, inverted |
| Health-care access | 14% | nearest hospital, hospitals within 3 km, nearest 108 / government ambulance, clinics, hospital-road cut in a big storm |
| Schools & daily needs | 14% | nearest school (40%), market (35%), bank (25%) |
| Transit & main roads | 14% | nearest metro / rail, bus stop, distance to the nearest arterial / expressway |
| Jobs & lifestyle hubs | 10% | IT / office places within 5 km, malls and cinemas within 3 km |
| Parks & lakes | 9% | parks within 1 km, lake amenity distance |
| Air quality (live) | 9% | live US AQI from Open-Meteo |
| Fire & police reach | 8% | nearest fire station and police station |

Labels: **Excellent** ≥ 90 · **Good** ≥ 80 · **Fair** ≥ 70 · **Challenged** below.

### The water-risk score (inside the "Water & flood safety" pillar and the insurer tiers)

| Factor | Weight | Status |
|---|---|---|
| Flood-susceptibility rank of the ward (learned model) | 40% | validated |
| Modelled depth in a 192 mm storm (Oct-2020 size) | 18% | modelled |
| Lake / tank proximity | 12% | indicative |
| Low pocket vs surroundings | 10% | indicative |
| Mapped GHMC nala nearby | 8% | official |
| Upstream catchment draining through the ward | 6% | validated |
| Officially listed inundation area nearby | 6% | official |

Insurer lines (**Motor**, **Property**, **Health access**) re-weight these factors and add line-specific ones (underpasses and
traffic density for motor; fire-service reach and industrial land for property; ambulance and hospital reach for health), then map
the 0–100 score to a tier **A–E** with cut points calibrated on all 145 ward centroids. Loadings shown beside a tier are
**illustrative**, to be calibrated on an insurer's own claims.

---

## 3. Data sources (all free and public — no paid API is required to run it)

| Layer | Source | What we use it for |
|---|---|---|
| Places and facilities | OpenStreetMap + Overture Maps (merged, de-duplicated) | ~2,570 hospitals, ~4,400 schools, ~4,260 banks, ~1,570 markets, ~1,700 parks, ~320 police stations, malls, cinemas, IT / office hubs, main roads |
| Transit and police | TSRTC bus stops (~3,350 in range), HMRL metro stops, Hyderabad police stations (OpenCity, public domain) | transit and fire / police pillars |
| Drainage and tanks | Telangana State GIS (TGRAC public ArcGIS service) | 96 GHMC nalas / 1,162 segments with existing vs proposed width, ~3,965 drain and canal lines, 847 tank outlines, 23 official inundation areas |
| Tank encroachment | HYDRAA water-body assessment (TGRAC) | 1,192 water bodies classed Live / Partially / Totally encroached for 2014 and 2023 (a satellite classification, not a legal notice) |
| Lakes | HMDA notified-lake list | 2,980 lakes with notification dates; official FTL-map PDF links for the 27 Hyderabad-district lakes |
| Government health | Telangana health GIS | government hospitals, clinics, ambulance stations |
| Terrain and land cover | SRTM 30 m, ESA WorldCover | flood-susceptibility features (offline model) |
| Flood labels | 8 documented Hyderabad floods (2016–2026), 78 ward records with source URLs | model training and validation |
| Live weather | Open-Meteo | 7-day forecast, rain on any past date (claim check), elevation, air quality |
| Address search | Photon (OSM), a local index, optional TomTom, pasted Google Maps links | search box |
| Market rates | property-portal asking prices, compiled and cleaned into `web/data/rates.json` | 77 priced localities; 140 of 145 wards within 4 km of one |

Rates are **asking prices, not deal prices**, and ward coverage is partial (the old city and east have gaps because no defensible
apartment price was found; those cells are left empty, never invented).

---

## 4. Is it live or precomputed?

**Hybrid.** The heavy work is done once, offline; the per-address work is instant and runs in the browser.

* **Precomputed (JSON in `web/data/`)**: the flood model's ward rankings and depth per rainfall, ward features, the facility / lake / drain / tank datasets, the rate bands, ward Location Scores for the map colours.
* **Computed live in the browser, per address** (`engine.js`): locating the ward, all distances and counts, every factor curve, the weighted scores, tiers, flags and the calculators. No server is involved, which is why a report appears in about a second.
* **Live external calls**: Open-Meteo (forecast, rain on a past date, elevation, air quality) and the address-search services.
* **Server functions (`api/`)**: only configuration, health, and the optional TomTom suggestions; there is no database.

---

## 5. How accurate is it? (the honest version)

| Claim | Evidence | Status |
|---|---|---|
| The flood ranking of wards is better than chance | **Leave-one-event-out AUC 0.69** over 8 real floods (0.5 = coin flip, 1.0 = perfect); 0.67 among wards of similar size | validated |
| It agrees with an independent official list | **AUC 0.79** against GHMC's own list of chronically waterlogged wards, never used in training | validated |
| Our first version was wrong | It scored **0.49** (a coin flip) when graded on events it had not seen — the rebuild fixed this, and the numbers are shown inside the app | disclosed |
| Official inundation spots | 43% of GHMC's 23 listed spots fall in our top-quartile wards (25% would be chance) — modest, because many are underpasses a ward-level model cannot see | disclosed |
| Everything else (lake distance, terrain pocket, facility distances, fire reach, prices) | Indicators from open map data, not validated predictions. Facility data is unaudited against ground truth (the audit script exists but needs a Google key) | indicative |

**Resolution is the ward (145 wards), not the street or the plot.** Rain-to-depth is a stated assumption anchored to documented
flood extents, not a hydraulic simulation. The model under-ranks flooding caused by choked drains at street level, and says so.
It is a **screening and triage tool**, not a valuation, a survey, legal advice or an actuarial rate.

---

## 6. How it compares

| | Scope | Audience | Open / explainable | Hyderabad lake, nala, HYDRAA records |
|---|---|---|---|---|
| **SETHU** | address → 8-factor score + flood | buyers, agents, insurers (three reports) | open data; every factor shows weight and status | **yes** |
| First Street *Flood Factor* (US) | property-level flood risk, 1–10, 30-year outlook, hydrodynamic model | consumers via real-estate portals; B2B | proprietary model | n/a (US) |
| RMSI *India FloodRisk 2.0*, AIR flood maps | pincode-level flood hazard | insurers (paid catastrophe-model products) | closed | no |
| FTL / buffer checkers (e.g. Landeed) | is a survey number inside a lake buffer | buyers | closed | partial |
| Typical GitHub flood projects | rainfall → flood classifier notebook, or a dashboard | none | open | no |

SETHU is **not** the first flood-risk product in India and does not claim to be. What we have not found elsewhere is the
combination: one open, explainable engine that serves buyers, agents *and* insurers, adds the Hyderabad-specific lake / nala /
tank-encroachment records, scores flood as one factor among eight, and shows its own validation (including the version that
failed). First Street is the right mental model — *"Flood Factor, but for Hyderabad, open, and for three audiences"* — while
being clear that it uses a far heavier physical model than we do.

---

## 7. Business model, funding and scale

*Pricing and budget figures are proposals and estimates, not quotes or commitments.*

* **Customers** pay per report (proposed ₹299). **Agents** pay per client report (proposed ₹499). **Insurers, banks and proptech platforms** pay a platform fee plus per-query API charges, negotiated in a pilot. The demo takes no payment.
* **Marginal cost per report is close to zero** today because scoring runs in the browser on precomputed data.
* **To reach a first insurer pilot (~6 months) we estimate ₹5–8 lakh** with the team unpaid: hosting and commercial data plans ≈ ₹1–1.5 L, legal and compliance review ≈ ₹1–1.5 L, data validation / paid property datasets ≈ ₹1.5–2.5 L, pilot sales and travel ≈ ₹1 L, contingency ≈ ₹1 L. Likely routes: the Startup India Seed Fund Scheme (a grant of up to ₹20 lakh for proof of concept, paid through an incubator; needs a DPIIT-recognised company), T-Hub / T-Fund and the college incubation cell, then pilot revenue. DST NIDHI-PRAYAS funds physical prototypes only, so a software product is not eligible. Check current terms before applying.
* **What scaling needs:** (1) turn the static JSON into an API service (spatial database, caching, per-customer keys and rate limits, monitoring); (2) **commercial plans** for services that are free for non-commercial use today (weather API, hosting, address search); (3) written permission or licences for commercial use of government layers and attribution for OpenStreetMap / Overture data; (4) a finer-than-ward resolution (10 m terrain, parcel data); (5) for each new city, a terrain model, labelled floods and local official records.

---

## 8. Run it

```bash
python -m venv .venv && .venv/Scripts/activate      # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt
cp .env.example .env                                # every key is optional
python serve.py                                     # http://localhost:8000
```

Optional keys: `TOMTOM_API_KEY` (second address-search provider, free, no card). The Google Maps adapter is in the code but dormant. No key is needed for the reports.

```bash
node tests/engine.test.js            # ≈3,000 checks: data integrity, scoring invariants, golden locations,
                                     # and every ward × every report variant renders without errors
```

**Deploy:** pushing to `main` redeploys on Vercel (`web/` static + `api/` functions). Free Hobby hosting is for non-commercial use.

---

## 9. Repo map — where the working lives

```
web/platform/engine.js     THE BRAIN: locate, measure, factor curves, weights, tiers, flags, claim check, market lookup
web/platform/reports.js    the three one-page reports and the PDF detail
web/platform/app.js        search, routing, location card, ⓘ info cards, report tabs, print
web/platform/map.js        Leaflet map: Hyderabad-only, ward tint, lakes, layers
web/data/                  everything the browser reads (geo, gov, hydraa_tanks, hmda_lakes, rates, wardfeat, model …)
web/planner.html           the government Flood Planner (rainfall slider, Japanese flood-control methods)

research/train_final.py    trains the flood-susceptibility model and runs the held-out validation  → model_card.json
research/build_features.py terrain / land-cover features per ward   ·   research/labels.csv  the 8 real floods with sources
pipeline/p3…p7             rainfall → depth, hospital access, interventions, exports
pipeline/p8…p18            facilities, ward features, rates import, Telangana GIS, HMDA, HYDRAA, transit data
tests/engine.test.js       the test harness   ·   tests/golden.json   hand-checked locations
api/                       Vercel functions (config, health, TomTom suggestions)
PITCH.md                   the stage script, demo order and jury Q&A
```

## 10. Roadmap

Street-level resolution; an insurer pilot in shadow mode on closed claims; RERA project data and registered-deal prices; Chennai and
Mumbai (the flood problem is bigger there); a public API; the 2026 GHMC reorganisation (this version uses the earlier 145 wards).

## 11. Credits and licences

OpenStreetMap © OpenStreetMap contributors (ODbL) · Overture Maps · OpenCity datasets (public domain) · Telangana State GIS / TGRAC and
HMDA public services (shown as published, with source labels) · Open-Meteo (free for non-commercial use) · Esri imagery for the optional
satellite view · Inter font (SIL OFL).
