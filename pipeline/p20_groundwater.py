"""p20_groundwater.py — clean the Telangana Ground Water Department monthly level files (research/external/groundwater)
and write per-station seasonal summaries to web/data/groundwater.json.

Cleaning rules (all counted and printed):
  * two date formats exist (dd/mm/yy in 2021-23 files, dd/mm/yyyy from 2024) — both parsed, anything else dropped
  * BOM / stray unnamed columns dropped; station id = district|mandal|village|lat|long
  * a reading is removed if missing, negative, > 120 m, or it jumps > 25 m from the same station's previous month and back
  * exact duplicate (station, month) rows collapsed to the median
Per station: latest reading, pre-monsoon (Apr-May) and post-monsoon (Oct-Nov) mean depth, post-monsoon recovery
(pre minus post: positive = water table rose after the rains), trend in m/yr (annual-mean slope, 2021-2025, needs >=4 years), months of data.
Depths are metres below ground level (m bgl): LARGER = DEEPER = worse.
Run: .venv/Scripts/python pipeline/p20_groundwater.py"""
import json, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "research" / "external" / "groundwater"
rows = []
for f in sorted(SRC.glob("level__*.csv")):
    d = pd.read_csv(f, encoding="utf-8-sig"); d.columns = [c.strip().lower() for c in d.columns]
    d = d[["district", "mandal", "village", "lat", "long", "date", "value"]]; rows.append(d)
G = pd.concat(rows, ignore_index=True); n0 = len(G)
s = G["date"].astype(str).str.strip()
dt = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce").fillna(pd.to_datetime(s, format="%d/%m/%y", errors="coerce"))
G["date"] = dt; bad_date = int(G.date.isna().sum()); G = G.dropna(subset=["date"])
for c in ("lat", "long", "value"): G[c] = pd.to_numeric(G[c], errors="coerce")
# lat/long are swapped in some files (lat ~81, long ~17): swap them back
swapped = (G.lat > 30) & (G["long"] < 30); n_swap = int(swapped.sum())
G.loc[swapped, ["lat", "long"]] = G.loc[swapped, ["long", "lat"]].values
n_nocoord = int((G.lat.isna() | G["long"].isna()).sum())
bad_val = int((G.value.isna() | (G.value < 0) | (G.value > 120)).sum()); G = G[G.value.between(0, 120)]
for c in ("district", "mandal", "village"): G[c] = G[c].astype(str).str.strip()
# station = district|mandal|village (a village can carry several wells, marked (D)/(S)/(M) in the name).
# Its coordinate = median of the readings that carry a full-precision (>=4 decimals) position, else any valid position.
G["sid"] = G.district.str.upper() + "|" + G.mandal.str.upper() + "|" + G.village.str.upper()
okc = G.lat.between(15.5, 20) & G["long"].between(77, 82)
dec = lambda x: x.round(6).map(lambda v: len(repr(v).split(".")[-1]) if v == v else 0)
G["prec"] = np.where(okc, np.minimum(dec(G.lat), dec(G["long"])), -1)
def best_xy(g):
    h = g[g.prec >= 4]; h = h if len(h) else g[g.prec >= 0]
    return pd.Series({"lat": h.lat.median() if len(h) else np.nan, "long": h["long"].median() if len(h) else np.nan, "hiprec": int(len(g[g.prec >= 4]) > 0)})
