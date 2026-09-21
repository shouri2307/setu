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
- [ ] 2 Build features per ward -> research/features.csv (existing + HAND/TWI from DEM + built-up + nala/drain density)
- [ ] 3 Fit + leave-one-event-out eval -> research/eval.md
- [ ] 4 Verdict; if better: wire into pipeline (new p3), re-export p4-p7, keep frozen tag as fallback

## Log (newest last)
- Setup done.
- Step 1 done: research/labels.csv has 6 events (2016-09:17, 2020-10-13:16, 2023-07-27:4 low-rain, 2025-06-12:3, 2025-07-18:15, 2025-09-18:11 wards). Localities mapped to ward ids by name (ambiguous ones skipped; Nagole/LB Nagar/Boduppal/Hayathnagar/Bandlaguda are OUTSIDE the 145 wards). Presence-only labels.
