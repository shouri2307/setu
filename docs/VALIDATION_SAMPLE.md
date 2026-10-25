# Validation sample (24 Oct 2026)

What was actually checked, how, and what was only implemented. Reproduce with:
`node research/v6/engine_sample.js` then `.venv/Scripts/python research/v6/validate_batch2.py`, and `node tests/engine.test.js` (4,680 checks).

## 1. Independent recomputation at six places
The recomputation uses separate code (shapely + pyproj distances) and the **raw** source downloads (`research/gov_cache/tank_wb13.json`, `tank_stream14.json`, and the TSDPS CSVs read directly), not the processed `web/data` files.

| Place | Tanks within 2 km (app / raw) | Est. design capacity, million m³ (app / raw) | Nearest stream, m and order (app / raw) | Heavy days per monsoon, 2018–2024 (app / raw) |
|---|---|---|---|---|
| Hussain Sagar | 1 / 1 | 22.95 / 22.95 | 104, order 4 / 104, order 4 | 0/0 2/2 3/3 1/1 1/1 2/2 1/1 |
| Gachibowli | 17 / 17 | 0.43 / 0.43 | none within 500 m / none | 1/1 0/0 1/1 0/0 2/2 2/2 2/2 |
| Charminar | 3 / 3 | 0.02 / 0.02 | none / none | 1/1 1/1 3/3 2/2 0/0 1/1 1/1 |
| Saroornagar lake | 6 / 6 | 2.25 / 2.25 | 120, order 3 / 120, order 3 | 0/0 0/0 3/3 3/3 0/0 1/1 1/1 |
| Shamshabad edge | 7 / 7 | 0.52 / 0.52 | none / none | outside the 145 wards, not modelled |
| Medchal | 8 / 8 | 0.00 / 0.00 | none / none | outside the 145 wards, not modelled |

No mismatches (including all 28 yearly heavy-day counts). This confirms the calculations and the de-duplication; it does not confirm that the source data describe the ground correctly.

## 2. Source-data checks that changed the design
- Water-body layer 12 ("Totally Encroached") is an **exact duplicate** of layer 13 (same 2,050 records); only one is used. Two overlapping records were removed.
- Tank `Volume` equals `Area × Bund_Heigh / 2` in every one of the 751 records that have it, so it is a formula estimate; 1,298 of 2,048 tanks have no bund height and therefore **no capacity**. The report says so and never sums a missing value as zero.
- `Area_Total` is the same area in acres, not an original or pre-encroachment extent, so the report never claims storage was "lost".
- Rainfall: complete June–October seasons are now used (2018–2025 files). 6,831 out-of-month stray rows were dropped; 2018 lists several stations per mandal (averaged); a mandal-year counts only if every month has ≥90% of its days, which excludes 2025 everywhere (June 2025 file: 63%). The result, about 1.4 heavy days per monsoon, replaces the event-months-only figure (7–12) that was inflated by selecting flood months. Cross-check against the older file series: 4,104 shared mandal-days, 99.4% within 0.1 mm, max difference 5.3 mm, same heavy-day count (125 vs 125).
- Groundwater (batch 1): validated against the official report (Bahadurpura 1.16 m minimum matches exactly; Hyderabad-district June means 9.27/12.35 m against 9.96/12.43 m).

## 3. Behaviour checks (tests)
- Missing data: no tank or stream in range gives zero counts and no nearest, never a crash or an invented value.
- Duplicates: no tank record is counted twice; no two records share an outline and area.
- Coordinates: tank, stream and land polygons are [lat, lon] inside the study box.
- Rain: counts never exceed observed days; excluded months stay excluded; the Khairatabad wettest day (174.5 mm, 2020-10-14) matches the raw file.
- Analogs: exclude the month-only 2016 date and incomplete June 2025; the wording says "too few" exactly when fewer than 3 storms qualify and never states a probability.
- Checklist: every concern or watch finding with a template appears; "good" findings never do; transient gaps (elevation or routing still loading) never become action items; no alarmist wording; only the two portals we have actually reached or used are shown with a link.
- Map popups: all 8 popup kinds show source, data period, resolution and confidence, escape HTML, and say "not available" when capacity is missing.
- Routing: fails over to a second host, caches results, and returns null (report says unavailable) when both hosts fail.

