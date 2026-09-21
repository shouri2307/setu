"""
p3_flood.py (v4) — data-driven flood model for SETU.

Two parts:

1. WHICH wards flood first  — LEARNED from history.
   research/train_final.py fits a flood-susceptibility score S per ward (0..1,
   1 = most flood-prone) from terrain/drainage features (height above nearest
   drainage, low pockets, wetness, water & nala proximity, built-up fraction,
   upstream area) using flooded localities from 6 real Hyderabad floods
   (research/labels.csv). It is validated by leave-one-event-out: trained on
   the other floods, scored on the held-out one (research/model_card.json).

2. HOW MUCH RAIN it takes    — ANCHORED to documented extents (an assumption).
   Rank wards by S. The most susceptible flood at low rain, the least at heavy
   rain. The rainfall-vs-share-of-city-flooded curve is pinned to three
   documented reference points (see ANCHORS). Depth then grows with rain above
   each ward's onset. The tool answers "what if X mm fell on every ward"
   (uniform rain is intentional, not a bug).

Reads:  research/susceptibility.csv, research/model_card.json
Writes: data/scenarios.json   (same schema as before — p4/p5/p6 unchanged)

Run from project root:  python pipeline/p3_flood.py
"""

import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

FLOOD_THRESHOLD_M = 0.12      # depth at/above which a ward counts as "flooded"
MAX_DEPTH_M = 0.5             # ward-average depths are shallow by construction
DEPTH_PER_MM = 0.0015         # extra depth per mm of rain above a ward's onset

# (share of wards flooded, rainfall mm). Linear in log(rain) between points.
#  ~3%  @  50 mm : Jul-2023 waterlogging spots after only ~50 mm
#  ~20% @ 192 mm : Oct-2020 (IMD Begumpet 192-197 mm), ~34 km2 severely inundated
#  ~55% @ 300 mm : Oct-2020 outskirts (Ghatkesar 322 mm) — widespread flooding
ANCHORS = [(0.00, 35), (0.03, 50), (0.20, 192), (0.55, 300), (1.00, 420)]

SCENARIOS_MM = sorted(set(list(range(25, 301, 25)) + [192]))


def onset_rain(S):
    """Rainfall (mm) at which each ward starts to flood, from susceptibility S."""
    order = S.sort_values(ascending=False).index          # most prone first
    q = pd.Series(np.linspace(0, 1, len(order)), index=order)
    qs = [a[0] for a in ANCHORS]
    logr = [np.log(a[1]) for a in ANCHORS]
    return pd.Series(np.exp(np.interp(q.values, qs, logr)), index=order).reindex(S.index)


def depth_at(rain_mm, R):
    d = np.minimum(MAX_DEPTH_M, FLOOD_THRESHOLD_M + DEPTH_PER_MM * (rain_mm - R))
    return d.where(rain_mm >= R, 0.0)


def main():
    print("=== SETU p3_flood v4 ===")
    sus = config.ROOT / "research" / "susceptibility.csv"
    card = config.ROOT / "research" / "model_card.json"
    if not sus.exists():
        print(f"[error] {sus} missing. Run research/build_features.py then research/train_final.py.")
        return
    S = pd.read_csv(sus, index_col="ward_id")["S"]
    mc = json.loads(card.read_text())
    R = onset_rain(S)
    print(f"[load] {len(S)} wards; onset rain range {R.min():.0f}-{R.max():.0f} mm, median {R.median():.0f} mm")

    scenarios = {}
    for r in SCENARIOS_MM:
        d = depth_at(r, R)
        scenarios[str(r)] = {str(int(z)): round(float(v), 3) for z, v in d.items() if v > 0.001}
    n192 = sum(v >= FLOOD_THRESHOLD_M for v in scenarios["192"].values())
    print(f"[check] wards flooded by rainfall:",
          ", ".join(f"{r}mm:{sum(v >= FLOOD_THRESHOLD_M for v in scenarios[str(r)].values())}"
                    for r in (25, 50, 100, 150, 192, 250, 300)))

    out = {
        "params": {
            "model": "v4 data-driven susceptibility + anchored rainfall onset",
            "flood_threshold_m": FLOOD_THRESHOLD_M,
            "depth_per_mm_above_onset": DEPTH_PER_MM,
            "max_depth_m": MAX_DEPTH_M,
            "rain_anchors_share_mm": ANCHORS,
            "calibrated_against": "6 Hyderabad floods: Sep-2016, Oct-2020, Jul-2023, Jun/Jul/Sep-2025",
            "note": "Ward ranking learned from history (leave-one-event-out AUC "
                    f"{mc['loeo_auc_mean']}); rainfall scale anchored to documented extents.",
        },
        "scenarios_mm": SCENARIOS_MM,
        "validation": {
            "rainfall_mm": 192,
            "loeo_auc_mean": mc["loeo_auc_mean"],
            "loeo_auc_by_event": mc["loeo_auc_ensemble"],
            "events_used": mc["events"],
            "flood_fraction": round(n192 / len(S), 3),
        },
        "scenarios": scenarios,
    }
    (config.DATA / "scenarios.json").write_text(json.dumps(out))
    print(f"[ok] wrote scenarios.json ({len(SCENARIOS_MM)} scenarios)")


if __name__ == "__main__":
    main()
