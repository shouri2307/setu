# SETHU — final-round pitch kit

## The line to open with
> **"SETHU is the credit score for any address in Hyderabad."**
> Type a place. In two seconds you know whether to buy it, how to price it, or how to insure it — and you can see exactly why.

Three one-liners, pick one and stick to it:
1. **"A CIBIL score for locations."** (instantly understood)
2. **"First Street's Flood Factor — but for Hyderabad, open-data, and for buyers, agents *and* insurers."** (for judges who know the field)
3. **"A health check-up for every address."** (for non-technical judges)

*Never open with "flood detection" or "flood model".* Flooding is one of eight factors. If a judge says "so it's a flood project?", answer:
"Flood is the factor we can prove — it's 22% of the score. The product is the address report built around it."

---

## Demo order: reports first, engine second, government planner last

1. **Reports first** — judges care about what a person gets, not the model. Spend most of the time here.
2. **Reveal the engine** (⚙ Engine button, 20 s) — "those were three uses; this is the one engine under them".
3. **Government planner last, as "one more thing"** (15–20 s, only if time) — it ties the story to this event's Japan theme and to the government audience, and it is the proof that the engine came from real flood science. Do **not** open with it: a rainfall slider and a colour map is exactly what looks like a normal hackathon project.

If time is short, skip the planner and use it only when a judge asks "where does the flood part come from?".

---

## The 2½-minute script (say it, then do it)

**0:00 — Hook (15 s)**
"October 2020. 192 millimetres of rain in one night. Families who had just bought plots in Hyderabad found out what they had really bought. A buyer today gets a brochure. Nobody tells them the lake is 20 metres away, the nala next door is being widened, or that the road to the hospital goes under water. We built the report that tells them."

**0:15 — Name (10 s)**
"This is **SETHU** — *bridge* in Telugu. The credit score for any address in Hyderabad. And the venue you're sitting in is already in it." → type **Cyber Gardens**, tap the first suggestion.

**0:25 — Customer report (45 s)**
- Point at the dial: "Location score around 85. And here is *why*." → the eight bars. "Flood safety is one factor. Hospital 68 metres away, metro 440 metres, schools and markets close by — all measured from this exact spot." (Skip the mall line for this venue: the nearest 'mall' in open data is an office tower.)
- Scroll to the calculator: "A family quoted ₹90 lakh. The real cost is ₹96.3 lakh with duties and brokerage — and the price meter shows ₹7,500 per square foot is *below* the area's asking band: a bargain or a warning. They know what to check before paying."

**1:10 — Real estate agent (15 s)**
Click the tab. "Same facts, different job: selling points, what buyers will push back on, and a price check against the market and the agent's own comparables."

**1:25 — Insurer (35 s)**
Click the tab → **Demo: genuine claim** (Tolichowki, 13 Oct 2020). "Claim says rain damage. 90 mm fell that day, the area is high-susceptibility, it's on the official inundation list → *fast-track*." Click **doubtful claim** (Banjara Hills, 2 Mar 2020). "No rain that day → *investigate*. This is not a fraud detector. It is evidence for the investigator, and speed for the honest customer."

**2:00 — Reveal (20 s)**
Click ⚙ **Engine**. "Those were three uses. This is the product: one engine — GHMC's nala records, HYDRAA's tank-encroachment assessment, HMDA lake notifications, 4,000 schools, 2,500 hospitals — all public data. The flood part was tested on floods it had never seen: **0.69** on held-out floods, **0.79** against GHMC's own list. Our first version scored 0.49 — a coin flip. We show that number inside the app, because trust is what an insurer pays for."

**2:20 — Business + ask (15 s)**
"Customers pay per report, agents per client, insurers and banks license the API. It runs on public data, so a new city takes days, not years. We want one insurer pilot, in shadow mode on their closed claims."

**2:35 — Close (5 s)**
"SETHU: so nobody in Hyderabad buys, sells or insures an address blind."

*(Optional +15 s if asked or time remains)* Click **Flood Planner** (from ⚙ Engine): "And for the government, the same engine drives a rainfall planner with Japanese flood-control methods — Tokyo's super levee, Nagoya's storage rule — matched to each ward's terrain."