## 4. Checked by hand in the running app
Groundwater popup (value, period, resolution, confidence, caveat shown; clicking a feature no longer drops a pin), evidence legend, checklist ticks persisted and counted, phone-width layout with no horizontal overflow, console free of errors from our data files.

## 5. Validation items finished on 24 Oct 2026
- **State GIS layer dates:** the server publishes only an ArcGIS document creation date per service (nalas 2025-04-16, water bodies and streams 2025-04-22, TCUR 2025-05-24, groundwater potential 2025-12-06, HYDRAA FTL tanks 2025-05-03, endowments 2026-07-28). Abstracts are placeholders and layer edit dates are not published, so the dates of the surveys behind the layers remain unknown. Accuracy is not published either.
- **Heat vs station temperatures: not validated.** Landsat composite per mandal vs mean station daily maximum air temperature on the same 15 scene dates: Spearman −0.09 (p = 0.66) over 27 mandals; satellite spread 3.4 °C, station spread 2.3 °C. Different quantities and a narrow station range make this a weak test, but the layer cannot be called validated, so it is shown with low confidence and says so.
- **Seismic zone:** secondary sources put Hyderabad in Zone II (IS 1893 Part 1:2016); a possible newer edition could not be confirmed. The report says "per secondary sources" and "a newer edition may change the zones".
- **Comparison feature:** symmetric (swapping A and B flips every verdict), self-comparison finds no differences, no winner/score/rank field exists, "unknown on one side" is labelled not comparable, and 24 ward pairs render without undefined/NaN or winner wording.

## 6. Implemented but NOT independently verified
- **Heat grid:** compared with station temperatures and found NOT to agree in ranking (section 5); low confidence.
- **Live routing times** are OSRM estimates with no traffic. The second host runs the same engine and data, so it is a failover, not an independent check. A Google Routes comparison was not run (needs a billed key and its terms restrict storing results).
- **Seismic zone** has not been checked against the BIS standard itself.
- **Official office processes** named in the checklist are mostly marked "not verified by SETU". Only the HMDA lakes portal (already used) and Bhu Bharati (reachable) carry links.
- **Groundwater potential, disappeared tanks, forest, endowment and transmission layers**: read correctly from the state GIS, but their dates and accuracy are not published.

## 7. Batch 4 (parcels, planning, water network, evidence quality), 24 Oct 2026
- **Tests:** 4,680 pass (433 new): registry integrity and enumerations; freshness rules; the engine cannot emit an unregistered finding; honesty invariants over 150 places (no high confidence on unvalidated or failed sources, 'unavailable' never rated, no-data never rated, scope present); **each optional data file removed in turn** (17 groups) with no dependent finding left rated and the source listed under 'why incomplete'; planning authority at 14 known places and overlap rate; about 40 synthetic parcel cases (ambiguous addresses, neighbouring parcels, sub-survey numbers, flagged numbers, overlapping outlines, near-edge pins, road features, no parcels, failed or missing data); 592 real parcels matched at an interior point with their own number and village (575 verified, 17 outside the old grid bound before a bug was found and fixed); old-city core honestly unavailable; every parcel tile equals the server count; overlap detection with injected footprints (over half, touching, 1% sliver, forest); prohibitory layer quoting and wording; network integrity, sections and wording.
- **Bugs found by this batch's own checks:** my first coverage scan stored failed requests as zero (flat zero everywhere); `SNo` misread as the survey number; non-unique `OBJECTID` merging distinct pipes (22% lost in one dense tile); the server's line count over-counting; parcel tile grid reaching past the study box so edge pins were called 'outside'; six findings reading reassuring when their data file was missing.
- **Independent recomputation:** water network at six places (see DATA_REGISTER section E).
- **Not validated:** parcel outline positional accuracy (unpublished), the prohibitory layer's legal meaning, authority-area boundary dates, network completeness outside the places checked.
