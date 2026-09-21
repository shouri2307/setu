# SETU retrain-v4 — progress log (READ THIS FIRST when resuming)

Branch: `retrain-v4`. Frozen demo = git tag `demo-frozen-v3.1` (do NOT modify `web/` model data or `pipeline/p3_flood.py` until a new model is verified better).
Old demo model (exact, reproducible): `archive/p3_flood_demo_v2.py` -> 63 wards flood @192mm, recall 11/18, AUC 0.596 vs the 18-ward news list.
Current repo p3_flood.py (Sep 18) is a different, worse variant (3/18, AUC 0.49); web/data was exported from the OLD one.

## Goal
Replace ad-hoc 2-dial calibration with ONE shared formula learned from several past Hyderabad floods:
P(ward floods | rainfall, terrain/drainage features). Each ward then gets a "rainfall needed to flood it".
Scope reminder (user): tool answers "what if X mm fell on every ward" (uniform rain is intended, not a flaw).

## Rules (set BEFORE looking at results)
- Labels = places named as INUNDATED in credible news/official sources (not deaths, not wall/house collapse). Presence-only: unnamed != dry.
- Validation = leave-one-event-out. Metric = AUC of predicted susceptibility vs named wards of the held-out event (+ recall at same flooded fraction). No tuning on the held-out event.
- Ship new model ONLY if held-out AUC clearly beats the old model (0.60) on the same events. Otherwise keep frozen demo + honest wording.
- Never flood 43% of city just to buy recall.

## Known facts (verified)
- Oct 13 2020: IMD Begumpet ~192-197 mm; outskirts 283-324 mm (Ghatkesar 322, Hayathnagar 294, Hastinapuram 283). Gurram Cheruvu bund breach was Oct 17-19 (2nd storm), not Oct 13.
- Several 'high confidence' 2020 labels are wall/house collapses (Hafeezpet, Balanagar, Chandrayangutta) = not inundation evidence.
- CHIRPS satellite rain useless here (70-108mm). Sentinel-1 only Oct 9 & Oct 21 2020 (weak).
- WorldCover built-up fraction per ward: AUC 0.39 vs 18 labels (flooded wards slightly LESS built-up) -> not a shortcut.
- Terrain priors vs 18 labels: elev/slope point the wrong way; only water proximity weakly helps (AUC 0.59).
- Open rain data: data.telangana.gov.in has 2022, 2023-25 sets; AIKosh has 2018 (584 AWS). No 2020 / 2016 set found. TSDPS site has no history.

## Steps / status
- [x] 0 Freeze demo (tag), archive old p3, branch created
- [x] 1 Harvest labels -> research/labels.csv (event, city_rain_mm, locality, ward_id, source_url, evidence)
- [x] 2 Build features per ward -> research/features.csv (existing + HAND/TWI from DEM + built-up + nala/drain density)
- [~] 3 Fit + leave-one-event-out eval -> research/eval.md
- [ ] 4 Verdict; if better: wire into pipeline (new p3), re-export p4-p7, keep frozen tag as fallback

## Log (newest last)
- Setup done.
- Step 1 done: research/labels.csv has 6 events (2016-09:17, 2020-10-13:16, 2023-07-27:4 low-rain, 2025-06-12:3, 2025-07-18:15, 2025-09-18:11 wards). Localities mapped to ward ids by name (ambiguous ones skipped; Nagole/LB Nagar/Boduppal/Hayathnagar/Bandlaguda are OUTSIDE the 145 wards). Presence-only labels.
- Step 2 done: research/build_features.py -> features.csv (19 feats: HAND, TWI, sinks, waterway/waterbody proximity, built-up, upstream area...). Needs pysheds (pip; patched np.in1d) + OSM waterways in research/osm_waterways.json.
- Step 3 first result (research/eval.py, leave-one-event-out AUC on 4 big events): OLD demo model @192 = 0.49 mean (coin flip); current repo p3 = 0.47; LEARNED logistic on features = 0.69-0.70 (A/B sets; per-event 0.58-0.83). Best single feats: hand_low_frac 0.67, sink_frac 0.65, waterbody_near 0.61 (area 0.65 = label-size bias, exclude).
- PLAN for wiring (step 4): learned susceptibility S -> per-ward 'rain needed to flood' R_i by monotone mapping anchored to documented extents (assumption, state it): ~3% wards @50mm (2023 low-rain), ~22% @192mm (Oct2020 ~34km2), ~60% @300mm. depth = 0.12 + k*(rain-R_i), cap 0.5. Emit same scenarios.json schema so p4-p7 + UI unchanged. Then re-export on this branch only.
- Step 3 DONE. research/train_final.py: ensemble (logistic + shallow RF, rank-averaged) LOEO AUC = 0.74 mean (2016:0.82, Oct2020:0.64, Jul2025:0.76, Sep2025:0.73). Controls: no-fit avg of 3 physical feats=0.68; shuffled labels=0.49+/-0.07; old demo model=0.49. Output: research/susceptibility.csv (S in [0,1], 1=most flood-prone). Top: Begumpet, Khairatabad, Chandanagar, Tolichowki, Balaji Nagar, Gachibowli, Langar Houz, Chintal, Uppal, Kukatpally. Sanity OK.
- CAVEATS to state honestly: presence-only news labels, 6 events, ~60 ward-mentions, locality->ward mapping by hand, features chosen a priori but 6 variants compared on same 4 test events (mild optimism), rain scale is ANCHORED to documented extents (not learned).
- NEXT: step 4 = write pipeline/p3_flood_v4.py (S -> R_i -> depth), same scenarios.json schema; re-run p4,p5,p6,p7 on this branch; verify UI.
- Step 4 DONE (branch retrain-v4): pipeline/p3_flood.py replaced by v4 (learned S -> onset rain via ANCHORS -> depth 0.12+0.0015*(rain-R), cap 0.5). p4,p5,p6 re-run OK; p6 now builds validation.json from research/labels.csv + honest limitations text; index.html legend notes 2020 map is not independent. Flood counts: 50mm:5, 100:17, 150:25, 192:29, 250:59, 300:80 (smooth, no cliff). Tested in browser: OK.
- To use new model: `git checkout retrain-v4` then `python serve.py`. Frozen demo: `git checkout demo-frozen-v3.1` (or main).
- IDEAS if more time: add more flood events to labels.csv (rerun build? no: only train_final.py -> p3..p6), inundation-only labels, per-event rain gauges.
