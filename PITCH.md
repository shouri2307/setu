# SETHU — final-round pitch kit

## The one-line version
**SETHU is a location-intelligence engine for Indian cities, built only on open data.**
Buyers, agents and insurers use the same engine through three different views.

## 90-second script (say it, then demo)

**0:00 — Hook (10 s)**
"October 2020. 192 mm of rain in one night. Cars floating on Tolichowki Road. Families who had just bought plots found out what land they had really bought."

**0:10 — One address, three reports (40 s).** Ask a judge for an address (or use their college) → search → location card appears.
1. **Customer report:** "Verdict in plain words, the water rising with rain, lakes near the plot, and the *true cost* — duties plus brokerage." → click *Try an example*.
2. **Real estate agent report:** "The same facts as negotiation evidence, and a market band from portals — we show asking prices and say so."
3. **Insurer report:** "Motor, Property and Health-access tiers with illustrative loadings — and a claim evidence check." → run the two demo buttons (Tolichowki 13 Oct 2020 = consistent; Banjara Hills 2 Mar 2020 = not supported by weather evidence). "Same engine, returned as JSON for their systems."

**0:50 — The reveal (10 s)**
"These are three *uses*. The product is SETHU — the engine underneath." → click **⚙ Engine**.

**1:00 — Proof (15 s)**
"Tested on floods it never saw: AUC 0.69 on held-out floods, 0.79 against GHMC's own waterlogging list. Our first version scored 0.49 — a coin flip. We show those numbers inside the app."

**1:15 — Business + ask (15 s)**
"Customers pay per report, agents per client, insurers and banks license the API. It runs on public and commercial map data, so it works in any Indian city in days — no government drain maps. We want one insurer pilot, in shadow mode on their closed claims."

## Expo stall
* QR code (header button) → the live site. Let visitors check **their own home** — the 📍 button uses their phone's location.
* Printed report: open the Customer report → PDF button, for a judge's locality.
* Have the two claim-demo buttons ready; they work offline of any typing.

## Say this / never say this
| Say | Never say |
|---|---|
| "Water-risk rank, tested on floods it never saw" | "Predicts flooding at your street" |
| "Indicative distance to a mapped lake — verify the legal FTL/buffer with HMDA/Irrigation" | "This plot is / isn't in the lake buffer" |
| "Illustrative loading, to calibrate with an insurer's claims" | "Insurers should charge X%" |
| "Rain-evidence tier; triage for investigators" | "Fraud detector" / "catches fraud" |
| "Ward-level today; finer once insurers share claims data" | "Street-level accuracy" |
| "Price check uses your own comparables and the official guidance value" | "AI-estimated land price" |

## Jury objections — answers
1. **"Routine hackathon flood project."** The flood model is one input. The product is the report people and insurers act on, and the validation is shown, not claimed.
2. **"No USP."** Open-data only (works in any city in days), honest validation inside the app, and one engine serving three customers.
3. **"Needs GHMC drain maps / government approval."** No RTI needed. GHMC's own nala network, drain and canal lines, tank outlines and a list of 23 official inundation areas are served publicly by the Telangana State GIS — SETHU already uses them (96 nalas, 1,162 segments with existing vs proposed widths, 3,960 drains). We state the limits: the records have no stated date, and their encroachment fields are blank. The ward flood model still runs on terrain, satellite and open maps.
4. **"Not relevant to Hyderabad."** Lake-buffer and waterlogging risk is *the* Hyderabad property question — and 2020 is in everyone's memory.
5. **"Is it only about the past?"** No — live 7-day rain forecast feeds the ward model; claims are checked against the rain on the claim date.
6. **"Why would insurers share data?"** They don't have to. Day one runs without their data. Pilot = deploy inside their environment, shadow mode on closed claims, only metrics leave (DPDP-friendly). Roadmap: federated learning across insurers.
7. **"Can't someone copy it with an LLM and public maps?"** The code, yes. Not quickly: the hand-mapped, sourced flood labels from 8 real events, the held-out validation, and — once insurers join — their claims data. We say this plainly.
8. **"Japanese methods are expensive."** They live in the government Flood Planner as one module, not the headline.
9. **"Why isn't it IoT?"** Because the problem is *information asymmetry* when buying, selling and insuring land — a data problem. Sensors would be a later labels-collection layer.
10. **"Business model / funding?"** Per-report (₹299 customer, ₹499 per agent client report — proposed), insurer/bank API + platform fee. Funding goes to data, compute, and an insurer pilot — not hardware.

## The lake-buffer answer (the Hyderabad hook)
For any address SETHU shows the nearest tank, HYDRAA/TGRAC's satellite status for it (Live / Partially / Totally Encroached, 2014 vs 2023), the HMDA notification record and a link to HMDA's official FTL map PDF. We say plainly: it is a satellite classification and a lookup aid, not a legal buffer check.

## One more honest number
Against the 23 official inundation spots, 43% fall in our top-quartile wards (25% by chance), 57% in the top 40%. Many spots are underpasses and junctions that a ward-level terrain model cannot see — which is exactly why the official spot list is scored alongside the model.

## Known limits (state them first)
* Ward-level model; lake distance, terrain pocket and facilities are indicators, not validated predictions.
* OpenStreetMap lake outlines are not legal FTL boundaries. Facility coverage varies.
* Rain archive is a coarse grid: it shows ~80–90 mm for the Oct-2020 night versus the 192 mm reference — use it as an evidence tier.
* Rain→depth scale is a stated assumption, not learned.
* The ClaimWatch fraud model is not part of this pitch; it was trained on a public US sample dataset.
