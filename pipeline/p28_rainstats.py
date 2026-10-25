"""p28_rainstats.py — heavy-rain statistics per mandal for COMPLETE monsoon seasons (June-October), from the Open Data Telangana (TSDPS) daily weather files
downloaded by p29_fetch_monsoon.py (research/external/tgdps/monsoon/, 2018-2025) -> web/data/rainstats.json

Rules (each is counted and written to the output so the app can show exactly what a number rests on):
  * a file contributes only rows dated inside its own month (some files carry stray days from other months)
  * where a mandal has several stations per day (2018 files list each weather station), the mandal's daily value is the MEAN of its stations; duplicate
    mandal-day rows in other years are averaged the same way
  * negative values, and values above 600 mm in a day, are dropped and counted
  * a mandal-year counts only if ALL FIVE months (Jun-Oct) have at least 90% of their days for that mandal; otherwise that year is excluded for that mandal
  * heavy rain = a rain-day above 64.5 mm (the IMD heavy-rain lower bound); a rain-day runs 08:30 to 08:30 IST
Consistency check against the older event-month files is printed (same agency, different dataset).
Run: .venv/Scripts/python pipeline/p28_rainstats.py"""
import json, re, calendar
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "research" / "external" / "tgdps" / "monsoon"
THR, FULL = 64.5, 0.90
YEARS = range(2018, 2026); MONTHS = (6, 7, 8, 9, 10)
norm = lambda s: re.sub(r"[^A-Z_]", "", str(s).upper())
ALIAS = {"AMEENPUR": "AMEENAPUR", "BACHUPALLY": "BACHPALLE", "DUNDIGAL": "DUNDIGAL_GANDIMAISAMMA", "GOLCONDA": "GOLKONDA", "MARREDPALLY": "MAREDPALLY", "MEDCHAL": "MEDCHEL",
         "SERILINGAMPALLE": "SERILINGAMPALLY", "TIRUMALAGIRI": "TIRUMALGIRI", "MAHESWARAM": "MAHESHWARAM", "HATHNOORA": "HATHANOORA", "CHOUTKUR": "CHOWTAKUR", "NANDIGAMA": "NANDIGAM"}
keys = sorted(set(pd.read_csv(ROOT / "research/v5/ward_event_rain.csv").mandal.astype(str)))
DISTRICTS = ("HYDERABAD", "RANGAREDDY", "RANGA REDDY", "MEDCHAL", "SANGAREDDY", "MEDAK", "VIKARABAD")

def read(y, m):
    d = pd.read_csv(SRC / f"w_{y}_{m:02d}.csv", encoding="latin-1"); d.columns = [c.strip().lower() for c in d.columns]
    rc = next(c for c in d.columns if c.startswith(("rain", "cumm")))
    s = d["date"].astype(str).str.strip()
    dt = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce").fillna(pd.to_datetime(s, format="%d-%b-%y", errors="coerce"))
    x = pd.DataFrame({"district": d["district"].astype(str).str.upper().str.strip(), "key": d["mandal"].map(norm), "date": dt, "rain": pd.to_numeric(d[rc], errors="coerce")})
    n0 = len(x); x = x[x.date.notna()]
    stray = int(((x.date.dt.year != y) | (x.date.dt.month != m)).sum()); x = x[(x.date.dt.year == y) & (x.date.dt.month == m)]
    x["key"] = x["key"].map(lambda k: ALIAS.get(k, k))
    dl = x.district.str.replace(r"[^A-Z]", "", regex=True)          # "MEDCHAL-MALKAJGIRI", "Medchal Malkajgiri", "RANGA REDDY" ... all match by their leading name
    x = x[dl.str.startswith(tuple(re.sub(r"[^A-Z]", "", d) for d in DISTRICTS)) & x.key.isin(keys)]
    neg = int((x.rain < 0).sum()); big = int((x.rain > 600).sum()); x = x[(x.rain >= 0) & (x.rain <= 600)]
    multi = int(x.duplicated(["key", "date"]).sum())
    x = x.groupby(["key", "date"], as_index=False).rain.mean()
    return x, dict(rows=n0, stray=stray, neg=neg, big=big, multi=multi)

frames, qc = [], {}
for y in YEARS:
    for m in MONTHS:
        x, q = read(y, m); frames.append(x.assign(y=y, m=m)); qc[f"{y}-{m:02d}"] = q
R = pd.concat(frames, ignore_index=True)
print("rows kept:", len(R), "| stray out-of-month rows dropped:", sum(q["stray"] for q in qc.values()), "| negative:", sum(q["neg"] for q in qc.values()), "| >600 mm:", sum(q["big"] for q in qc.values()),
      "| duplicate mandal-days (station means):", sum(q["multi"] for q in qc.values()))
