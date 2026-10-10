# SETU — Project status (aim · what was needed · what's done · what's pending)

_Last updated: 2026-10-10 (night before the final)._ Companion files: `PITCH.md` (script + Q&A), `docs/STATUS.md` (bug log).

## 1. The aim
Turn SETU from a hackathon flood planner into a **real, sellable product**: a location-intelligence
engine for Hyderabad that produces three separate, professional reports from one explainable engine:

| Report | For | Core promise |
|---|---|---|
| **Customer report** | families buying/renting | "Is it safe to buy here? What does it really cost?" |
| **Agent report** | real-estate professionals | "Evidence, market range and client-ready brief to price and negotiate." |
| **Insurer report** | underwriters & claims analysts | "Exposure tiers, claim evidence check, API-ready JSON." |

Built only on public/commercial-API data (no GHMC drain maps), honest about what is validated.

## 2. What was needed (gap analysis from the jury feedback + our own audit)
1. A product story beyond "flood detection": three customers, one engine. ✔ decided
2. Data that is **complete and correct** (facilities, lakes, rain, terrain). ◐ partly
3. A UI that looks and reads like a paid product (big type, separate full-page reports). ◐ in progress
4. Local market-rate context (asking-price ranges, total cost of buying). ◐ in progress
5. Verification: facts audited against ground truth; automated tests. ◐ in progress
6. Reliability for a live demo (fallbacks if any external service fails). ◐ in progress
7. Insurance beyond water (motor, property, health-access, fire reach). ◐ in progress
8. Real checkout, deploy, QR, updated pitch. ☐ pending

## 3. Done
* Flood-susceptibility engine (validated: AUC 0.69 held-out floods, 0.79 independent GHMC list).
* **Facility data (no Google needed):** OpenStreetMap merged with the Overture Maps open places dataset (Meta/Microsoft/Foursquare), de-duplicated — 2,554 hospitals · 1,965 clinics · 4,417 schools · 2,102 colleges · 4,262 banks · 1,573 markets · 1,700 parks · 176 transit · 15 fire · 231 police · 1,434 pharmacies, plus 464 water bodies incl. Hussain Sagar — `web/data/geo.json` (pipeline: p8 → p11 → p12). Fire stations remain sparse everywhere (about 15 mapped citywide).
* **Phase 0** — test harness (`node tests/engine.test.js`: 1,530 checks incl. every ward × every report variant rendered with no `undefined`/`NaN`), golden locations, tier calibration, bug log (`docs/STATUS.md`).
* **Phase 2** — new UI: Explore screen (full-bleed map + location card) and full-page Report screen; design system (Inter, 16px base, big numbers), SVG charts (risk gauge, depth-vs-rain curve, price band, rain timeline, forecast bars), mobile layout, print stylesheet, sticky tabs, shareable links.
* **Phase 3** — three separate reports: Customer (verdict, flags, rain curve, neighbourhood, lakes/terrain, true cost calculator, insurance angle, tailored checklist, AI in English/Telugu/Hindi), Agent (market band, price check vs comps, commission/deal economics, negotiation evidence, selling points, land character), Insurer (Motor / Property / Health-access tiers, factor tables, claim evidence check with rain chart, rain outlook, API-ready JSON, validation panel). Demo paywall (₹299 / ₹499 / enterprise).
* **Phase 4** — market-rate module: `web/data/rates.json` (18 localities, every band sourced with URL; asking prices, not transactions), total-cost calculator (≈6% Telangana duties, editable), Agent price check.
* **Phase 1 code** — `api/_google.py` + `/api/{config,health,places,suggest,place}`, `MapKit` (Google Maps with automatic Leaflet/OSM fallback, also on auth failure), facility merge (Google first, OSM backup, source badge on every report), address autocomplete. **Dormant until keys exist — untested against live Google.**
* **Location Score** (7 pillars: water & flood safety, health access, schools & daily needs, transit, parks & lakes, live air quality, fire & police reach) in all three reports; map can be coloured by flood rank or location score. SETU is positioned as a location-intelligence engine, not a flood model.
* **Rates for every place:** `docs/CHATGPT_RATES_PROMPTS.md` (master prompt + 6 ward batches + 59 extra localities) and `pipeline/p10_rates_import.py` (validates, flags outliers, matches by locality and ward, labels rows "AI-compiled estimate"). **Imported 10 Oct 2026:** `pipeline/p10a_clean_paste.py` repairs the pasted batches (escaped URLs, one-line records, missing/extra columns) → `data/rates_input.csv`; the importer then merged hand-curated and ChatGPT rows (18 places priced by both become one outer-limits band, flagged as disagreeing). Result: 77 priced localities; 48 of 145 wards have their own band, 119 wards sit within 2.5 km of a priced place and 140 within 4 km (5 outer wards get none). ChatGPT left ~104 rows empty on purpose (sparse portal data) — most of the old city and east wards. Guidance-value-only rows are kept but inert.
* **Official GHMC drainage records** (Telangana State GIS public service): 96 nalas, 1,162 segments (existing vs proposed width), 3,960 drains/canals, 847 tank outlines, 44 river/stream polygons, 23 official inundation areas -> `web/data/gov.json` (pipeline p14). Scored in water/motor/property risk, flagged in the buyer verdict, shown as map layers and an "Official drainage records" card. Nala-level encroachment fields are blank in the source, so they are NOT shown.
* **HYDRAA / TGRAC water-body assessment** (Telangana GIS, public): 1,192 tank polygons (590 named) classified Live / Partially / Totally Encroached for 2014 and 2023 (`web/data/hydraa_tanks.json`, p18). Shown on the map ("Tank encroachment"), flagged in buyer verdicts, listed in the drainage card. Satellite classification, not a legal notice. The layer mislabels some polygons (e.g. Hussain Sagar is labelled "Fox Sagar"), so the app prefers the OpenStreetMap name when both coincide and shows the government label alongside.
* **HMDA notified lakes**: 2,980 lakes with notification dates; verified official FTL-map PDF links for all 27 Hyderabad-district lakes (p15, p15b). Status shown only on unambiguous name (and area) matches.
* **Official transit / health points**: 4,041 TSRTC bus stops, 174 HMRL metro stops, 176 Hyderabad police stations, 116 government ambulance stations, government hospitals and Basti Dawakhanas (p17, p18) merged into the facility layer.
* **Roads & demand drivers** (Overture): ORR/expressway, national-highway and arterial distances; IT/office places, malls, cinemas -> Jobs & lifestyle pillar and "Trade routes & demand drivers" card (pipeline p13 -> p12).
* Grounded AI explainer (Groq) restricted to report data, per-lens prompts, offline fallback text.
* Facility audit script ready: `tests/audit_facilities.py` (needs the Places key).

