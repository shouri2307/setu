"""p21_gw_quality.py — Telangana Ground Water Department pre/post-monsoon water-quality samples (2018-2025) -> web/data/gwquality.json
Column names change between years, so parameters are matched by pattern. lat/long are swapped in some files (fixed) and
implausible positions are dropped. Values are lab results for ONE well on ONE date; they do not describe a plot's own borewell.
Indian drinking-water standard (BIS IS 10500) reference limits used in the app: fluoride 1.0 (acceptable) / 1.5 mg/L (permissible),
nitrate 45 mg/L, TDS 500 (acceptable) / 2000 mg/L (permissible), pH 6.5-8.5.   Run: .venv/Scripts/python pipeline/p21_gw_quality.py"""
import json, re, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "research" / "external" / "groundwater"
def pick(cols, *pats):
    for p in pats:
        for c in cols:
            if re.fullmatch(p, c.strip(), flags=re.I): return c
    return None
rows, log = [], []
for f in sorted(SRC.glob("quality_*.csv")):
    d = pd.read_csv(f, encoding="utf-8-sig"); cols = list(d.columns)
    yr = int(re.search(r"(20\d\d)", f.name).group(1)); seas = "pre" if f.name.startswith("quality_pre") else "post"
    m = dict(dist=pick(cols, r"district"), mand=pick(cols, r"mandal"), vill=pick(cols, r"village"), lat=pick(cols, r"lat_gis", r"latitude", r"lat"),
             lon=pick(cols, r"long_gis", r"longitude", r"long"), ph=pick(cols, r"ph"), tds=pick(cols, r"tds"), f=pick(cols, r"f", r"fluoride"),
             no3=pick(cols, r"no3", r"no_3.*", r"nitrate"), cl=pick(cols, r"cl", r"cl -"), aq=pick(cols, r"principalaquifer"))
    if m["lat"] is None or m["lon"] is None or m["tds"] is None: log.append((f.name, "skipped: missing " + str([k for k in ("lat", "lon", "tds") if m[k] is None]))); continue
    x = pd.DataFrame({"district": d[m["dist"]], "mandal": d[m["mand"]], "village": d[m["vill"]], "lat": pd.to_numeric(d[m["lat"]], errors="coerce"),
                      "lon": pd.to_numeric(d[m["lon"]], errors="coerce"), "ph": pd.to_numeric(d[m["ph"]], errors="coerce") if m["ph"] else np.nan,
                      "tds": pd.to_numeric(d[m["tds"]], errors="coerce"), "f": pd.to_numeric(d[m["f"]], errors="coerce") if m["f"] else np.nan,
                      "no3": pd.to_numeric(d[m["no3"]], errors="coerce") if m["no3"] else np.nan, "cl": pd.to_numeric(d[m["cl"]], errors="coerce") if m["cl"] else np.nan,
                      "aquifer": d[m["aq"]] if m["aq"] else ""})
    sw = (x.lat > 30) & (x.lon < 30); x.loc[sw, ["lat", "lon"]] = x.loc[sw, ["lon", "lat"]].values
    ok = x.lat.between(15.5, 20) & x.lon.between(77, 82); n_bad = int((~ok).sum()); x = x[ok]
    x["year"] = yr; x["season"] = seas; rows.append(x); log.append((f.name, f"{len(x)} samples, swapped {int(sw.sum())}, bad position {n_bad}, F {int(x.f.notna().sum())}, NO3 {int(x.no3.notna().sum())}"))
Q = pd.concat(rows, ignore_index=True)
# physical sanity: remove impossible lab values
Q.loc[(Q.f < 0) | (Q.f > 20), "f"] = np.nan; Q.loc[(Q.no3 < 0) | (Q.no3 > 1500), "no3"] = np.nan
Q.loc[(Q.tds < 0) | (Q.tds > 30000), "tds"] = np.nan; Q.loc[(Q.ph < 3) | (Q.ph > 12), "ph"] = np.nan
for l in log: print("  ", l)
print("total samples", len(Q), "| years", sorted(Q.year.unique()))
H = Q[Q.lat.between(17.2, 17.65) & Q.lon.between(78.2, 78.7)]
print("Hyderabad-area samples:", len(H), "| latest year", int(H.year.max()), "| samples in latest 3 years", int((H.year >= H.year.max() - 2).sum()))
print("Hyderabad-area, 2023-2025: fluoride >1.5 mg/L: %.0f%% | nitrate >45: %.0f%% | TDS >2000: %.0f%% | TDS >500: %.0f%%" % tuple(100 * ((H[H.year >= 2023][c] > lim).sum() / max(H[H.year >= 2023][c].notna().sum(), 1)) for c, lim in (("f", 1.5), ("no3", 45), ("tds", 2000), ("tds", 500))))
R = Q[Q.year >= 2021].copy()
out = [[round(float(r.lat), 5), round(float(r.lon), 5), str(r.village)[:40], str(r.mandal)[:30], int(r.year), r.season,
        None if pd.isna(r.tds) else round(float(r.tds)), None if pd.isna(r.f) else round(float(r.f), 2), None if pd.isna(r.no3) else round(float(r.no3), 1),
        None if pd.isna(r.ph) else round(float(r.ph), 2), None if pd.isna(r.cl) else round(float(r.cl)), str(r.aquifer)[:30] if isinstance(r.aquifer, str) else ""] for r in R.itertuples()]
meta = {"source": "Telangana Ground Water Department pre/post-monsoon water quality (Open Data Telangana), 2021-2025", "fields": ["lat", "lon", "village", "mandal", "year", "season", "tds_mgl", "fluoride_mgl", "nitrate_mgl", "ph", "chloride_mgl", "aquifer"],
        "limits": {"fluoride": [1.0, 1.5], "nitrate": 45, "tds": [500, 2000], "ph": [6.5, 8.5]}}
(ROOT / "web" / "data" / "gwquality.json").write_text(json.dumps({"meta": meta, "samples": out}, separators=(",", ":")), encoding="utf-8")
print("written samples (2021+):", len(out))