### Stage checklist
- Open the **live site** and the **local copy** in two tabs; keep the QR (header button) ready — "check your own home on your phone".
- Pre-type nothing: typing "Cyber Gardens" live shows search works.
- Know the three numbers: **0.69 · 0.79 · 0.49**.
- Wi-Fi fails? Run the local copy (`python serve.py`): reports and calculators work with no internet. Map tiles, the rain-on-date claim check, air quality and address search need internet — keep a phone hotspot ready.

---

## Questions the jury will ask

**"Is this just a flood project?"** No — flood is 22% of an eight-factor score; the product is the address report for three customers.

**"Is it accurate?"** *Ward-level flood ranking:* AUC 0.69 on 8 unseen floods (0.5 is a coin flip), 0.79 against GHMC's own waterlogging list. *Everything else* (lake distance, facilities, terrain pocket) is an indicator from open map data and is labelled that way. Ward-level, not street-level. Prices are asking prices.

**"What about First Street / existing players?"** First Street's Flood Factor (US) is the right comparison: property-level flood score, 1–10, 30-year outlook, shown on real-estate portals — but it uses a heavy proprietary hydrodynamic model and is US-only. In India, RMSI and AIR sell pincode-level flood hazard to insurers (paid, closed), and tools like Landeed check a survey number against lake buffers. We are not the first flood-risk product. We are an open, explainable engine that serves buyers, agents *and* insurers, adds Hyderabad's own lake / nala / HYDRAA records, treats flood as one factor among eight, and publishes its own validation, including the failure.

**"Hundreds of GitHub projects predict floods."** Those are rainfall → classifier notebooks. This is an end-to-end product: type any address, get a decision, with official government records, a claim-evidence check, three audiences and honest accuracy.

**"Needs GHMC drain maps / government approval."** No. GHMC's nala network, 3,900+ drain lines, tank outlines and the 23-spot inundation list are public on the Telangana State GIS; we already use them. We state their limits (undated, nala-level encroachment blank).

**"Why would insurers share data?"** They don't have to for day one. Pilot = deploy in their environment, shadow mode on closed claims, only metrics leave. Roadmap: calibrate loadings on their claims.

**"Can someone copy it?"** The code, yes. The sourced flood labels, the held-out validation, the Hyderabad official-record integration and, later, insurer claims data are the moat.

**"Business model and funding?"** Per-report (₹299 / ₹499, proposed) plus insurer API and platform fees. About ₹5–8 lakh gets us to a first insurer pilot (estimate: hosting and commercial data plans, legal review, validation data, pilot costs) — no hardware.

**"Why not IoT?"** The problem is information asymmetry in buying, selling and insuring land — a data problem. Sensors could later improve the labels.

**"Is it live?"** Reports compute live in the browser from precomputed model outputs; rain, air quality and elevation come live from Open-Meteo.

**"What can't it do?"** Street- or parcel-level accuracy; legal FTL / buffer status (it points to the HMDA map instead); valuation (prices are asking prices); the 2026 GHMC reorganisation (it uses the earlier 145 wards).

---

## Say this / never say this
| Say | Never say |
|---|---|
| "Credit score for an address" | "Flood detection / prediction model" |
| "Water-risk rank, tested on floods it never saw" | "Predicts flooding at your street" |
| "Indicative distance to a mapped lake — verify the legal FTL with HMDA" | "This plot is / isn't in the lake buffer" |
| "Illustrative loading, to calibrate on an insurer's claims" | "Insurers should charge X%" |
| "Rain-evidence tier; triage for investigators" | "Fraud detector / catches fraud" |
| "Ward-level today; finer with insurer data" | "Street-level accuracy" |
| "Asking-price band" | "AI-estimated land price" |
| "We have not found another open product that combines these" | "Nobody has ever done this" |

## Known limits (state them before they are found)
Ward-level model · rain-to-depth is a stated assumption · facility data comes from open maps and varies (only ~15 fire stations are mapped) ·
prices are portal asking prices and some wards have none · HYDRAA status is a satellite classification, not a legal notice · the ClaimWatch
fraud model is not part of this project.