## 4. Pending
| Item | Who | State |
|---|---|---|
| Run the ChatGPT rates prompts, put the CSV at `data/rates_input.csv`, run `p10_rates_import.py`, spot-check 3 areas | **user** | done 10 Oct — spot-check still open |
| Say "commit and deploy" → I commit, push, set Vercel env (`GROQ_API_KEY` only is required), check the live URL + QR | user OK needed | waiting |
| Optional: free TomTom key (no card) for better street-address search -> `TOMTOM_API_KEY` in `.env` / Vercel | user | optional |
| Optional: Razorpay test-mode checkout instead of the labelled demo button | needs test keys | optional |
| Final rehearsal of the 90-second pitch on the deployed site | both | last |

## 5. Honest limits (state them on stage)
* Flood ranking is ward-level and validated; lake distance, terrain pocket, facilities are **indicators**, not validated predictions.
* OpenStreetMap lake outlines are not legal FTL/buffer boundaries — verify with HMDA/Irrigation Dept.
* Himayat Sagar and ~30 smaller lakes are still missing from the lake layer.
* Market rates are **portal asking prices**, not transaction prices; agent commissions are not published — brokerage is a user input.
* Rain archive is a coarse grid (shows ~80–90 mm for the Oct-2020 night vs a 192 mm reference): an evidence tier, not an exact reading.
* Insurance loadings are illustrative, not actuarial rates.
* The 85% target is defined as: ≥85% of facility facts match Google in a 40-point audit; 100% of UI flows pass; price ranges cross-checked on ≥2 portals. It is **not** a claim about flood-prediction accuracy.

## 6. What the user must do
1. Create two Google API keys and put them in `.env` (`GOOGLE_MAPS_BROWSER_KEY`, `GOOGLE_PLACES_SERVER_KEY`).
2. Provide any local rates they trust (ChatGPT-sourced rates will be cross-checked before use).
3. Add the same env vars in Vercel before deploying.
