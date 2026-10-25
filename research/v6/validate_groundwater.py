import pandas as pd, numpy as np, glob, re, json
from pathlib import Path
R = Path("research/external/groundwater")
rows = []
for f in sorted(R.glob("level__*.csv")):
    try: d = pd.read_csv(f, encoding="latin-1")
    except Exception as e: print("ERR", f.name, e); continue
    d.columns = [c.strip().lower() for c in d.columns]; d["file"] = f.name; rows.append(d)
G = pd.concat(rows, ignore_index=True)
print("files", len(rows), "rows", len(G), "cols", [c for c in G.columns if c != "file"])
G["date"] = pd.to_datetime(G["date"], format="%d/%m/%Y", errors="coerce")
print("date NaT:", G.date.isna().sum(), "| range", G.date.min().date(), G.date.max().date())
print("units:", G.units.value_counts().to_dict())
G["value"] = pd.to_numeric(G["value"], errors="coerce")
print("value NaN:", G.value.isna().sum(), "| negative:", (G.value < 0).sum(), "| >100:", (G.value > 100).sum(), "| describe:", G.value.describe().round(1).to_dict())
G["sid"] = G.district.str.upper() + "|" + G.mandal.str.upper() + "|" + G.village.str.upper() + "|" + G.lat.round(4).astype(str) + "|" + G["long"].round(4).astype(str)
print("distinct stations:", G.sid.nunique(), "| rows per month (median):", int(G.groupby(G.date.dt.to_period("M")).size().median()))
dup = G.duplicated(["sid", "date"]).sum(); print("duplicate (station,date):", dup)
per = G.groupby("sid").date.nunique(); print("months per station: median", int(per.median()), "min", per.min(), "max", per.max(), "| stations with <24 months:", (per < 24).sum())
mm = G.groupby(G.date.dt.to_period("M")).sid.nunique(); print("months with station count <1500:", mm[mm < 1500].to_dict())
bad = G[(G.lat < 15.8) | (G.lat > 19.95) | (G["long"] < 77.2) | (G["long"] > 81.8)]; print("coords outside Telangana box:", bad.sid.nunique(), "stations")
# stations with jumpy series (|month-to-month change| > 25 m)
G = G.sort_values(["sid", "date"]); G["dv"] = G.groupby("sid").value.diff().abs(); print("month-to-month jumps >25 m:", int((G.dv > 25).sum()), "rows,", G[G.dv > 25].sid.nunique(), "stations")
# Hyderabad area coverage
H = G[(G.lat.between(17.2, 17.65)) & (G["long"].between(78.2, 78.7))]
print("Hyderabad box stations:", H.sid.nunique(), "| by district:", H.drop_duplicates("sid").district.value_counts().to_dict())
st = H.drop_duplicates("sid")[["sid", "lat", "long"]]
# coverage vs the 145 ward centroids
z = json.load(open("web/data/zones.json"))["wards"]
cx = np.array([[np.mean([p[1] for r in w["rings"] for p in r]), np.mean([p[0] for r in w["rings"] for p in r])] for w in z])
def hav(a, b, c, d):
    R_ = 6371000; p1, p2 = np.radians(a), np.radians(c); dp = p2 - p1; dl = np.radians(d - b)
    x = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2; return 2 * R_ * np.arcsin(np.sqrt(x))
dmin = np.array([hav(c[0], c[1], st.lat.values, st["long"].values).min() for c in cx])
print("ward centroid -> nearest station (m): median %.0f, p90 %.0f, max %.0f | wards with a station within 2 km: %d/145, within 5 km: %d/145" % (np.median(dmin), np.percentile(dmin, 90), dmin.max(), (dmin <= 2000).sum(), (dmin <= 5000).sum()))
# seasonal summaries
G["m"] = G.date.dt.month; G["y"] = G.date.dt.year
pre = G[G.m.isin([4, 5])].groupby(["sid", "y"]).value.mean().groupby("sid").mean()
post = G[G.m.isin([10, 11])].groupby(["sid", "y"]).value.mean().groupby("sid").mean()
print("stations with both pre (Apr-May) and post (Oct-Nov) means:", len(pre.index.intersection(post.index)))
G.to_pickle("research/external/groundwater/_all.pkl")
