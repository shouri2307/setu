# SETU evidence matrix

Generated from `web/data/quality.json` by `research/v7/gen_matrix.js`; ages computed for 2026-10-24. **Do not edit by hand**: edit the registry, regenerate, and run the tests (they fail if the engine emits a finding the registry does not list).

The same data drives the internal dashboard at `web/quality.html`. Survey / observation dates are kept apart from the date a GIS service document was created (the second says when a map was published, not when the ground was surveyed).

## Summary

75 findings, 36 sources.

| Flag | Findings |
|---|---|
| Stale (older than allowed for this kind of data) | 4 |
| Undated (no observation date published) | 41 |
| Unvalidated (not checked against anything independent) | 42 |
| Failed validation | 1 |
| Licence: demo / non-commercial only | 10 |
| Licence unverified | 66 |
| No data (reported as unknown) | 3 |
| Coarse scope (ward, mandal, locality or city-wide) | 7 |

## Sources

| Source | Provider | Observation period | Map service created | Fetched | Resolution | Coverage | Freshness | Validation | Licence | Findings |
|---|---|---|---|---|---|---|---|---|---|---|
| SETHU ward flood model | this project (terrain, drainage and land-cover features; labels from news-named flooded wards) | 2016-09 to 2026-06 | — | 2026-09-22 | 145 GHMC wards | the 145 GHMC wards only; not applied outside | model | validated: tested on floods it never saw (leave-one-event-out) AUC about 0.69: better than chance, modest; labels cap what any model can reach | verify: labels come from news reports; input datasets' terms not all confirmed | 3 |
| Storm rainfall by mandal (8 documented floods) | Open Data Telangana (TSDPS) daily mandal rainfall | 2020-10 to 2026-06 | — | 2026-10-24 | mandal | 27 mandals around Hyderabad | historical | validated: 14 Oct 2020 mandal readings average 211 mm against the 192 mm reference | restricted: non-commercial; written permission needed (tsdps-plg@telangana.gov.in) | 2 |
| Heavy-rain days per monsoon | Open Data Telangana (TSDPS) daily weather files, June-October 2018-2025 | 2018-06 to 2024-10 | — | 2026-10-24 | mandal | 27 mandals, 5-7 complete monsoons each (2025 excluded: incomplete file) | historical | validated: recomputed independently at 4 places (28 yearly counts, no mismatch); agrees with the older file series on 4,104 shared mandal-days | restricted: non-commercial; written permission needed | 1 |
| Roads, hospitals, schools, shops and other places | OpenStreetMap (Overpass) merged with Overture Maps places | not published | — | 2026-09-22 | point / line | study box; completeness varies by neighbourhood | undated | unvalidated: nothing checks that a mapped hospital or school still operates or offers the service named | verify: OSM is ODbL (attribution and share-alike); Overture terms vary by theme | 16 |
| Bus stops, metro stations, police stations | OpenCity / Telangana open data (TSRTC, HMRL GTFS stops, Hyderabad police) | not published | — | 2026-10-10 | point | Hyderabad | undated | unvalidated: stop locations only; no timetable, frequency or service check | verify: listed as public domain by OpenCity; original terms not confirmed | 5 |
| 108 ambulance stations and health facilities | Telangana State GIS health layers (TGRAC) | not published | — | 2026-10-10 | point | Hyderabad area | undated | unvalidated: locations not checked on the ground | verify: terms not confirmed | 1 |
| 90 m elevation around the pin | Open-Meteo elevation API | not published | — | live | 90 m | global | live | unvalidated: coarse; integer-metre terrain model | restricted: free tier is non-commercial; needs a paid plan or another source before real traffic | 1 |
| Air quality now | Open-Meteo air-quality API | not published | — | live | model grid (about 11 km) | global | live | not-applicable: a modelled snapshot of the current hour, not a measurement at the pin | restricted: free tier is non-commercial | 1 |
| Road travel time and distance | OSRM public demo servers on OpenStreetMap roads (two hosts, failover) | not published | — | live | road network | global | live | unvalidated: the second host runs the same engine and data, so it is a failover, not an independent check; no Google comparison was run | restricted: public demo servers; not for production traffic | 5 |
| GHMC nalas, drains and listed inundation points | Telangana State GIS (TGRAC) GHMC Nalas and Vulnerability map | not published | 2025-04-16 | 2026-10-10 | line segment / point | 96 nalas, 1,162 segments, 23 inundation points | undated | internal-check: audited for blanks and duplicates; encroachment fields are all zero in the source and are not shown as data | verify: OpenCity lists it public domain; original terms not confirmed | 4 |
| Tank status 2014 vs 2023 | TGRAC / HYDRAA water-body assessment | 2014 to 2023 | 2025-05-03 | 2026-10-10 | tank polygon | 1,192 tanks | aging | internal-check: satellite class (live / encroached), not a legal finding | verify: terms not confirmed | 2 |
| HMDA lake list and FTL notification status | HMDA lakes information portal (lakes.hmda.gov.in) | not published | — | 2026-10-10 | lake (no geometry) | 2,980 lakes; 55% lack a final notification | undated | internal-check: matched to tank outlines by name, which can mis-match | verify: terms not confirmed | 1 |
| Tank capacity records and stream order | TGRAC HMDA_ORR_GHMC_Water_Bodies layers 13 and 14 | 2011 to 2023 | 2025-04-22 | 2026-10-24 | tank polygon / stream line | 2,048 de-duplicated tank records (capacity for 750), 1,355 stream segments | aging | internal-check: recomputed independently from the raw download at six places with no mismatch; capacity is the source's area x bund / 2 estimate and is missing for 63% of tanks | verify: terms not confirmed | 5 |
| Groundwater potential map | TGRAC Groundwater_Potential | not published | 2025-12-06 | 2026-10-24 | mapped unit (regional) | 1,979 units in the study box | undated | unvalidated: read correctly from the service; accuracy and survey date not published | verify: terms not confirmed | 1 |
| Disappeared water bodies | TGRAC 'Water Bodies - Disappeared' layer | not published | 2025-04-22 | 2026-10-24 | polygon | study box | undated | unvalidated: read correctly; accuracy and survey date not published | verify: terms not confirmed | 2 |
| Forest boundary, high-voltage lines and substations | TGRAC TCUR (Telangana Core Urban Region) | not published | 2025-05-24 | 2026-10-24 | polygon / line / point | study box | undated | unvalidated: read correctly; accuracy and survey date not published | verify: terms not confirmed | 4 |
| Endowment properties | TGRAC Endowment Lands 2026 | not published | 2026-07-28 | 2026-10-24 | point (location approximate) | Hyderabad | undated | unvalidated: points, not boundaries | verify: terms not confirmed | 1 |
| Groundwater levels | Telangana Ground Water Department via Open Data Telangana | 2021-01 to 2026-07 | — | 2026-10-24 | monitoring well (point) | 1,526 clean stations statewide, 115 in the Hyderabad area | current | validated: Bahadurpura April-2025 minimum matches the official report exactly; Hyderabad June means within 0.7 m of official; wells 1.5 km apart differ by metres | verify: terms not confirmed | 7 |
| Groundwater quality samples | Telangana Ground Water Department via Open Data Telangana | 2018 to 2025 | — | 2026-10-24 | sample point | 10,668 samples 2021+ (pre- and post-monsoon) | current | internal-check: downloaded and parsed; not compared with an independent laboratory source | verify: terms not confirmed | 5 |
| Landfills and dump yards | Lakeer open-GIS repository (Telangana / GHMC sources) | not published | — | 2026-10-24 | polygon | 11 sites | undated | unvalidated: not checked against GHMC | verify: terms of each original dataset not confirmed | 1 |
| Power breakdown history | Lakeer open-GIS repository (utility log) | 2017-04 to 2018-03 | — | 2026-10-24 | grid cell | FY2017-18 only | stale | unvalidated: dated and shown unscored | verify: terms not confirmed | 1 |
| Traffic choke points and planned junction improvements | Lakeer open-GIS repository (Hyderabad Traffic Police, GHMC) | not published | — | 2026-10-24 | point | short lists | undated | unvalidated: not checked | verify: terms not confirmed | 2 |
| Flood rehabilitation centres | Lakeer open-GIS repository (GHMC list) | not published | — | 2026-10-24 | point | 101 listed localities | undated | unvalidated: not checked | verify: terms not confirmed | 1 |
| Lake, river and STP water quality | Lakeer open-GIS repository (TSPCB 2017) | 2017-01 to 2017-12 | — | 2026-10-24 | monitoring station | sparse stations | stale | unvalidated: dated and shown as such | verify: terms not confirmed | 2 |
| Noise monitors | Lakeer open-GIS repository (TSPCB 2018) | 2018-01 to 2018-12 | — | 2026-10-24 | monitoring station | 10 monitors | stale | unvalidated: dated and shown as such | verify: terms not confirmed | 1 |
| Surface heat in the dry season | Landsat 8/9 Level-2 (USGS) via Microsoft Planetary Computer | 2024-03 to 2026-05 | — | 2026-10-24 | 150 m grid | study box | current | negative: across 27 mandals the ranking did not agree with station air temperature (Spearman -0.09, p = 0.66; stations differ by only about 2 C, so the test is weak) | ok: USGS open data | 1 |
| Dry-season greenness (NDVI) | Landsat 8/9 Level-2 (USGS) via Microsoft Planetary Computer | 2024-03 to 2026-05 | — | 2026-10-24 | 150 m grid | study box | current | internal-check: physically consistent (park greenest, old city least) but not compared with an independent vegetation product | ok: USGS open data | 1 |
| Earthquake zone | secondary sources citing IS 1893 (Part 1):2016 | not published | — | — | city | Hyderabad | reference | unvalidated: not checked against the BIS standard itself; a newer edition may change zones. The state GIS seismic layer (separate finding) puts the whole study box in Zone II, which agrees, but its own zoning edition is not published | ok: a published fact | 1 |
| Asking-price ranges | property-portal price-trend pages compiled with an AI assistant | 2025 to 2026-10 | — | 2026-10-10 | locality | 77 localities | current | unvalidated: portal figures disagree widely; asking prices, not registered deals | verify: high risk: portal data, indirect provenance; needs a licensed source before commercial use | 1 |
| Planning-authority areas (which plan governs) | TGRAC HMDA layers (MCH, HUDA, CDA, HADA, HMR, HMR growth corridor) and mandal boundaries | not published | 2025-04-17 | 2026-10-24 | authority-area polygon (simplified ~22 m) | HMDA region | reference | internal-check: checked at 14 known places (Gachibowli and Kondapur in CDA, Kukatpally and Uppal in HUDA, Shamshabad in HADA, Charminar and Banjara Hills in MCH) | verify: terms not confirmed | 1 |
| Published master plans (documents) | HMDA: Revised Development Plan (circle PDFs), Master Plan 2031 mandal sheets, HUDA / HADA / CDA plans | 2021 to 2022 | — | 2026-10-24 | static PDF / JPEG sheets | 7 core circles, about 30 mandal sheets | documents | not-applicable: file dates are upload dates (2021-2022), not plan dates; sheets are 23-29 MB images, not georeferenced | verify: public HMDA website; reuse terms not confirmed | 2 |
| Survey-parcel outlines | TGRAC Bhunaksha cadastral layer 'Cadastral 2.5m' | not published | 2025-04-19 | 2026-10-24 | parcel polygon (about 1 m after simplification) | survey parcels across most of the study box; the old MCH core is mostly a single placeholder polygon | undated | unvalidated: SNo is a village serial, not a survey number; about 1% of numbers are flagged duplicate or unreadable at source; accuracy and survey date not published | verify: terms not confirmed; owner fields never requested | 3 |
| Parcels carrying a prohibitory-land category | TGRAC Bhunaksha layer 'ULB_Cadastral_Prohibited' | not published | 2025-04-19 | 2026-10-24 | parcel polygon | 812 parcels in the study box, mostly outside the old city | undated | unvalidated: legal basis, date and completeness not documented; the official prohibited-property list is reported to have contained many wrongly listed parcels | verify: terms not confirmed | 1 |
| HMWSSB mapped water-supply pipes and sewer lines; service sections | TGRAC TCUR service (HMWSSB network layers) | not published | 2025-05-24 | 2026-10-24 | 100 m cells (derived); section polygons | supply pipes across most of the city; sewer lines only for the 'core city' | undated | unvalidated: mapping completeness is uneven (900 m boxes hold from 0 to over 700 pipe segments); a pipe on the map is not a connection | verify: terms not confirmed; pipe geometry is not redistributed, only coarse cell presence | 2 |
| State fire-station list | Telangana State GIS (TGRAC) TCUR layer 61 'Fire Stations' | not published | 2025-05-24 | 2026-10-25 | point (positional accuracy not published) | 71 records for the Hyderabad metro districts: 32 Existing and 39 Proposed | undated | unvalidated: compared with OpenStreetMap at 10 places: the nearest Existing station matched at 4; OSM maps only 10 stations in the area so it cannot confirm the rest; 6 of the 8 OSM stations inside the study box sit on a listed station, 2 do not; the source's remarks (Moved, not found accurate) did not separate matching from non-matching stations | verify: no licence text is published for this service | 1 |
| State seismic-zone layer | Telangana State GIS (TGRAC) TCUR layer 90 'Sesismic Zones' | not published | 2025-05-24 | 2026-10-25 | regional zone polygon (~50 m simplification) | 3 polygons: Zone II (two areas) and Zone III. The whole Hyderabad map region (17.20-17.66 N, 78.18-78.70 E, 2,392 grid points) is Zone II; the nearest Zone III boundary is at least 102 km away | undated | internal-check: agrees with the Zone II reference at all 2,392 grid points of the map region and at the 14 test places; the edition of the zoning behind the layer is not published and neither source is the BIS standard itself | verify: no licence text is published for this service | 1 |

