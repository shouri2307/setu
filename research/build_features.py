"""Build per-ward terrain/drainage features -> research/features.csv
Run from repo root:  python research/build_features.py
"""
import sys, json, warnings
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio import features as rfeat
from rasterio.windows import from_bounds
from shapely.geometry import LineString
from shapely.ops import unary_union

warnings.filterwarnings("ignore")
if not hasattr(np, "in1d"):
    np.in1d = np.isin  # pysheds 0.5 vs numpy 2.x
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "pipeline"))
import config
sys.path.insert(0, str(ROOT / "research"))
import water_utils as p3

import os
DEM = os.environ.get("DEM_PATH") or str(config.RAW / "hyderabad_dem.tif")
OUT = os.environ.get("FEATURES_OUT") or str(ROOT / "research" / "features.csv")
gdf = gpd.read_file(config.DATA / "zones_enriched.geojson")
gdf = gdf.set_crs("EPSG:4326", allow_override=True)
ids = gdf.zone_id.astype(int).tolist()

# ---------- hydrology from DEM (pysheds) ----------
from pysheds.grid import Grid
grid = Grid.from_raster(DEM); dem = grid.read_raster(DEM)
filled = grid.fill_depressions(grid.fill_pits(dem))
inflated = grid.resolve_flats(filled)
fdir = grid.flowdir(inflated)
acc = grid.accumulation(fdir)
A = np.asarray(acc, dtype="float64")
stream = acc > 400                       # ~0.36 km2 contributing area
hand = np.asarray(grid.compute_hand(fdir, inflated, stream), dtype="float64")
dem_a = np.asarray(dem, dtype="float64"); fill_a = np.asarray(filled, dtype="float64")
sink = np.clip(fill_a - dem_a, 0, None)
dy, dx = 30.7, 29.5
gy, gx = np.gradient(dem_a, dy, dx)
slope = np.hypot(gx, gy)
twi = np.log((A * dx * dy / dx) / np.maximum(slope, 0.005))
transform = grid.affine
lab = rfeat.rasterize([(g, int(i)) for g, i in zip(gdf.geometry, ids)], out_shape=dem_a.shape,
                      transform=transform, fill=-1, dtype="int32")

def zstat(arr, fn):
    out = {}
    for i in ids:
        v = arr[(lab == i) & np.isfinite(arr)]
        out[i] = fn(v) if v.size else np.nan
    return out

f = pd.DataFrame(index=ids)
f["hand_mean"] = pd.Series(zstat(hand, np.mean))
f["hand_low_frac"] = pd.Series(zstat(hand, lambda v: (v < 2).mean()))
f["twi_mean"] = pd.Series(zstat(twi, np.mean))
f["sink_frac"] = pd.Series(zstat(sink, lambda v: (v > 0.3).mean()))
f["sink_depth_mean"] = pd.Series(zstat(sink, np.mean))
f["acc_log_max"] = pd.Series(zstat(A, lambda v: np.log10(v.max() + 1)))
f["relief_std"] = pd.Series(zstat(dem_a, np.std))

# ---------- existing ward attributes ----------
g2 = gdf.set_index(gdf.zone_id.astype(int))
f["elev_mean"] = g2.mean_elev; f["elev_min"] = g2.min_elev
f["slope_pct"] = g2.slope_pct; f["ponding"] = g2.ponding_fraction
f["area_km2"] = g2.area_m2 / 1e6
if os.environ.get("DEM_PATH"):
    me = zstat(dem_a, np.mean); g2["mean_elev"] = pd.Series(me); f["elev_mean"] = g2.mean_elev
mean_by_id = g2.mean_elev.to_dict()
def nbr_rel(r):
    nb = [mean_by_id[int(n)] for n in r.neighbors if int(n) in mean_by_id]
    return r.mean_elev - np.mean(nb) if nb else 0.0
f["elev_rel_nbrs"] = g2.apply(nbr_rel, axis=1)

# upstream area through flows_to chain
flows = {int(r.zone_id): (None if pd.isna(r.flows_to) else int(r.flows_to)) for r in gdf.itertuples()}
area = g2.area_m2.to_dict(); up = {i: 0.0 for i in ids}
for i in ids:
    j, hops = flows[i], 0
    while j is not None and j in up and hops < 200:
        up[j] += area[i]; j = flows[j]; hops += 1
f["upstream_km2"] = pd.Series(up) / 1e6

# ---------- water proximity (metric CRS) ----------
M = "EPSG:32644"; gm = gdf.to_crs(M); gm.index = ids
water = p3._load_water_union(M)
lines = []
for el in json.loads((ROOT / "research/osm_waterways.json").read_text())["elements"]:
    g = el.get("geometry")
    if g and len(g) > 1:
        lines.append(LineString([(p["lon"], p["lat"]) for p in g]))
ww = gpd.GeoSeries(lines, crs="EPSG:4326").to_crs(M)
ww_u = unary_union(list(ww.geometry)); ww_b = ww_u.buffer(300)
wat_b = water.buffer(300) if water is not None else None
f["waterway_len_km_per_km2"] = [gm.loc[i].geometry.intersection(ww_u).length / 1000 / (area[i] / 1e6) for i in ids]
f["waterway_near_frac"] = [gm.loc[i].geometry.intersection(ww_b).area / area[i] for i in ids]
f["waterbody_dist_m"] = [gm.loc[i].geometry.distance(water) if water is not None else np.nan for i in ids]
f["waterbody_near_frac"] = [gm.loc[i].geometry.intersection(wat_b).area / area[i] if wat_b is not None else np.nan for i in ids]

# ---------- built-up fraction (ESA WorldCover 2021) ----------
url = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N15E078_Map.tif"
with rasterio.open(url) as ds:
    w = from_bounds(*gdf.total_bounds, ds.transform); wc = ds.read(1, window=w); wtr = ds.window_transform(w)
bu = []
for g in gdf.geometry:
    m = rfeat.rasterize([(g, 1)], out_shape=wc.shape, transform=wtr, fill=0, dtype="uint8").astype(bool)
    v = wc[m]; bu.append(float((v == 50).mean()) if v.size else np.nan)
f["builtup_frac"] = bu

f.index.name = "ward_id"
f.round(4).to_csv(OUT)
print(f.describe().T[["mean", "std", "min", "max"]].round(3))