mdays = lambda y, m: calendar.monthrange(y, m)[1]
out, excl_total = {}, 0
for k in keys:
    g = R[R.key == k]; per_year = []; excl = []
    for y in YEARS:
        gy = g[g.y == y]
        cov = [gy[gy.m == m].date.nunique() / mdays(y, m) for m in MONTHS]
        if min(cov) < FULL: excl.append([y, round(min(cov), 2)]); continue
        per_year.append([y, int((gy.rain > THR).sum()), round(float(gy.rain.sum()), 1), round(float(gy.rain.max()), 1)])
    if not per_year: continue
    gq = g[g.y.isin([p[0] for p in per_year])].sort_values("rain", ascending=False)
    over = [p[1] for p in per_year]; w = gq.iloc[0]
    out[k] = {"per_year": per_year, "years": [p[0] for p in per_year], "mean_over": round(float(np.mean(over)), 2), "min_over": int(min(over)), "max_over": int(max(over)),
              "mean_season_mm": round(float(np.mean([p[2] for p in per_year])), 0), "wettest": [round(float(w.rain), 1), str(w.date.date())],
              "top": [[str(d.date()), round(float(v), 1)] for d, v in zip(gq[gq.rain > THR].date.head(8), gq[gq.rain > THR].rain.head(8))], "excluded_years": excl}
    excl_total += len(excl)
meta = {"source": "Open Data Telangana (TSDPS) mandal-level daily weather files, June-October of 2018-2025", "licence": "non-commercial", "threshold_mm": THR, "scope": "complete monsoon seasons (June-October) only",
        "min_month_coverage": FULL, "years_considered": [min(YEARS), max(YEARS)], "day_convention": "08:30 to 08:30 IST",
        "aggregation": "where a mandal lists several stations per day (2018) the mandal value is the mean of its stations",
        "cleaning": {"stray_out_of_month_rows": sum(q["stray"] for q in qc.values()), "negative": sum(q["neg"] for q in qc.values()), "over_600mm": sum(q["big"] for q in qc.values()), "duplicate_mandal_days_averaged": sum(q["multi"] for q in qc.values())},
        "not_included": "2016 (file ends in September) and 2017 (different layout) are not used; 2026 is incomplete (October still running)"}
(ROOT / "web" / "data" / "rainstats.json").write_text(json.dumps({"meta": meta, "mandals": out}, separators=(",", ":")), encoding="utf-8")
ny = [len(v["years"]) for v in out.values()]; mo = [v["mean_over"] for v in out.values()]
print(f"mandals {len(out)} of {len(keys)} | complete seasons per mandal: min {min(ny)}, median {int(np.median(ny))}, max {max(ny)} | mandal-years excluded for low coverage: {excl_total}")
print(f"heavy days per monsoon: mean across mandals {np.mean(mo):.1f} (min {min(mo):.1f}, max {max(mo):.1f})")
# consistency with the older event-month dataset (same agency, a different file series). Like with like: same district rule, and only months where the old
# file is complete (the old 2025 files carry stray one-day placeholder rows of 0 mm, which were already found unreliable and are excluded from every statistic)
import sys; sys.path.insert(0, str(ROOT / "research" / "v5")); from load_mandal_rain import load
old = load(); old["key"] = old.mandal.map(norm).map(lambda k: ALIAS.get(k, k)); old = old[old.key.isin(keys)]
old = old[old.district.str.replace(r"[^A-Z]", "", regex=True).str.startswith(tuple(re.sub(r"[^A-Z]", "", d) for d in DISTRICTS))]
old["ym"] = old.date.dt.to_period("M"); nd = old.groupby(["key", "ym"]).date.transform("nunique"); old = old[nd >= old.ym.map(lambda p: calendar.monthrange(p.year, p.month)[1]) * FULL]
old = old.groupby(["key", "date"], as_index=False).rain.mean()
new = R.assign(date=pd.to_datetime(R.date))[["key", "date", "rain"]]; j = old.merge(new, on=["key", "date"], suffixes=("_old", "_new")); dd = (j.rain_old - j.rain_new).abs()
print(f"cross-dataset check on {len(j):,} shared mandal-days (same districts, complete old months): within 0.1 mm for {100 * (dd <= 0.1).mean():.1f}% | differ by >5 mm on {int((dd > 5).sum())} | max abs difference {dd.max():.1f} mm | correlation {np.corrcoef(j.rain_old, j.rain_new)[0, 1]:.4f}")
heavy_old = int((j.rain_old > THR).sum()); heavy_new = int((j.rain_new > THR).sum()); print(f"heavy days (>{THR} mm) on the shared days: old file {heavy_old}, new file {heavy_new}")
