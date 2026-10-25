# Data-source discovery, round 2 (25 Oct 2026)

Discovery only. **Nothing here is integrated into the app.** For each lead: what was actually reached, what it contains, what it would add to a property report, and what is still unknown. Method: the whole state GIS server was catalogued once (names only), every candidate layer was queried at five real places (Charminar, Gachibowli, Hussain Sagar, Saroornagar lake, Kukatpally), portals were opened, and plan files were inspected through byte ranges (nothing large was downloaded). Scripts and raw output: `research/v8/`.

The guiding rule from the review: we need **independent, verifiable evidence for claims SETU already makes**, not more layers.

## 1. Ranked result

| Rank | Gap | What was found | Verdict | Next step |
|---|---|---|---|---|
| 1 | **Lake / FTL evidence tied to survey numbers** | Official FTL boundary polygons are **not retrievable**: HYDRAA's `FTL_Tanks` and `Topo_Tanks` services declare 2014 / 2023 / 2025 groups but their sub-layers return nothing (query and identify both fail). What *is* reachable: a HYDRAA **lake-side cadastral layer** (`Fourth_Window`, 63,686 parcels) and the HYDRAA tank layer (`First_Window`, 1,122 tanks) with the tank's **base survey number** and its first-seen period. | **Ready to investigate, partial.** Gives "the survey number of the lake" and the parcels around it, not the legal FTL line. | Compare `Fourth_Window` with the cadastral layer we use at 20 lakes; build "your survey number is X metres from tank survey no. Y" only if the comparison holds |
| 2 | **Is the parcel recorded as agricultural land?** (new, not on the review list) | `Bhunaksha_query` layer 7 'Cadastral' (239,986 parcels in urban-local-body villages) carries `LandUse_Fr`, the **revenue-record land class**: Dry, Wet, Abadi, Tank, Road, Waste Land, Naksha… (228,151 filled). | **High value for peri-urban buyers; not zoning.** A "Dry" or "Wet" parcel is recorded as agricultural and usually needs conversion before housing. Does not cover the old city. | Check it against our parcel tiles by village and survey number; show it as "recorded class", never as permitted use |
| 3 | **Fire stations, seismic zone** | `TCUR` layer 61 'Fire Stations': 71 points marked **Existing / Proposed** (some "Moved"). `TCUR` layer 90 'Seismic Zones': 3 polygons; **Zone II at all five test places**. | **Ready, small.** Fire: honest Existing vs Proposed. Seismic: the state GIS now corroborates the secondary-source Zone II we had flagged as unverified (still not the BIS standard itself). | Replace the OSM-only fire finding; point-in-polygon for seismic; compare with OSM at 10 places before switching |
| 4 | **Master-plan zoning** | A search of all **2,038 layers** found **no land-use / master-plan zoning layer**. HMDA's plan files are **not georeferenced**: the Shamshabad sheet is a 53,251 x 8,224 pixel JPEG with no coordinates and no world file; the core-city circle PDF carries no GeoPDF markers in the sampled bytes. | **Cannot be built from public data today.** Manual georeferencing would be approximate and unverifiable. | Keep "zoning: not read". The only real route is to ask HMDA for vector data in writing |
| 5 | **Groundwater, geology, water quality** | TGRAC's water-datasets page lists the 1:50,000 programme layers: lithology, geomorphology, structures (lineaments), wells (water table, depth, yield), recharge structures, and Phase IV pre- and post-monsoon quality (pH, TDS, hardness, fluoride, chloride, iron, nitrate, sulphate). The groundwater-potential layer we already use comes from this programme. CGWB's monitoring page is reachable. | **Moderate, regional scale only.** Lithology and lineaments are reachable as services. Must be labelled as regional, never a property measurement. | Pull lithology + geomorphology + lineaments, compare with the groundwater-potential units we have |
| 6 | **Satellite flood footprints** | NRSC NDEM flood maps exist as PDFs (the example Telangana map, 2 Sep 2024, is 1.5 MB and downloads). **Directory listings are blocked** (403 / 404), so there is no public index; an event catalogue has to be built by hand from the site. TCUR's 'Flooding Area' layer (30 polygons) is in the far north (about 19.4 N), nowhere near Hyderabad. | **Valuable for validation, heavy to build.** Each map would need georeferencing. | Pilot with 2 to 3 events; use only to *test* the flood model, never as a new finding |
| 7 | **Historical air quality** | CPCB and OGD pages are reachable (JavaScript apps; no documented bulk download found). OGD resource APIs normally need a registered key (not verified here). | **Low priority.** | Defer |
| - | **Parcel identity / land records** | Bhu Bharati `knowLandStatus` was **unreachable** from this machine (connection fails even with curl); it is a lookup portal, not a bulk feed. | **Stays a manual step** in the checklist. | None |

## 2. Detail

### 2.1 What the server really contains
49 folders, 171 services, 2,038 layers (catalogue in `research/v8/tgrac_catalogue.json`). Our earlier survey saw 22 services. The `TCUR` service alone has 90+ layers; I had only read layers 0-39.