xy = G.groupby("sid").apply(best_xy)
G = G.drop(columns=["lat", "long"]).join(xy, on="sid"); G = G.dropna(subset=["lat", "long"])
n_lowprec = int((xy.hiprec == 0).sum())
G["ym"] = G.date.dt.to_period("M")
dups = int(G.duplicated(["sid", "ym"]).sum())
G = G.groupby(["sid", "ym"], as_index=False).agg(district=("district", "first"), mandal=("mandal", "first"), village=("village", "first"), lat=("lat", "first"), long=("long", "first"), value=("value", "median"))
G = G.sort_values(["sid", "ym"]); prev = G.groupby("sid").value.shift(1); nxt = G.groupby("sid").value.shift(-1)
spike = ((G.value - prev).abs() > 25) & ((G.value - nxt).abs() > 25); n_spike = int(spike.sum()); G = G[~spike]
print(f"swapped lat/long rows fixed {n_swap:,} | rows with no coordinate on the row {n_nocoord:,} (filled from the station's other months) | stations with only low-precision coordinates {n_lowprec}")
G["y"] = G.ym.dt.year; G["m"] = G.ym.dt.month
print(f"rows read {n0:,} | bad/unparsed dates {bad_date:,} | out-of-range or missing values {bad_val:,} | duplicate station-months collapsed {dups:,} | spikes removed {n_spike}")
print(f"clean rows {len(G):,} | stations {G.sid.nunique()} | months {G.ym.min()}..{G.ym.max()}")
# position QC: drop stations whose coordinate is a placeholder or cannot be right
pos = G.drop_duplicates("sid")[["sid", "district", "lat", "long"]].copy()
pos["key"] = pos.lat.round(3).astype(str) + "," + pos["long"].round(3).astype(str)
shared = pos.groupby("key").sid.transform("nunique") >= 2                      # two different stations on exactly the same point
hyd = pos.district.str.upper().eq("HYDERABAD") & ~(pos.lat.between(17.30, 17.52) & pos["long"].between(78.30, 78.62))
dmed = pos.groupby("district")[["lat", "long"]].transform("median")
far = (np.hypot((pos.lat - dmed.lat) * 111, (pos["long"] - dmed["long"]) * 106) > 90)
badpos = set(pos[shared | hyd | far].sid); G = G[~G.sid.isin(badpos)]
print(f"stations dropped for suspect position: {len(badpos)} (shared placeholder point {int(shared.sum())}, Hyderabad district outside the city {int(hyd.sum())}, >90 km from own district {int(far.sum())})")
out = []
for sid, g in G.groupby("sid"):
    latest = g.iloc[-1]
    pre = g[g.m.isin([4, 5])].groupby("y").value.mean(); post = g[g.m.isin([10, 11])].groupby("y").value.mean()
    ann = g.groupby("y").value.agg(["mean", "count"]); ann = ann[(ann["count"] >= 10) & ann.index.isin(range(2021, 2026))]
    trend = float(np.polyfit(ann.index.values, ann["mean"].values, 1)[0]) if len(ann) >= 4 else None
    rec = float(pre.mean() - post.mean()) if len(pre) and len(post) else None
    out.append([round(float(latest.lat), 5), round(float(latest["long"]), 5), latest.village, latest.mandal, latest.district,
                round(float(latest.value), 2), str(latest.ym), None if not len(pre) else round(float(pre.mean()), 2), None if not len(post) else round(float(post.mean()), 2),
                None if rec is None else round(rec, 2), None if trend is None else round(trend, 3), int(len(g)), int(g.y.min()), int(g.y.max())])
# renamed stations (e.g. Jagadevpur / Jagdevpur) appear twice at the same point: keep the one with more months of data
out.sort(key=lambda r: -r[11]); seen = set(); dedup = []
for r_ in out:
    k = (round(r_[0], 3), round(r_[1], 3))
    if k in seen: continue
    seen.add(k); dedup.append(r_)
print(f"merged {len(out) - len(dedup)} renamed duplicate stations at the same point"); out = dedup
meta = {"source": "Telangana Ground Water Department via Open Data Telangana (monthly water level, m below ground level)",
        "fields": ["lat", "lon", "village", "mandal", "district", "latest_m", "latest_month", "pre_m", "post_m", "recovery_m", "trend_m_per_yr", "months", "first_year", "last_year"],
        "notes": "larger depth = deeper water table = worse; recovery = pre minus post (positive = rose after monsoon); trend = annual-mean slope 2021-2025 (positive = deepening)",
        "cleaning": {"rows_read": n0, "bad_dates": bad_date, "bad_values": bad_val, "duplicates": dups, "spikes": n_spike, "swapped_latlon_rows_fixed": n_swap, "rows_without_coordinates": n_nocoord, "stations_low_precision_coords": n_lowprec, "stations_dropped_suspect_position": len(badpos)}}
(ROOT / "web" / "data" / "groundwater.json").write_text(json.dumps({"meta": meta, "stations": out}, separators=(",", ":")), encoding="utf-8")
st = pd.DataFrame(out, columns=meta["fields"])
H = st[st.lat.between(17.2, 17.65) & st.lon.between(78.2, 78.7)]
print(f"stations written {len(st)} | Hyderabad box {len(H)} | with trend {int(st.trend_m_per_yr.notna().sum())} | with recovery {int(st.recovery_m.notna().sum())}")
print("Hyderabad box: latest depth median %.1f m (p10 %.1f, p90 %.1f) | trend median %+.2f m/yr | recovery median %+.1f m" % (H.latest_m.median(), H.latest_m.quantile(.1), H.latest_m.quantile(.9), H.trend_m_per_yr.median(), H.recovery_m.median()))
print("statewide: latest median %.1f m | trend median %+.2f m/yr | share deepening >0.3 m/yr: %.0f%%" % (st.latest_m.median(), st.trend_m_per_yr.median(), 100 * (st.trend_m_per_yr > 0.3).sum() / st.trend_m_per_yr.notna().sum()))
