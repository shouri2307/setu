# SETU data-source and licensing register

Status: **working draft, 24 Oct 2026** (updated after the evidence-report build). Written from what the repo uses and what was verified by running the extraction.
This is a demo / research prototype. Restricted and unverified sources are included on purpose and are labelled; they must be cleared or replaced before any commercial release.
Not legal advice. "Verify" means the terms were not confirmed.

Source status labels: **VERIFIED** (we downloaded and inspected it) · **PARTIALLY VERIFIED** · **UNAVAILABLE** · **NEEDS PERMISSION**.
Licence status: **OK** (commercial use allowed with attribution) · **Restricted** · **Verify**.

## A. In the app today (data files in `web/data/`)

| Layer | Provider / extraction | Coverage and date | Verification | Licence | Notes |
|---|---|---|---|---|---|
| Roads, hospitals, schools, amenities | OpenStreetMap (Overpass), Overture Maps — `pipeline/p1,p11,p12` | study box, undated | VERIFIED | ODbL (OSM) · Overture varies by theme → **Verify** | attribution on the map |
| Basemap tiles | tile.openstreetmap.org · Esri World Imagery | — | VERIFIED | **Restricted** (demo only) | swap before real traffic |
| Geocoding | Photon (OSM), local index, TomTom | — | VERIFIED | Verify | |
| Live weather, air, elevation | Open-Meteo | live | VERIFIED | **Restricted** (free tier non-commercial) | |
| Nalas, drains, tanks, 23 inundation points | TGRAC ArcGIS `GHMCNalas_vul` — `p14` | 96 nalas, 1,162 segments; undated | VERIFIED + audited | Verify (OpenCity lists it public domain) | encroachment fields are blank (all 0) — not shown as data |
| Tank status 2014 vs 2023 | TGRAC / HYDRAA assessment — `p18` | 1,192 tanks | VERIFIED | Verify | satellite class, not legal |
| HMDA lake list | lakes.hmda.gov.in — `p15` | 2,980 lakes, no geometry, 55% lack final notification | VERIFIED | Verify | |
| Bus / metro / police | OpenCity datasets — `p17` | undated | PARTIALLY VERIFIED | Verify | |
| Terrain | SRTM | 30 m, integer metres | VERIFIED | OK | |
| Built-up share | ESA WorldCover 2021 | 10 m | VERIFIED | OK (CC BY 4.0) | |
| Land-price ranges | portal price-trend pages (Housing.com etc.) compiled with an AI assistant | 77 localities, Oct 2026 | PARTIALLY VERIFIED | **Verify, high risk** | indirect provenance |
| **Groundwater levels** | Telangana Ground Water Dept via Open Data Telangana — `p19`,`p20` → `groundwater.json` | monthly, Jan 2021–Jul 2026, 1,526 clean stations (115 in Hyderabad area) | VERIFIED + validated vs official report | Verify | see validation below |
| **Groundwater quality** | same source, pre/post-monsoon 2018–2025 — `p21` → `gwquality.json` | 10,668 samples 2021+; fluoride, nitrate, TDS, pH, aquifer | VERIFIED | Verify | |
| **Storm rainfall** | Open Data Telangana (TSDPS) mandal daily rainfall — `p23` → `stormhist.json` | 8 events, 27 mandals | VERIFIED (Oct 2020 city mean 211 mm matches the 192 mm reference) | **Restricted: NON-COMMERCIAL** | ask tsdps-plg@telangana.gov.in |
| **Surface heat / greenness** | Landsat 8/9 L2 via Microsoft Planetary Computer — `p25` → `heat.json` | 19 clear scenes Mar–May 2024–26, 150 m grid | physically consistent (lake 30 °C, park 38 °C, old city 43 °C) but **NOT validated**: across 27 mandals its ranking did not agree with weather-station air temperature (Spearman −0.09, p = 0.66; stations differ by only ~2 °C) | OK (USGS open) | surface not air temperature; reported with low confidence |
| **Landfills, power breakdowns, traffic choke points, junction plan, flood shelters, lake/STP quality, noise** | Lakeer open-GIS repo (Telangana / GHMC / TSPCB sources) — `p22` → `civic.json` | power FY2017-18 only; quality 2017; noise 2018; others undated | VERIFIED | Verify per dataset | dated layers are labelled "dated" and mostly unscored |
| **Groundwater potential, disappeared tanks, forest boundary, HT lines, substations, endowment properties** | TGRAC ArcGIS (several folders) — `p26` → `land.json` | study box, undated | VERIFIED by point queries | Verify | owner/personal layers deliberately NOT used |
| **Tank capacity records and stream order** | TGRAC `HMDA_ORR_GHMC_Water_Bodies` layers 13 and 14 — `p27` → `tanks.json` | 2,048 de-duplicated tank records (capacity for 750), 1,355 stream segments, orders 2–6; undated, status classes 2011 and 2023 | VERIFIED + independently recomputed at 6 places | Verify | layer 12 is an exact duplicate of 13 and is ignored; capacity is the source's area×bund/2 estimate |
| **Heavy-rain statistics** | Open Data Telangana (TSDPS) daily weather files, June–October 2018–2025 (`p29` fetch) — `p28` → `rainstats.json` | 27 mandals, 5–7 complete monsoons each (2018–2024; 2025 is excluded because the June 2025 file has only 63% of its days) | VERIFIED: recomputed independently at 4 places (28 yearly counts); matches the older files on 4,104 shared mandal-days (99.4% within 0.1 mm, 125 vs 125 heavy days) | **Restricted: NON-COMMERCIAL** | about 1.4 heavy days (>64.5 mm) per monsoon; 2018 lists several stations per mandal (averaged); 6,831 out-of-month stray rows dropped |
| **Survey-parcel outlines** | TGRAC `Bhunaksha_Cadastral` layer 0 'Cadastral 2.5m' — `p31` → `web/data/parcels/*.json` (145 lazy tiles of 0.03°) | 47,249 parcel records (42,980 unique, 216 villages); service document created 2025-04-19; survey date and accuracy not published | VERIFIED: every tile holds exactly the parcels the server counts; matcher tested on 592 real parcels and on synthetic neighbours, overlaps, flagged numbers and gaps | Verify | `SNo` is a village serial, NOT a survey number (`Parcel_num` is); only filled `Parcel_num` polygons kept; old city core has only a placeholder; outlines are survey numbers (median 0.77 ha), not house plots; owner fields never requested |
| **Prohibitory-category parcels** | TGRAC `Bhunaksha` layer 0 'ULB_Cadastral_Prohibited' — `p31` → `web/data/prohib.json` | 656 parcels in the box; service created 2025-04-19 | PARTIALLY VERIFIED: all 656 join onto the cadastral parcels by village and number; legal basis and date undocumented | Verify | quoted as recorded and never as the legal prohibited-property register |
| **Planning-authority areas** | TGRAC `HMDA` layers 0 and 2 — `p30` → `web/data/plan.json` | six areas (MCH, HUDA, CDA, HADA, HMR, HMR growth corridor), 51 mandal polygons; service created 2025-04-17; ~22 m simplification | VERIFIED at 14 known places; specific areas overlap at boundary slivers only (0.8% of grid points) | Verify | says which plan governs, NOT what a plot is zoned for; undated; HMDA jurisdiction reportedly widened in 2025 |
| **HMWSSB mapped network** | TGRAC `TCUR` layers 32 (supply), 39 (core-city sewer), 36 (sections) — `p32` → `web/data/network.json` (~100 m cells, 944 KB) | 215,506 supply and 90,298 sewer segments in the box (214,808 / 90,298 in use); 110 sections; service created 2025-05-24 | VERIFIED: independent recomputation at six places agrees within about 4% per window, diameters differ in 2 of 82 cells | Verify | a mapped pipe is not a connection; no mapped pipe is not 'no supply'; sewer is core city only; pipe geometry not redistributed; `ENABLED` flag and 1900-01-01 abandon dates ignored |
| **Road routing** | OSRM public servers on OpenStreetMap roads (live, per report, two hosts with failover, cached) | live | VERIFIED | **Restricted** (demo servers) | the offline grid builder `p24a/p24b` is optional and unfinished because public map servers time out |

