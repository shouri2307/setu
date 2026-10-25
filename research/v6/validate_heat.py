"""Heat validation: does the Landsat dry-season surface-temperature composite rank Hyderabad mandals the way the mandal weather stations (TSDPS) do?
Landsat sees surface temperature at ~10:30 local on clear days; the stations report air temperature. They are different quantities, so only a rank agreement across mandals is a fair test.
Uses: web/data/heat.json (the app's grid), research/v5/mandals_osm.geojson (mandal polygons), TSDPS weather CSVs Mar-May 2024-2026 (scene dates taken from research/v6/heat.log)."""
import json, re, sys
from pathlib import Path
import numpy as np, pandas as pd
from shapely.geometry import shape, Point
from shapely.prepared import prep
from scipy.stats import spearmanr, pearsonr
ROOT = Path(__file__).resolve().parent.parent.parent
H = json.loads((ROOT / "web/data/heat.json").read_text()); m = H["meta"]; nx, ny, cell, bb = m["nx"], m["ny"], m["cell_deg"], m["bbox"]
lst = np.array([np.nan if v is None else v / 10 for v in H["lst"]]).reshape(ny, nx)
gx = bb[0] + (np.arange(nx) + .5) * cell; gy = bb[3] - (np.arange(ny) + .5) * cell
GX, GY = np.meshgrid(gx, gy)
norm = lambda s: re.sub(r"[^A-Z_]", "", str(s).upper())
ALIAS = {"AMEENPUR": "AMEENAPUR", "BACHUPALLY": "BACHPALLE", "DUNDIGAL": "DUNDIGAL_GANDIMAISAMMA", "GOLCONDA": "GOLKONDA", "MARREDPALLY": "MAREDPALLY", "MEDCHAL": "MEDCHEL", "SERILINGAMPALLE": "SERILINGAMPALLY", "TIRUMALAGIRI": "TIRUMALGIRI"}
keys = set(pd.read_csv(ROOT / "research/v5/ward_event_rain.csv").mandal.astype(str))
polys = {}
for f in json.loads((ROOT / "research/v5/mandals_osm.geojson").read_text())["features"]:
    k = norm(f["properties"]["name"].replace(" mandal", "")); k = ALIAS.get(k, k)
    if k in keys: polys[k] = prep(shape(f["geometry"]))
mand_lst = {}
for k, pg in polys.items():
    box = pg.context.bounds; sel = (GX >= box[0]) & (GX <= box[2]) & (GY >= box[1]) & (GY <= box[3]) & np.isfinite(lst)
    pts = [(i, j) for j, i in zip(*np.where(sel)) if pg.contains(Point(GX[j, i], GY[j, i]))] if sel.any() else []
    if len(pts) >= 15: mand_lst[k] = float(np.nanmedian([lst[j, i] for i, j in pts]))
dates = sorted(set(re.findall(r"^used (\d{4}-\d{2}-\d{2})", (ROOT / "research/v6/heat.log").read_text(), flags=re.M)))
print("scene dates used:", len(dates), "| mandals with enough clear cells:", len(mand_lst), "of", len(polys))
T = []
for y, mo in sorted({(int(d[:4]), int(d[5:7])) for d in dates}):
    f = ROOT / "research/external/tgdps/monsoon" / f"w_{y}_{mo:02d}.csv"
    if not f.exists(): continue
    d = pd.read_csv(f, encoding="latin-1"); d.columns = [c.strip().lower() for c in d.columns]
    tc = [c for c in d.columns if c.startswith("max temp") or c == "temp_max"][0]
    s = d["date"].astype(str); d["dt"] = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce").fillna(pd.to_datetime(s, format="%d-%b-%y", errors="coerce"))
    d["key"] = d["mandal"].map(norm).map(lambda k: ALIAS.get(k, k)); d["tmax"] = pd.to_numeric(d[tc], errors="coerce")
    d = d[d.key.isin(mand_lst) & d.dt.dt.strftime("%Y-%m-%d").isin(dates) & d.tmax.between(15, 50)]
    dl = d["district"].astype(str).str.upper().str.replace(r"[^A-Z]", "", regex=True); d = d[dl.str.startswith(("HYDERABAD", "RANGAREDDY", "MEDCHAL", "SANGAREDDY"))]
    T.append(d[["key", "dt", "tmax"]])
T = pd.concat(T); ndays = T.dt.nunique(); tm = T.groupby(["key", "dt"]).tmax.mean().groupby("key").mean()
common = sorted(set(mand_lst) & set(tm.index)); a = np.array([mand_lst[k] for k in common]); b = np.array([tm[k] for k in common])
rho, p = spearmanr(a, b); r, pr = pearsonr(a, b)
print(f"scene dates with station data: {ndays} | mandals compared: {len(common)}")
print(f"satellite surface temperature (composite) across mandals: median {np.median(a):.1f} C, range {a.min():.1f}-{a.max():.1f} (spread {a.max()-a.min():.1f})")
print(f"station daily maximum air temperature on the same dates: median {np.median(b):.1f} C, range {b.min():.1f}-{b.max():.1f} (spread {b.max()-b.min():.1f})")
print(f"rank agreement across mandals: Spearman rho = {rho:.2f} (p = {p:.3f}) | Pearson r = {r:.2f}")
top = sorted(common, key=lambda k: -mand_lst[k])[:4]; bot = sorted(common, key=lambda k: mand_lst[k])[:4]
print("hottest by satellite:", [(k, round(mand_lst[k], 1), round(tm[k], 1)) for k in top]); print("coolest by satellite:", [(k, round(mand_lst[k], 1), round(tm[k], 1)) for k in bot])