## Findings

Scope says what a result applies to: the pin position, the matched parcel outline, features near the pin, an area estimate, the whole ward / mandal / city, live data, or nothing.

| Finding | Section | Applies to | Sources | Flags | Why it can be unknown |
|---|---|---|---|---|---|
| Flood susceptibility (SETHU model) (`sus`) | hazards | ward: the whole ward, not the street | SETHU ward flood model | licence-unverified, coarse-scope | outside the 145 GHMC wards the model is not applied |
| Modelled water depth in a 192 mm storm (`depth`) | hazards | ward: the whole ward, a stated-rain scenario | SETHU ward flood model | licence-unverified, coarse-scope | outside the 145 GHMC wards the model is not applied |
| What this ward's mandal recorded in 8 documented floods (`storms`) | hazards | ward: the ward's mandal in 8 documented floods | Storm rainfall by mandal (8 documented floods); SETHU ward flood model | restricted-licence, licence-unverified, coarse-scope | mandal not among the 27 with rainfall data |
| Heavy-rain days per monsoon in this mandal (`heavyrain`) | hazards | mandal: the whole mandal | Heavy-rain days per monsoon | restricted-licence, coarse-scope | mandal not among the 27 with complete monsoon seasons |
| Storm analogs (preliminary historical association) (`analog`) | hazards | ward: the ward's mandal, six dated storms | Storm rainfall by mandal (8 documented floods) | restricted-licence, coarse-scope | fewer than 3 qualifying storms or mandal not covered |
| Low pocket vs surroundings (`pocket`) | hazards | nearby: about 1 km around the pin, 90 m terrain | 90 m elevation around the pin | unvalidated, restricted-licence | the elevation service did not answer |
| Lake / tank proximity (`lake`) | hazards | nearby: lakes and tanks near the pin; the outline is not the legal boundary | Roads, hospitals, schools, shops and other places; Tank capacity records and stream order | undated, unvalidated, licence-unverified | — |
| Mapped nala nearby (`nala`) | hazards | nearby: nalas within a stated distance | GHMC nalas, drains and listed inundation points | undated, licence-unverified | — |
| Recorded encroachment on this nala (`nalaenc`) | hazards | nearby: the nearest mapped nala | GHMC nalas, drains and listed inundation points | undated, licence-unverified | encroachment fields are blank in the source |
| Natural stream channel nearby (`stream`) | hazards | nearby: natural streams within 500 m | Tank capacity records and stream order | licence-unverified | — |
| Officially listed inundation area (`inund`) | hazards | nearby: 23 officially listed points only | GHMC nalas, drains and listed inundation points | undated, licence-unverified | — |
| Nearest tank: 2014 vs 2023 satellite status (`hy`) | hazards | nearby: the nearest assessed tank | Tank status 2014 vs 2023 | licence-unverified | — |
| HMDA lake notification (`hmda`) | hazards | nearby: the nearest tank matched by name | HMDA lake list and FTL notification status; Tank status 2014 vs 2023 | undated, licence-unverified | no name match |
| Surface heat in the dry season (`heat`) | hazards | nearby: the 150 m cell around the pin | Surface heat in the dry season | failed-validation | pin outside the heat grid or no clear scene |
| Vegetation cover (dry-season greenness) (`green`) | hazards | nearby: the 150 m cell around the pin | Dry-season greenness (NDVI) | — | pin outside the grid |
| Earthquake zone (`seismic`) | hazards | region: the whole city | Earthquake zone | unvalidated, coarse-scope | — |
| Flood rehabilitation centres nearby (`shelter`) | hazards | nearby: listed centres within a stated distance | Flood rehabilitation centres | undated, unvalidated, licence-unverified | — |
| Groundwater depth (`gw`) | water | area: nearby wells | Groundwater levels | licence-unverified | no monitoring wells loaded |
| Nearest monitoring well (observed) (`gwnear`) | water | nearby: one monitoring well | Groundwater levels | licence-unverified | — |
| Groundwater depth around here (median of nearby wells) (`gwdepth`) | water | area: median of at least 3 agreeing wells within 3 km | Groundwater levels | licence-unverified | fewer than 3 wells nearby, or the wells disagree |
| Depth at the end of the dry season (Apr–May) (`gwpre`) | water | area: median of nearby wells | Groundwater levels | licence-unverified | fewer than 3 wells nearby |
| Rebound after the monsoon (`gwrec`) | water | area: median of nearby wells | Groundwater levels | licence-unverified | fewer than 3 wells nearby |
| Multi-year trend (`gwtrend`) | water | area: median trend of nearby wells | Groundwater levels | licence-unverified | too little history in nearby wells |
| How well monitored is this spot? (`gwcov`) | water | nearby: monitoring density around the pin | Groundwater levels | licence-unverified | — |
| Groundwater quality (`gwq`) | water | area: samples within 3-5 km | Groundwater quality samples | licence-unverified | no recent samples nearby |
| Fluoride in nearby groundwater (`gwf`) | water | area: samples within 3-5 km, not this well | Groundwater quality samples | licence-unverified | no recent samples nearby |
| Nitrate in nearby groundwater (`gwno3`) | water | area: samples within 3-5 km, not this well | Groundwater quality samples | licence-unverified | no recent samples nearby |
| Salinity (TDS) in nearby groundwater (`gwtds`) | water | area: samples within 3-5 km, not this well | Groundwater quality samples | licence-unverified | no recent samples nearby |
| Principal aquifer type (nearby sample records) (`aq`) | water | area: nearby sample records | Groundwater quality samples | licence-unverified | — |
| Nearest lake / river water-quality station (`lakewq`) | water | nearby: the nearest monitoring station (2017) | Lake, river and STP water quality | stale, unvalidated, licence-unverified | — |
| Sewage treatment plant outlet nearby (`stp`) | water | nearby: the nearest plant | Lake, river and STP water quality | stale, unvalidated, licence-unverified | — |
| Hydrogeology of the ground here (regional map) (`gwp`) | water | area: the regional map unit the pin falls in | Groundwater potential map | undated, unvalidated, licence-unverified | pin outside the mapped units |
| Mapped tank storage nearby (`tankstore`) | water | nearby: tanks within 2 km | Tank capacity records and stream order | licence-unverified | capacity is missing for 63% of tanks |
| Water connection, supply hours and tanker dependence (`supply`) | water | none: no data: connection, supply hours and tanker use are not published | No source | no-data | no public record of connections, supply frequency or tanker dependence per address |
| Mapped HMWSSB supply pipe near the pin (`supplynet`) | water | nearby: mapped pipes in the 100 m cells around the pin | HMWSSB mapped water-supply pipes and sewer lines; service sections | undated, unvalidated, licence-unverified | pin outside the mapped network area |
| Mapped sewer line near the pin (`sewernet`) | water | nearby: mapped sewer lines in the 100 m cells around the pin (core city only) | HMWSSB mapped water-supply pipes and sewer lines; service sections | undated, unvalidated, licence-unverified | sewer lines are mapped only for the core city |
| Distance to a main road (`road`) | infra | nearby: nearest mapped main road | Roads, hospitals, schools, shops and other places | undated, unvalidated, licence-unverified | — |
| Hospital: road travel (`acc_hospital`) | infra | live: road route from the pin to the nearest mapped hospitals | Road travel time and distance; Roads, hospitals, schools, shops and other places | undated, unvalidated, restricted-licence, licence-unverified | the routing servers did not answer |
| Metro / rail station: road travel (`acc_metro`) | infra | live: road route from the pin to the nearest mapped station | Road travel time and distance; Bus stops, metro stations, police stations | undated, unvalidated, restricted-licence, licence-unverified | the routing servers did not answer |
| Bus stop: road travel (`acc_bus`) | infra | live: road route from the pin to the nearest mapped stop | Road travel time and distance; Bus stops, metro stations, police stations | undated, unvalidated, restricted-licence, licence-unverified | the routing servers did not answer |
| School: road travel (`acc_school`) | infra | live: road route from the pin to the nearest mapped school | Road travel time and distance; Roads, hospitals, schools, shops and other places | undated, unvalidated, restricted-licence, licence-unverified | the routing servers did not answer |
| Market / supermarket: road travel (`acc_market`) | infra | live: road route from the pin to the nearest mapped market | Road travel time and distance; Roads, hospitals, schools, shops and other places | undated, unvalidated, restricted-licence, licence-unverified | the routing servers did not answer |
| Traffic congestion points within 1 km (`choke`) | infra | nearby: points within 1 km | Traffic choke points and planned junction improvements | undated, unvalidated, licence-unverified | — |
| GHMC junction improvement planned nearby (`junc`) | infra | nearby: the nearest planned junction | Traffic choke points and planned junction improvements | undated, unvalidated, licence-unverified | — |
| Power breakdown history (dated) (`power`) | infra | area: cells within 1.5 km, FY2017-18 | Power breakdown history | stale, unvalidated, licence-unverified | — |
| High-voltage transmission line nearby (`tx`) | infra | nearby: lines within a stated distance | Forest boundary, high-voltage lines and substations | undated, unvalidated, licence-unverified | — |
| Electricity substation nearby (`sub`) | infra | nearby: substations within 3 km | Forest boundary, high-voltage lines and substations | undated, unvalidated, licence-unverified | — |
| Landfill / dump yard (`landfill`) | infra | nearby: the nearest site | Landfills and dump yards | undated, unvalidated, licence-unverified | — |
| Nearest noise monitor (dated) (`noise`) | infra | nearby: the nearest monitor (2018) | Noise monitors | stale, unvalidated, licence-unverified | — |
| Air quality right now (`air`) | infra | live: model grid, the current hour | Air quality now | restricted-licence | the air-quality service did not answer |
| Hospital (`f_hospital`) | live | nearby: mapped places within a stated distance; service not verified | Roads, hospitals, schools, shops and other places | undated, unvalidated, licence-unverified | — |
| School (`f_school`) | live | nearby: mapped places within a stated distance; service not verified | Roads, hospitals, schools, shops and other places | undated, unvalidated, licence-unverified | — |
| Market / supermarket (`f_market`) | live | nearby: mapped places within a stated distance | Roads, hospitals, schools, shops and other places | undated, unvalidated, licence-unverified | — |
| Metro / rail station (`f_metro`) | live | nearby: mapped stations within a stated distance | Roads, hospitals, schools, shops and other places; Bus stops, metro stations, police stations | undated, unvalidated, licence-unverified | — |
| Bus station (`f_bus`) | live | nearby: mapped stations within a stated distance; frequency unknown | Roads, hospitals, schools, shops and other places; Bus stops, metro stations, police stations | undated, unvalidated, licence-unverified | — |
| Park (`f_park`) | live | nearby: mapped places within a stated distance | Roads, hospitals, schools, shops and other places | undated, unvalidated, licence-unverified | — |
| Bank (`f_bank`) | live | nearby: mapped places within a stated distance | Roads, hospitals, schools, shops and other places | undated, unvalidated, licence-unverified | — |
| Police station (`f_police`) | live | nearby: mapped stations within a stated distance | Roads, hospitals, schools, shops and other places; Bus stops, metro stations, police stations | undated, unvalidated, licence-unverified | — |
| Fire station (`f_fire`) | live | nearby: mapped stations within a stated distance | Roads, hospitals, schools, shops and other places | undated, unvalidated, licence-unverified | — |
| Government ambulance (108) station (`f_amb`) | live | nearby: 108 stations within a stated distance | 108 ambulance stations and health facilities | undated, unvalidated, licence-unverified | — |
| Jobs and lifestyle hubs (`f_jobs`) | live | nearby: mapped offices, malls and cinemas within 3-5 km | Roads, hospitals, schools, shops and other places | undated, unvalidated, licence-unverified | — |
| Disappeared water body (`lost`) | land | pin: tested at the pin position, not matched to a parcel | Disappeared water bodies | undated, unvalidated, licence-unverified | — |
| Forest land boundary (`forest`) | land | pin: tested at the pin position, with distance if outside | Forest boundary, high-voltage lines and substations | undated, unvalidated, licence-unverified | — |
| Endowment (temple) properties nearby (`endow`) | land | nearby: points within 400 m; locations approximate | Endowment properties | undated, unvalidated, licence-unverified | — |
| Plot identity (survey parcel) (`plot`) | land | pin: which surveyed parcel the pin falls in; boundaries are a drawn outline, not a legal boundary | Survey-parcel outlines | undated, unvalidated, licence-unverified | no survey parcels are mapped here (the old city core), or the pin is on a road or unmapped land |
| Listed in a state prohibitory-land layer (`prohib`) | land | pin: tested at the pin position against parcels listed in a state GIS layer | Parcels carrying a prohibitory-land category; Survey-parcel outlines | undated, unvalidated, licence-unverified | no parcel mapped here, so the layer cannot be tested; the legal register is on the registration portal |
| Which official plan governs this area (`planauth`) | land | pin: which authority's plan governs the area the pin is in | Planning-authority areas (which plan governs); Published master plans (documents) | licence-unverified | pin outside the HMDA authority areas held |
| Master-plan land use and zoning (`zoning`) | land | none: no data: the plans are published as images and PDFs and are not read | Published master plans (documents) | licence-unverified, no-data | HMDA publishes the plans as static sheets; no queryable land-use layer was found |
| Layout and building permissions (`perm`) | land | none: no data: approvals are held in HMDA / DTCP systems | No source | no-data | no public bulk record of layout and building permissions was reached |
| Lake buffer / FTL risk (`ftl`) | land | nearby: lake outline distance; not the legal FTL | Roads, hospitals, schools, shops and other places; Tank capacity records and stream order | undated, unvalidated, licence-unverified | — |
| Nala widening near the plot (`widen`) | land | nearby: nala segments within 150 m; widths partly blank | GHMC nalas, drains and listed inundation points | undated, licence-unverified | — |
| Typical asking price (apartments) (`price`) | land | locality: a named locality, asking prices | Asking-price ranges | unvalidated, licence-unverified, coarse-scope | no priced locality within 4 km |
| Mapped features overlapping the parcel outline (`overlap`) | land | parcel: the whole matched survey outline, tested against three layers | Survey-parcel outlines; Disappeared water bodies; Forest boundary, high-voltage lines and substations; Tank capacity records and stream order | undated, unvalidated, licence-unverified | needs a pin that matches exactly one survey parcel; not possible in the old city core where no survey parcels are mapped |
| Fire station on the state list (`fire_gis`) | infra | nearby: listed points within 10 km; straight line, not response time | State fire-station list | undated, unvalidated, licence-unverified | no station listed as Existing within 10 km, or the list is not loaded |
| Earthquake zone (state GIS layer) (`seismic_gis`) | hazards | area: the regional zone polygon the pin is in, not a building | State seismic-zone layer | undated, licence-unverified | outside the zones mapped in the state layer, or the layer is not loaded |