### 2.2 HYDRAA / lakes
- `Hydra_Folder/First_Window` layer 0 'ORR Tanks': 1,122 polygons. Fields include water-body name, village, **`Base_Syno` (the tank's own survey number)**, `WBCP` (period it first appears, e.g. "Before 1940s"), 2014 and 2023 status. Example: Kummari Kunta, Gachibowli, base survey no. 81, Live. This is the layer behind our existing tank status finding; the survey number and first-seen period are **not yet used**.
- `Hydra_Folder/Fourth_Window` 'Cadastral Parcels': 63,686 polygons (about 4,700 in Hyderabad district), remarks such as "Cheruvu", "Kunta", "Tari" mark parcels that are water-body parcels. At Saroornagar lake it returns 31 parcels within 900 m where the main cadastral layer returns 3. Fields: survey number, village, mandal, remark, type (Dry / Wet). District names are spelled six different ways ("Rangareddy", "Ranga Reddy", "RangaReddy", "Hydarabad"...): needs cleaning.
- `FTL_Tanks`, `Topo_Tanks`: year groups only. **FTL polygons are not available through the public REST API.** The HMDA lakes portal (already used) holds the FTL PDFs for about 25 Hyderabad-district lakes; its page is a single-page app with no data API visible.
- HYDRAA's asset-protection page links two PDF lists (protection units), not FTL data.
- The Musi basin service has a Musi River buffer polygon (one feature, buffer distance 600 m) whose legal meaning is undocumented: not used.

### 2.3 Revenue land class
`LandUse_Fr` values (top): Dry 86,918; Wet 63,122; "Naksha" 61,304; blank 11,835; Waste Land 4,935; Road 1,813; Tank 1,383; Abadi 875. The code field `LUCodeTiff` is the same classification as numbers. These are **old revenue-map categories**, not current use and not zoning. The layer covers ULB villages (Pedda Amberpet, Manikonda, Narsingi, Nizampet, Boduppal, Dammaiguda and many more) and returned nothing at our five core places.

### 2.4 Emergency and civic
Fire stations: `TCUR/61` has 71 features (Existing / Proposed / Moved remark); `PoliceProperties` and `TGIIC` layers hold 438 statewide. Ambulance layers (existing and proposed stations) are already integrated. The Fire Services website lists stations by district but is a form-based page.

### 2.5 Master plans
HMDA publishes about 30 mandal sheets (JPEG) and 7 circle PDFs. Inspected without downloading the files: sheet dimensions 53,251 x 8,224 px, no EXIF GPS, no geo tags, no sidecar (`.jgw`, `.jpgw`, `.wld`, `.xml`, `.prj` all 404); PDF is version 1.4 with one large image object and no GeoPDF markers in the head and tail samples.

### 2.6 Portals reached, and their access model
| Portal | Reached | Access model seen |
|---|---|---|
| HMDA lakes | yes | single-page app, no data API visible |
| HYDRAA asset protection | yes | PDF lists only |
| TGRAC water datasets | yes | a table describing datasets; services on the ArcGIS server |
| TGRAC WebGIS | yes | links to a forest-lands web app |
| Bhu Bharati land status | **no** | lookup portal, not reachable from here |
| Bhuvan TWRIS | yes | JavaScript geoportal, no bulk API documented |
| NRSC NDEM | yes | PDF maps; directory listings blocked |
| CPCB AQI | yes | JavaScript app |
| data.gov.in AQI | yes | catalogue page; API normally needs a registered key (not verified) |
| India-WRIS | yes | JavaScript shell |
| CGWB monitoring | yes (curl) | page of links; Python could not verify its certificate |

Two hosts (`www.hmda.gov.in`, `cgwb.gov.in`) fail certificate-chain checks in Python while browsers and curl accept them. I did not disable verification; any pipeline that fetches from them needs a deliberate decision (a pinned intermediate certificate, or manual download).

## 3. Reuse permissions (status: unverified)
- **None of the state GIS services publishes licence text** (abstracts are placeholders). Everything from `tgrac.telangana.gov.in` stays "licence unverified" in the register.
- NRSC / NDEM and Bhuvan content: terms not checked.
- data.gov.in datasets are normally released under the Government Open Data Licence (India), but each resource must be checked individually; not verified here.
- Before any public release: ask TGRAC and HYDRAA in writing which layers may be redistributed in a commercial product.

## 4. Corrections to earlier statements
- "TCUR has no fire-station layer": **wrong**; layer 61 exists (the review was right).
- "Seismic zone: secondary sources only": the state GIS now corroborates Zone II; the BIS standard itself is still unchecked.
- "No master-plan data": confirmed after searching all 2,038 layers, not only the ones I knew about.

## 5. Integration plan (when you say go), with the test that decides each one
| Order | Build | It only ships if |
|---|---|---|
| 1 | Seismic from the state layer; fire stations from `TCUR/61` with Existing / Proposed | at 10 places the layer agrees with OSM within 300 m for existing stations, and "Proposed" is never counted as present |
| 2 | Lake-side parcels + tank base survey number | at 20 lakes the HYDRAA parcels and our cadastral parcels agree where both exist, and the survey numbers of the lakes match the HMDA lake list for the lakes where both name one |
| 3 | Revenue land class on parcels | for 500 parcels the class from layer 7 matches the parcel found by village and number in our tiles; wording says "recorded as", never "zoned" |
| 4 | Lithology / geomorphology / lineaments | the regional units agree with the groundwater-potential unit already used at 20 places |
| 5 | Flood-footprint pilot (2-3 events) | georeferencing error is measured against a known landmark and is smaller than a ward |

Each new finding gets a registry entry, scope, validation status and a removal test like every other source, so the dashboard and the tests cover it from day one.

## 6. What stays impossible for now
Legal FTL lines as data; land-use zoning of any plot; title and ownership; the individual plot inside a survey number; survey dates of the GIS layers; the legal meaning of the Musi buffer and prohibitory layers.
