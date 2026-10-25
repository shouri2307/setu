"""Per-ward, per-event rainfall from Open Data Telangana mandal-level daily rainfall -> research/v5/ward_event_rain.csv

Mandal polygons: OpenStreetMap (research/v5/mandals_osm.geojson, admin_level 6). Each ward takes the rainfall of the
mandal containing its centroid (wards that fall in a mandal with no rainfall record take the nearest mandal that has one).
Event windows follow the IMD/TGDPS day convention (a day's total is 08:30 the previous day -> 08:30), so an evening storm on
date D shows up on D+1:
  ev_rain_mm  = rain on D and D+1          peak_day_mm = max single day in D-1..D+1
  ant_rain_mm = rain on D-5..D-1 (wet ground before the storm)
  rain_rel    = ward ev_rain / mean ev_rain over all 145 wards (the spatial footprint of THIS storm; ~1 for city-wide storms)
Source licence is NON-COMMERCIAL (Open Government Licence India, TSDPS).
"""
import sys, re, json
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import shape
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "research" / "v5"))
from load_mandal_rain import load

EVENT_DATE = {'2016-09': '2016-09-23', '2020-10-13': '2020-10-13', '2021-07-14': '2021-07-14', '2023-07-27': '2023-07-27',
              '2025-06-12': '2025-06-12', '2025-07-18': '2025-07-18', '2025-09-18': '2025-09-18', '2026-06-09': '2026-06-09'}
ALIAS = {'AMEENPUR': 'AMEENAPUR', 'BACHUPALLY': 'BACHPALLE', 'DUNDIGAL': 'DUNDIGAL_GANDIMAISAMMA', 'GOLCONDA': 'GOLKONDA',
         'MARREDPALLY': 'MAREDPALLY', 'MEDCHAL': 'MEDCHEL', 'SERILINGAMPALLE': 'SERILINGAMPALLY', 'TIRUMALAGIRI': 'TIRUMALGIRI',
         'MAHESWARAM': 'MAHESHWARAM', 'HATHNOORA': 'HATHANOORA', 'CHOUTKUR': 'CHOWTAKUR', 'NANDIGAMA': 'NANDIGAM'}
norm = lambda s: re.sub(r'[^A-Z_]', '', s.upper().replace(' MANDAL', '').replace('(M)', '').strip())

r = load()
r["key"] = r.mandal.map(norm)
r = r[r.district.isin(['HYDERABAD', 'RANGAREDDY', 'MEDCHAL-MALKAJGIRI', 'MEDCHAL_MALKAJGIRI', 'MEDCHAL MALKAJGIRI', 'SANGAREDDY', 'MEDAK', 'VIKARABAD'])]
have = set(r.key)

fc = json.loads((ROOT / "research/v5/mandals_osm.geojson").read_text(encoding="utf-8"))
mrows = []
for f in fc["features"]:
    k = norm(f["properties"]["name"]); k = ALIAS.get(k.replace('_', ''), ALIAS.get(k, k))
    mrows.append({"key": k, "geometry": shape(f["geometry"])})
mand = gpd.GeoSeries([x["geometry"] for x in mrows], crs="EPSG:4326")
mand_key = [x["key"] for x in mrows]
M = "EPSG:32644"
mand_m = mand.to_crs(M)

wards = gpd.read_file(ROOT / "data" / "zones_enriched.geojson").set_crs("EPSG:4326", allow_override=True)
wards["ward_id"] = wards.zone_id.astype(int)
cent = wards.to_crs(M).geometry.centroid
usable = [i for i, k in enumerate(mand_key) if k in have]

assign, how = {}, {}
for wid, c in zip(wards.ward_id, cent):
    inside = [i for i in usable if mand_m.iloc[i].contains(c)]
    if inside:
        assign[wid] = mand_key[inside[0]]; how[wid] = "inside"
    else:
        d = [(mand_m.iloc[i].distance(c), i) for i in usable]; j = min(d)[1]
        assign[wid] = mand_key[j]; how[wid] = "nearest"
print("wards mapped inside a mandal with data:", sum(v == "inside" for v in how.values()), "| nearest fallback:", sum(v == "nearest" for v in how.values()))
print("distinct mandals used:", len(set(assign.values())))

# a ward centroid can sit in a mandal polygon that has no rainfall record under any name -> reported above ('nearest')
rows = []
for ev, d in EVENT_DATE.items():
    D = pd.Timestamp(d)
    sub = r[(r.date >= D - pd.Timedelta(days=5)) & (r.date <= D + pd.Timedelta(days=1))]
    ev_r = sub[(sub.date >= D)].groupby("key").rain.sum()
    pk = sub[(sub.date >= D - pd.Timedelta(days=1))].groupby("key").rain.max()
    ant = sub[(sub.date < D)].groupby("key").rain.sum()
    for wid in wards.ward_id:
        k = assign[wid]
        rows.append({"ward_id": wid, "event": ev, "mandal": k, "ev_rain_mm": ev_r.get(k, np.nan), "peak_day_mm": pk.get(k, np.nan), "ant_rain_mm": ant.get(k, np.nan)})
out = pd.DataFrame(rows)
out["rain_rel"] = out.ev_rain_mm / out.groupby("event").ev_rain_mm.transform("mean")
print(out.groupby("event").agg(mean_ev=("ev_rain_mm", "mean"), max_ev=("ev_rain_mm", "max"), min_ev=("ev_rain_mm", "min"), nan=("ev_rain_mm", lambda s: int(s.isna().sum()))).round(1))
out.round(3).to_csv(ROOT / "research/v5/ward_event_rain.csv", index=False)
