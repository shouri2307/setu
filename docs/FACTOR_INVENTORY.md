# SETU factor inventory (24 Oct 2026)

Every factor the evidence report can show, with status: **Implemented** (real data, tested) · **Partial** (works with caveats) · **Planned** (source verified, not built) · **Unavailable** (no usable source found). The report shows "unknown" for anything it cannot answer; it never fills a zero.

The report has five sections and **no combined score** (the original 8-pillar Location Score is unchanged). A section turns *Concern* only on a high-severity finding or three ordinary concerns.

## Hazards
| Factor | Status | Source / method | Caveat |
|---|---|---|---|
| Flood susceptibility rank | Implemented | SETHU ward model (8 floods), LOEO AUC ≈ 0.69 | ranks wards, not streets |
| Modelled depth at 192 mm | Implemented | stated rain→depth assumption | order of magnitude |
| Storm history per ward (8 events) | Implemented | TSDPS mandal rain + news-named wards | non-commercial; "named" ≠ only flooded place |
| Low pocket vs surroundings | Implemented | live 90 m elevation | coarse |
| Lake/tank proximity | Implemented | OSM + TGRAC outlines | not the legal FTL |
| Nearest tank 2014 vs 2023, HMDA notification | Implemented | TGRAC/HYDRAA, HMDA list | satellite class / name matching |
| Mapped nala; nala encroachment | Implemented / Unavailable | TGRAC | encroachment fields blank in source |
| Listed inundation areas | Implemented | 23 GHMC points | very short list |
| Surface heat | Partial | Landsat 8/9, 150 m | **not validated** (no rank agreement with station air temperature); low confidence |
| Greenness (NDVI) | Implemented | Landsat 8/9, 150 m | dry-season greenness |
| Seismic zone | Partial | "Zone II" per secondary sources, IS 1893:2016 | not checked against the standard; a newer edition may differ |
| Earthquake zone (state GIS layer) | Implemented | TGRAC TCUR seismic layer: Zone II across the whole map region | regional zone only; says nothing about a building's structure; zoning edition unpublished |
| Flood shelters | Implemented | GHMC list (101) | only listed localities |
| Heavy-rain days per monsoon (mandal) | Implemented | TSDPS daily files, 5–7 complete June–October seasons 2018–2024 | about 1.4 a year; 2025 excluded (incomplete file); mandal not plot; too few seasons for a return period |
| Storm analogs (preliminary association) | Implemented | 6 date-specific storms ≥ 60 mm vs news-named wards | associations only, tiny samples, never a probability |
| Natural stream channel nearby | Implemented | TGRAC stream-order layer | does not prove a buried channel |
| Historical inundation maps (NRSC) | Planned | 9 PDFs for Oct 2020 | qualitative |
| Riverine flood extent (Telangana) | Planned | Sentinel-1 probe works for Khammam | separate research track |

## Water security
| Factor | Status | Source / method | Caveat |
|---|---|---|---|
| Nearest monitoring well (observed) | Implemented | GWD monthly piezometers | one well |
| Area depth, dry-season depth, rebound, trend | Implemented | median of ≥3 agreeing wells within 3 km | wells vary by metres; trend starts in wet years |
| Monitoring coverage | Implemented | counts + distance | |
| Fluoride, nitrate, salinity (TDS) | Implemented | GWD water-quality samples vs BIS limits | other wells' results |
| Aquifer / hydrogeology (recharge, yield, well depth, success) | Implemented | TGRAC groundwater-potential map, 1,979 units | regional, undated |
| Lake/river and STP water quality | Implemented (dated) | TSPCB 2017 via Lakeer | 8+ years old |
| Mapped tank storage nearby | Implemented | TGRAC water-body layer, capacity = area×bund/2 | estimate, missing for 63% of tanks, present-day storage not measured |
| Rainfall deficit / drought | Planned | complete monsoon rainfall 2018–2024 now in hand | not built |
| Mapped HMWSSB supply pipe near the pin | Implemented | TGRAC TCUR supply-line layer in ~100 m cells | a mapped pipe is not a connection; mapping uneven; undated |
| Mapped sewer line near the pin | Partial | TGRAC core-city sewer layer | core city only |
| HMWSSB operating section | Implemented | TGRAC section polygons | names the office area, not a connection |
| Water connection, supply hours, tanker dependence | Unavailable | no public per-address record found | |

