# SETHU platform — build status & bug log

> Phase table below is the original plan. Current state (10 Oct 2026): phases 0, 2, 3, 4 done; phase 1 (Google) replaced by free OSM + Overture + Telangana GIS data; phase 5 partly done (3,001 automated checks, print verified); phase 6 deployed to Vercel, live-site check pending Deployment Protection being switched off. See PROJECT_STATUS.md.

## Phases
| # | Phase | State |
|---|---|---|
| 0 | Triage: data completion, test harness, golden locations, calibration, bug log | **done** — 1,529 checks pass |
| 1 | Real data: Google Maps/Places/Geocoding, OSM fallback | not started — needs keys |
| 2 | UI rebuild: Explore screen + full-page Report screen, design system, charts | not started |
| 3 | Three reports: Customer / Agent / Insurer (+ API tab, Telugu/Hindi) | not started |
| 4 | Market-rate module: curated rate table, comps tool, total-cost calculator | not started |
| 5 | Verification: 40-point facility audit, ward-lookup check, price cross-check, E2E | not started |
| 6 | Hardening & launch: fallbacks, test-mode checkout, deploy, pitch update | not started |

## Test harness
`node tests/engine.test.js [--net] [--dist]` — data integrity, geometry, scoring invariants, golden
locations (`tests/golden.json`), claim-check logic; `--net` hits live APIs; `--dist` prints tier distribution.

## Bugs found and fixed in Phase 0
1. Multipolygon lakes (Hussain Sagar, Himayat Sagar…) came back from OpenStreetMap as bounding boxes only → the lake layer was missing them. Geometry is now fetched by relation id and outer ways are stitched into closed rings. *(harness caught it: golden "Hussain Sagar" failed)*
2. Swimming pools, sewers and fountains were counted as lakes/ponds → excluded.
3. Multi-ring water bodies were measured with only their first ring → area, inside-test and distance now use all rings.
4. Tier cut-points were uncalibrated → set per score from the distribution over all 145 ward centroids.
5. Map zoom buttons overlapped the layer chips → moved.
6. A quote-escaping slip in the claim caveat broke the engine file → fixed and syntax-checked.

7. Lake outlines for multipolygon relations now come from Nominatim (Overpass kept timing out): 18 of 50 recovered, including Hussain Sagar, Umda Sagar. **Still missing:** Himayat Sagar and ~30 smaller relations → Google satellite view in P1 covers the visual gap; lake distances for those are unavailable until then.

## Known open issues (owner phase)
* OpenStreetMap coverage is thin in places: 581 schools, 8 fire stations, 109 transit stops, 88 police stations → **P1** (Google Places + audit in **P5**).
* Facilities score is therefore optimistic; do not present as fact until P1.
* UI: single cramped sidebar, small type, three lenses squeezed into it → **P2/P3**.
* No market-rate data; price tool relies on user-entered numbers → **P4**.
* URL hash does not update when the lens changes → P2.
* No fallback state if the geocoder is slow/offline beyond a toast → P6.
* Print layout, mobile layout and AI under load untested → P2/P5/P6.
