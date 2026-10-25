# Next-batch audit: property identity, planning and water (24 Oct 2026)

Scope: the gap between a location report and a report about one specific property. Method: probe every candidate source for real, record exactly what came back, separate **confirmed access** (we downloaded and inspected it) from **leads** (a search result or a page we have not opened), then build only what the evidence supports. Nothing here is committed or deployed. The per-factor register is in [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md) (generated from the same registry as the dashboard at `web/quality.html`).

## 1. What was found

### Parcels and survey numbers: confirmed, and my earlier conclusion was wrong
The earlier note said "no parcels inside core GHMC". That was true of the two layers I had tested, and wrong for the state cadastral layer I had not.

| Fact | Evidence |
|---|---|
| The layer | TGRAC `Bhunaksha_Cadastral` layer 0 "Cadastral 2.5m": 3,823,475 polygons statewide, 3,693,825 (96.6%) with a filled `Parcel_num`. Service document created 2025-04-19; survey dates and accuracy are not published. |
| `SNo` is not a survey number | It is a **village serial** (Kondapur 1665, Kohtaguda 1666). The survey number is `Parcel_num` ("91/1", "215"). Treating `SNo` as the survey number would have given plausible but wrong answers. |
| Three kinds of polygon | survey parcels (`Parcel_num` filled); village-sized placeholders ("Missing Village", "Not Available"); one "GHMC … to be checked" polygon over the old city. Only the first kind is a parcel. |
| Coverage in the study box | 47,249 parcel records (42,980 unique, 216 villages). Nearly every 0.03° cell in the HUDA, CDA, HADA and wider HMDA areas has parcels; 41 of 49 cells inside the 145 wards have some; in the old MCH core only 7 of 15 cells do. At Charminar, Banjara Hills, Secunderabad and Hussain Sagar the pin falls only in the placeholder. |
| Granularity | median outline 7,716 m² (0.77 ha): these are **survey numbers**, which in a built-up layout can hold hundreds of house plots. The layer cannot identify a plot or a flat. |
| Data quality | about 1% of numbers carry remarks such as "Duplicate Number" or "Not Visible Number"; 1.1% of (village, number) pairs are used by more than one outline. |
| Prohibitory category | `Bhunaksha` layer 0 "ULB_Cadastral_Prohibited": 656 parcels in the box carry a free-text `CATEGORY_OF_PROHIBITORY_LAND` (Govt Land, Covered By Court Stay, Sarkari, Assigned, Wakf, Endowment, Ceiling Surplus…). All 656 join onto the cadastral parcels by village and number. Legal basis, date and completeness are **not documented**. |
| Not used, by design | `Dharani_Database`, `Owners_Info_*` (owner personal data). |

### Official master plans: confirmed to exist, confirmed not machine-readable
- HMDA's site (hmda.gov.in, unreachable at the earlier probe, reachable on 24 Oct 2026) publishes: the **Master Plan 2031** as about 30 mandal-wise **JPEG sheets** (23-29 MB each, files dated 2021); the **Revised Development Plan of the erstwhile MCH area** as seven circle-wise **PDFs** (about 29 MB, uploaded June 2022) plus a zoning-regulations PDF and a commercial-roads PDF; and HUDA / HADA / CDA plans listed on the same page (not opened).
- None is georeferenced and no vector zoning layer was found on the servers we reached. Georeferencing 23-29 MB images from control points would be approximate at best, so SETU does **not** read them and cannot state any plot's land use.
- **Confirmed and built:** TGRAC `HMDA` layer 0 holds the six planning-authority areas (MCH, HUDA, CDA, HADA, HMR, HMR growth corridor). They answer "which plan governs here" and were checked at 14 places against local planning history (Gachibowli and Kondapur in CDA, Kukatpally and Uppal in HUDA, Shamshabad in HADA, Charminar and Banjara Hills in MCH). The wider HMDA region links straight to the mandal's Master Plan 2031 sheet.
- Caveats: authority areas are undated (service created 2025-04-17); HMDA's jurisdiction was reportedly widened in 2025 (secondary source), so the report asks the buyer to confirm.
- `StampsAndRegistrations/SRO` (circles; "Buildings with Price", 40,589 polygons): no hits at 8 test points, coverage unclear, not used.
- A third-party map-layer site sells HMDA master-plan overlays; not used (provenance and terms unknown).

