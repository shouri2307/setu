"""p9_wardfeat.py — export per-ward terrain/land features + SETU susceptibility to the browser."""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
f = pd.read_csv(ROOT / "research" / "features.csv")
s = pd.read_csv(ROOT / "research" / "susceptibility.csv")
d = f.merge(s, on="ward_id")
d["pct"] = d["S"].rank(pct=True)
keep = ["S", "pct", "hand_low_frac", "twi_mean", "sink_frac", "builtup_frac", "upstream_km2",
        "area_km2", "elev_mean", "elev_rel_nbrs", "waterbody_near_frac", "waterway_near_frac", "slope_pct"]
out = {int(r.ward_id): {k: round(float(r[k]), 4) for k in keep} for _, r in d.iterrows()}
(ROOT / "web" / "data" / "wardfeat.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
print(len(out), "wards written")