## B. Verified but NOT integrated

| Source | Finding | Status |
|---|---|---|
| TGRAC `Bhunaksha_Cadastral` layer 0 | **now integrated** (section A). The earlier note 'none inside core GHMC' was wrong: survey parcels cover the former HUDA / CDA / HADA wards; the gap is the old MCH core (only a placeholder polygon). The `30cm` layer, `DLS` base cadastral and `HMDA` cadastral / pocket layers returned nothing in the box and are not used | VERIFIED |
| TGRAC DLS `Dharani_Database`, `Owners_Info_*` | contain owner personal data | **not used, by design** |
| TGRAC `SRO` (Circle, Buildings with Price 40,589 polygons, Road Type) | no hits at 8 test points; service created 2025-07-31; coverage unclear | PARTIALLY VERIFIED |
| OpenCity 'core city sewer lines' and HMWSSB water-connection CSVs | listed by search results only (sewer GeoJSON public domain, PM Gati Shakti source; connections are monthly applied / approved tables, not spatial); not opened | LEAD |
| Telangana prohibited-property (Section 22-A) register | reported by secondary sources to have no single downloadable file, to have contained many wrongly listed parcels and to be under revision; not reached | CANNOT BE VERIFIED |
| TGRAC layer dates | each service's metadata `CreaDate` (when the ArcGIS map document was created): nalas 2025-04-16, water bodies and stream order 2025-04-22, TCUR (forest, transmission, substations) 2025-05-24, groundwater potential 2025-12-06, HYDRAA FTL tanks 2025-05-03, endowment lands 2026-07-28. Abstract and purpose fields are placeholders ("test", "aa") and layer edit dates are not published, so the date of the underlying survey is **unknown** | VERIFIED |
| TGRAC `Pollution_Category_Boundaries`, `Soil_Atlas`, `Mines_Geology_Layer` | reachable; pollution zones sparse, soil atlas only Khammam, geology duplicates the groundwater-potential layer and is slow | VERIFIED, low value now |
| TGSRTC / HMRL / MMTS GTFS | the Open Data Telangana entries hold only terms-and-conditions documents; feeds need an application | **NEEDS PERMISSION** |
| HMDA master plans | hmda.gov.in is reachable (it did not respond at the first probe, so availability is intermittent). Official plans exist as **static documents**: Master Plan 2031 as about 30 mandal JPEG sheets (23-29 MB, 2021), the Revised Development Plan of the erstwhile MCH area as 7 circle PDFs (~29 MB, 2022), a zoning-regulations PDF; HUDA / HADA / CDA plans are listed but were not opened. Not georeferenced; no vector layer found. Only HEAD requests were made (nothing downloaded) | CONFIRMED to exist; NOT machine-readable |
| Bhu Bharati portal | reachable (HTML); no bulk parcel API confirmed | PARTIALLY VERIFIED |
| Telangana weather stations (NWDP hourly) | 38 river-basin stations, none in Hyderabad, junk values | UNAVAILABLE for this use |
| IMD gridded rainfall 0.25° | downloadable (POST form); smooths cloudbursts | VERIFIED, superseded by mandal data |
| NRSC/Bhuvan Oct 2020 flood maps | 9 annotated PDFs, qualitative only | VERIFIED |
| Sentinel-1 radar | open and reachable; Khammam Sept 2024 flood mask works as a probe, Hyderabad passes miss the 2020 peak | VERIFIED (research only) |
| OSM full road network by Overpass | public servers time out on city-wide queries | UNAVAILABLE at scale |

