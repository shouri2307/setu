"""Per-ward features from the official GHMC / TGRAC / HYDRAA layers -> research/v5/ghmc_features.csv

These are added NEXT TO the existing terrain features (research/features.csv); nothing is overwritten.
Fixed in advance (not selected on the validation score):
  drainage block : ghmc_nala_len_km_per_km2, ghmc_nala_near_frac, drain_union_near_frac, stream11_len_km_per_km2, nala_width_mean
  tank block     : tgrac_tank_area_frac, tgrac_tank_near_frac, hy_lost_area_frac, hy_enc_built_area_frac
Deliberately NOT used: the 5 encroachment / court-case fields (all zero in the source), the 23 official inundation
points and the GHMC chronic list (both are held out as independent checks).

Run from repo root:  .venv/Scripts/python research/v5/build_ghmc_features.py
"""
import json, warnings
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent.parent
CACHE = ROOT / "research" / "gov_cache"
M = "EPSG:32644"

wards = gpd.read_file(ROOT / "data" / "zones_enriched.geojson").set_crs("EPSG:4326", allow_override=True)
ids = wards.zone_id.astype(int).tolist()
wm = wards.to_crs(M); wm.index = ids
area = (wm.geometry.area).to_dict()


def layer(n):
    return json.loads((CACHE / f"layer{n}.json").read_text(encoding="utf-8"))


def lines_gdf(feats, keep=()):
    rows = []
    for f in feats:
        for p in (f.get("geometry") or {}).get("paths") or []:
            if len(p) >= 2:
                rows.append({"geometry": LineString(p), **{k: f["attributes"].get(k) for k in keep}})
    return gpd.GeoDataFrame(rows, crs="EPSG:4326").to_crs(M)


def polys_gdf(feats):
    rows = []
    for f in feats:
        rs = (f.get("geometry") or {}).get("rings") or []
        if rs:
            p = Polygon(rs[0], rs[1:]); p = p if p.is_valid else p.buffer(0)
            rows.append({"geometry": p})
    return gpd.GeoDataFrame(rows, crs="EPSG:4326").to_crs(M)


nala = lines_gdf(layer(2))
seg = lines_gdf(layer(5), keep=("Ext_Width",))
l11 = lines_gdf(layer(11))
tg = polys_gdf(layer(13))

osm = []
for el in json.loads((ROOT / "research/osm_waterways.json").read_text(encoding="utf-8"))["elements"]:
    g = el.get("geometry")
    if g and len(g) > 1:
        osm.append(LineString([(p["lon"], p["lat"]) for p in g]))
osm = gpd.GeoSeries(osm, crs="EPSG:4326").to_crs(M)

hy = json.loads((ROOT / "web/data/hydraa_tanks.json").read_text(encoding="utf-8"))["tanks"]
hrows = []
for t in hy:
    r = t.get("rings")
    if r and len(r[0]) >= 3:
        p = Polygon([(lo, la) for la, lo in r[0]]); p = p if p.is_valid else p.buffer(0)
        hrows.append({"geometry": p, "s14": t.get("s14"), "s23": t.get("s23")})
hyg = gpd.GeoDataFrame(hrows, crs="EPSG:4326").to_crs(M)

nala_u = unary_union(list(nala.geometry)); nala_b = nala_u.buffer(300)
union_b = unary_union(list(osm) + list(nala.geometry)).buffer(300)
tg_u = unary_union(list(tg.geometry)); tg_b = tg_u.buffer(300)
lost = unary_union(list(hyg[(hyg.s14 == "L") & (hyg.s23 != "L")].geometry))
enc = unary_union(list(hyg[hyg.s23.isin(["PB", "TB"])].geometry))

# segment midpoints -> mean existing width (non-zero) per ward
seg = seg[seg.Ext_Width.fillna(0) > 0].copy()
seg["mid"] = seg.geometry.interpolate(0.5, normalized=True)
midpts = gpd.GeoDataFrame({"w": seg.Ext_Width.values}, geometry=list(seg.mid), crs=M)

f = pd.DataFrame(index=ids)
f["ghmc_nala_len_km_per_km2"] = [wm.loc[i].geometry.intersection(nala_u).length / 1000 / (area[i] / 1e6) for i in ids]
f["ghmc_nala_near_frac"] = [wm.loc[i].geometry.intersection(nala_b).area / area[i] for i in ids]
f["drain_union_near_frac"] = [wm.loc[i].geometry.intersection(union_b).area / area[i] for i in ids]
l11_idx = l11.sindex
def l11_len(g):
    hit = l11.iloc[list(l11_idx.query(g))]
    return hit.geometry.intersection(g).length.sum() / 1000
f["stream11_len_km_per_km2"] = [l11_len(wm.loc[i].geometry) / (area[i] / 1e6) for i in ids]
j = gpd.sjoin(midpts, gpd.GeoDataFrame({"ward_id": ids}, geometry=list(wm.geometry), crs=M), how="inner", predicate="within")
f["nala_width_mean"] = j.groupby("ward_id").w.mean().reindex(ids)
f["tgrac_tank_area_frac"] = [wm.loc[i].geometry.intersection(tg_u).area / area[i] for i in ids]
f["tgrac_tank_near_frac"] = [wm.loc[i].geometry.intersection(tg_b).area / area[i] for i in ids]
f["hy_lost_area_frac"] = [wm.loc[i].geometry.intersection(lost).area / area[i] for i in ids]
f["hy_enc_built_area_frac"] = [wm.loc[i].geometry.intersection(enc).area / area[i] for i in ids]
f.index.name = "ward_id"
out = ROOT / "research" / "v5" / "ghmc_features.csv"
f.round(5).to_csv(out)
print(f.describe().T[["mean", "std", "min", "max"]].round(4))
print("wards with nala width:", int(f.nala_width_mean.notna().sum()), "of", len(f))