## If a source is removed

Findings that rest only on the source become unknown; findings with other sources lose a supporting source. The test suite removes each data file in turn and fails if any finding that depends only on it is still rated good, watch or concern.

| Source | Becomes unknown | Loses a supporting source |
|---|---|---|
| SETHU ward flood model | sus, depth | storms |
| Storm rainfall by mandal (8 documented floods) | analog | storms |
| Heavy-rain days per monsoon | heavyrain | — |
| Roads, hospitals, schools, shops and other places | road, f_hospital, f_school, f_market, f_park, f_bank, f_fire, f_jobs | lake, acc_hospital, acc_school, acc_market, f_metro, f_bus, f_police, ftl |
| Bus stops, metro stations, police stations | — | acc_metro, acc_bus, f_metro, f_bus, f_police |
| 108 ambulance stations and health facilities | f_amb | — |
| 90 m elevation around the pin | pocket | — |
| Air quality now | air | — |
| Road travel time and distance | — | acc_hospital, acc_metro, acc_bus, acc_school, acc_market |
| GHMC nalas, drains and listed inundation points | nala, nalaenc, inund, widen | — |
| Tank status 2014 vs 2023 | hy | hmda |
| HMDA lake list and FTL notification status | — | hmda |
| Tank capacity records and stream order | stream, tankstore | lake, ftl, overlap |
| Groundwater potential map | gwp | — |
| Disappeared water bodies | lost | overlap |
| Forest boundary, high-voltage lines and substations | tx, sub, forest | overlap |
| Endowment properties | endow | — |
| Groundwater levels | gw, gwnear, gwdepth, gwpre, gwrec, gwtrend, gwcov | — |
| Groundwater quality samples | gwq, gwf, gwno3, gwtds, aq | — |
| Landfills and dump yards | landfill | — |
| Power breakdown history | power | — |
| Traffic choke points and planned junction improvements | choke, junc | — |
| Flood rehabilitation centres | shelter | — |
| Lake, river and STP water quality | lakewq, stp | — |
| Noise monitors | noise | — |
| Surface heat in the dry season | heat | — |
| Dry-season greenness (NDVI) | green | — |
| Earthquake zone | seismic | — |
| Asking-price ranges | price | — |
| Planning-authority areas (which plan governs) | — | planauth |
| Published master plans (documents) | zoning | planauth |
| Survey-parcel outlines | plot | prohib, overlap |
| Parcels carrying a prohibitory-land category | — | prohib |
| HMWSSB mapped water-supply pipes and sewer lines; service sections | supplynet, sewernet | — |
| State fire-station list | fire_gis | — |
| State seismic-zone layer | seismic_gis | — |