## C. Competitors' databases
Not scraped or reused. Used only to discover what exists; originals are fetched from authorised sources.

## D. Before a paid customer
1. Replace or license: Open-Meteo, OSRM demo server, the price data, OSM/Esri tiles.
2. Written permission for TSDPS rainfall; confirm terms for TGRAC/HMDA/HYDRAA layers and the Ground Water Dept files.
3. Add attribution text to every report and the map footer.
4. Re-read this register and re-mark every "Verify".

## E. Validation notes (what was checked, and what was found)
- **Groundwater levels:** the source files had swapped latitude/longitude in 27,366 rows, two date formats, ~3,750 rows without coordinates and placeholder coordinates shared by 575 stations. After cleaning: the shallowest April-2025 reading (Bahadurpura, **1.16 m**) matches the Telangana Ground Water Department's reported minimum exactly; Hyderabad-district June means are 9.27 m (2025) and 12.35 m (2026) against the official 9.96 m and 12.43 m; our statewide March-2025 mean (10.63 m over 1,344 cleaned stations) is 0.7 m deeper than the official 9.91 m (all 1,771 stations), because dropping suspect-position stations biases slightly deep. Nearby wells disagree strongly (median 5 m within 1.5 km), so the report only gives an area estimate with at least 3 agreeing wells.
- **Heat:** physically consistent (open water 30 °C, KBR park 38 °C and greenest, dense old city 43 °C and 85th percentile).
- **Storm rainfall:** the 14 Oct 2020 mandal readings average 211 mm over the storm window, matching the 192 mm reference; the previous Open-Meteo archive showed only 80–90 mm.
- **Heavy-rain statistics:** the older event-month counts (7–12 heavy days) were inflated by selecting flood months; the complete-monsoon figure is about 1.4 a year. The two TSDPS file series agree on 4,104 shared mandal-days (correlation 1.0000, 99.4% within 0.1 mm, same 125 heavy days). The 2025 monsoon is not in the counts (June 2025 file incomplete), so the recent big storms are missing from them.
- **Heat (negative result):** the Landsat composite ranks the old city (Charminar, Bahadurpura) hottest, which is physically plausible, but the 27-mandal rank correlation with station air temperature on the same 15 scene dates is −0.09, so it is reported as unvalidated, low confidence.
- **State GIS layer dates:** only the ArcGIS document creation date is published (2025–2026); the survey dates of the underlying data are not.
- **Seismic zone:** secondary sources list Hyderabad in Zone II of IS 1893 (Part 1):2016; a possible newer edition could not be confirmed. The report says so and asks the reader to verify.
- **Parcel layer:** `SNo` is a village serial, not a survey number; `Parcel_num` is. Blank-`Parcel_num` polygons are village placeholders or the old-city placeholder and are never matched. About 1% of numbers are flagged duplicate or unreadable at source and can never produce a 'verified' match.
- **Line layers:** `OBJECTID` is not unique (404 distinct values over 481 lines in one box); the real key is `OBJECTID_12`. `returnCountOnly` over-counts lines, so completeness is checked geometrically. Polygon tiles are checked against the server count exactly.
- **Water network:** independent recomputation (exact shapely clipping against each cell, raw unsimplified geometry) at six places: 82 cells compared, window totals within about 4%, worst single cell 59 m, diameter mismatches 2 of 82.
- **Missing-data safety:** each optional data file was removed in turn; six findings (`nala`, `inund`, `lost`, `choke`, `landfill`, `f_jobs`) used to read good or concern when their data was absent and now read 'data not loaded'.