## Infrastructure
| Factor | Status | Source / method | Caveat |
|---|---|---|---|
| Distance to main road | Implemented | OSM | |
| Road travel time/distance to hospital, metro, bus, school, market | Implemented | OSRM on OSM roads (live) | no live traffic; demo server |
| Traffic congestion points, junction plan | Implemented | Hyderabad Traffic Police, GHMC | short lists |
| Power breakdown history | Implemented (unscored) | FY2017-18 log | 8 years old |
| High-voltage lines, substations | Implemented | TGRAC/TCUR | |
| Fire station on the state list | Implemented | TGRAC TCUR fire layer (32 Existing, 39 Proposed) | straight-line; positions flagged uncertain by the source; never says a station operates |
| Landfills (by size) | Implemented | 11 sites; only one ≥ 20 ha | |
| Noise | Implemented (dated) | 10 monitors, 2018 | sparse |
| Air quality | Implemented | live model | |
| Bus service frequency (GTFS) | **Needs permission** | feed not public | |
| Road width / access to the plot | Unavailable | | |

## Liveability
Hospital, school, market, metro, bus, park, bank, police, fire, 108 ambulance, jobs/malls — **Implemented** from OSM/Overture/health GIS (straight-line distances; see Infrastructure for road time).

## Land & planning
| Factor | Status | Source / method | Caveat |
|---|---|---|---|
| Disappeared tank under/near the pin | Implemented | TGRAC "Water Bodies – Disappeared" | map record, not legal |
| Forest boundary | Implemented | TGRAC/TCUR | |
| Endowment properties nearby | Implemented | TGRAC points | approximate locations |
| Lake buffer / FTL risk | Partial | outline proximity | needs the legal FTL |
| Nala widening | Implemented | TGRAC segments | width fields partly blank |
| Asking price band | Partial | portal pages compiled with an AI assistant | indirect provenance |
| Plot identity (survey parcel) | Partial | TGRAC cadastral outlines; statuses verified / approximate / no match / source unavailable; manual survey number and village | survey-number level, not house plot; old city core unavailable; outline is not a legal boundary |
| Listed in a state prohibitory-land layer | Partial | TGRAC 'ULB_Cadastral_Prohibited' (656 parcels in the box) | NOT the legal register; undocumented basis and date |
| Which official plan governs this area | Implemented | TGRAC HMDA authority areas + official plan links | says which plan, not the zone |
| Mapped features overlapping the parcel outline | Implemented | cadastral outline vs disappeared-tank, forest and tank layers | only for an unambiguous match; sampled, 3% minimum |
| Master-plan land use / zoning | Unavailable | official plans are PDF / JPEG sheets | not read by SETU |
| Layout permissions, utility approvals | Unavailable | | ask HMDA with the survey number |

## Not attempted (no usable source)
Crime, road-accident black spots, soil/geotechnical (soil atlas covers Khammam only), building structural safety.

## Report features (not factors)
| Feature | Status | Notes |
|---|---|---|
| Five-section evidence report | Implemented | no combined score |
| Interactive evidence map layers (wells, groundwater zones, heat, high-voltage lines, disappeared tanks, tank status and capacity, streams) | Implemented | every feature opens a popup with source, data period, resolution, confidence and caveat; Leaflet engine only |
| Evidence-driven due-diligence checklist | Implemented | one action per concern / watch / data gap, grouped legal vs flood vs water vs infrastructure; ticks saved on the device; offices marked "not verified" unless reached |
| Live road routing with failover and cache | Implemented | OSRM public servers; no traffic |
| Compare two addresses | Implemented | same engine for both; evidence and coverage side by side; no winner or score; unknown on one side is "not comparable"; shareable link `#/c/…` |
| Evidence-quality registry and internal dashboard (`quality.html`) | Implemented | every source and finding with observation date, service date, resolution, coverage, licence, validation, freshness, scope and removal impact; generated matrix in `EVIDENCE_MATRIX.md` | internal |
| 'Applies to' scope tags, 'why incomplete' list, property-identity card | Implemented | | |