### Water: partly confirmed
- **Confirmed:** the TCUR service carries HMWSSB's mapped network: 215,519 supply-line segments (99.7% "IN USE"), 54,977 valves, 264 reservoirs, 54 pump houses, 110 operating sections, 1,100 dockets, and for the "core city" 90,299 sewer lines and 214,067 manholes. All 215,506 / 90,298 segments inside the box were downloaded and rasterised to ~100 m cells (pipe geometry is not redistributed). Independent recomputation at six places agrees within about 4% per window.
- Data traps found: `OBJECTID` is not unique in these layers (404 distinct values over 481 lines in one box; the true key is `OBJECTID_12`); the server's `returnCountOnly` over-counts line layers; 12,599 supply segments carry an abandon date of 1900-01-01 (a placeholder); 37% of supply segments read `ENABLED = 0` with no documented meaning, so the flag is not used.
- Mapping is uneven (a 900 m box holds from 0 to over 700 supply segments) and sewer lines exist for the core city only.
- **Lead, not opened:** OpenCity lists a "core city sewer lines" GeoJSON (public domain, PM Gati Shakti source) and monthly HMWSSB water-connection CSVs (applied / approved: tabular, not spatial).
- **Not found anywhere public:** connection status per address, supply hours, tanker dependence.

## 2. What was built

| Item | Status |
|---|---|
| Evidence-quality registry and internal dashboard (`quality.json`, `quality.html`) | built; 34 sources, 73 findings; tests fail if the engine emits an unlisted finding |
| "Applies to" scope on every finding (pin, parcel outline, near the pin, area, ward, mandal, city, live, none) | built |
| "Why this report is incomplete" list | built |
| Property identity: pin → survey parcel with the statuses **verified match / approximate match / no match / source unavailable**, manual survey number, village, plot, LP and document references (references stay on the device, never in the link) | built |
| Planning authority + official plan links; zoning stays **unknown** | built |
| Prohibitory-category layer, quoted as recorded, never as the legal register | built |
| Parcel-outline overlap with disappeared tanks, forest and tank outlines (only for an unambiguous match) | built |
| Mapped water-supply and sewer presence, operating section | built |
| Missing data can no longer read as reassuring (removal test over every optional file) | built; it found and fixed six real cases (`nala`, `inund`, `lost`, `choke`, `landfill`, `f_jobs`) |

## 3. Ranked list

### Ready to implement (no permission needed, evidence in hand)
1. Extend parcel tiles beyond the study box (same pipeline, `p31`), if the demo grows.
2. Automate the monthly groundwater refresh with change detection (`p19`/`p20` already exist).
3. Open the OpenCity sewer-lines and water-connection files and compare with the TGRAC network (a second, independent source for the water layer).
4. Satellite urban-expansion layer (Landsat / Sentinel are open), after validating the time periods.
5. Investigate the SRO "Buildings with Price" layer's real coverage (a registered-value proxy), before any price comparison.

### Needs permission or a licence decision first
1. Reuse terms for the TGRAC / HMDA parcel, planning and HMWSSB layers (no licence text published).
2. Written permission for TSDPS rainfall (non-commercial).
3. TGSRTC GTFS feeds (application required): bus frequency.
4. Property-portal price data: provenance and commercial rights, before any asking-price versus fundamentals comparison.
5. Paid or self-hosted replacements for Open-Meteo, OSRM demo servers and public map tiles before real traffic.

### Cannot be verified from public data today
- Legal restriction status of any property (the official prohibited-property register has reportedly contained many wrongly listed parcels and is being revised; SETU only quotes a state GIS layer and sends the buyer to the registration portal and Bhu Bharati).
- Title, ownership and encumbrances.
- Which plot or flat inside a survey number; boundaries on the ground; positional accuracy of the outlines (unpublished).
- Land-use zoning of any plot; layout and building permissions.
- Whether a mapped pipe is connected or flowing; supply hours; tanker dependence.
- The survey date of every TGRAC layer (only the map-document creation date is published, and the abstracts are placeholders such as "test").
- Heat-layer validity (negative result) and the seismic zone against the standard itself.

## 4. Lessons worth keeping
- Count queries are not ground truth for line layers; compare against a geometric check.
- Never de-duplicate on an attribute named `OBJECTID` without checking it is the layer's real key.
- A field called `SNo` was not what its name suggests; read sample rows before trusting a join.
- A failed request must be stored as "unknown", never as zero (my first coverage scan did the opposite and returned a flat zero everywhere).

## 5. UI overhaul (24 Oct 2026)
The report used to stack a 73/100 gauge, a "High caution" verdict, eight progress bars and, far below, an evidence report that deliberately has no score. It contradicted itself and buried the answer. Now (`web/platform/view.js`, `theme.css`):
- **One story per address:** what this check is about (map pin or matched plot) → the short version (needs attention / look into / looks fine / couldn't check) → before you pay (five steps) → details by topic (land and legal first) → cost → how to read it.
- **No combined score.** The convenience score lives inside "Everyday life", labelled as convenience, not safety.
- **Plain words:** every finding has a plain title; source, period, resolution, scope and the next step sit behind "Details and source".
- **Status is an icon and a word**, never colour alone. Light, high-contrast theme; mobile bottom sheet; agent, insurer and comparison views share the new evidence layer.
- Tests cover order, counts, every finding appearing once with its status word, jump links, escaping of hostile text, loading states, jargon-free summary text and the other lenses (4,704 checks in total).
