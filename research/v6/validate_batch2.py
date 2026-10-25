"""Independent validation of batch-2 values at six real places. Uses SEPARATE code and the RAW downloads (not the processed web/data files):
  tanks   : raw TGRAC response research/gov_cache/tank_wb13.json, shapely + pyproj (UTM 44N) distances
  streams : raw TGRAC response research/gov_cache/tank_stream14.json
  rain    : raw TSDPS CSVs (event months) read directly, days > 64.5 mm per mandal
Compares with research/v6/engine_sample.json (the app's own numbers) and prints a markdown table.   python research/v6/validate_batch2.py"""
import json, re
from pathlib import Path
import numpy as np, pandas as pd
import pyproj
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import transform
ROOT = Path(__file__).resolve().parent.parent.parent
eng = json.loads((ROOT / "research/v6/engine_sample.json").read_text())
tr = pyproj.Transformer.from_crs(4326, 32644, always_xy=True).transform
prj = lambda g: transform(tr, g)
num = lambda v: (lambda s: float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else None)(str(v).strip())

# ---------- tanks from the raw response ----------
tk = json.loads((ROOT / "research/gov_cache/tank_wb13.json").read_text())
T = []
for f in tk:
    rg = (f.get("geometry") or {}).get("rings")
    if not rg or len(rg[0]) < 4: continue
    a = f["attributes"]; area, bund, vol = num(a.get("Area")), num(a.get("Bund_Heigh")), num(a.get("Volume"))
    T.append({"g": prj(Polygon(rg[0]).buffer(0)), "vol": vol if (vol and area and bund and abs(vol - area * bund / 2) / vol < .02) else None, "name": (a.get("WB_Name") or "").strip()})
ST = [(prj(LineString(p)), num(f["attributes"].get("ORDSH"))) for f in json.loads((ROOT / "research/gov_cache/tank_stream14.json").read_text()) for p in (f.get("geometry") or {}).get("paths", []) if len(p) > 1]

# ---------- rain: raw monsoon CSVs, separate and deliberately simple code ----------
M = ROOT / "research/external/tgdps/monsoon"
def raw_year_counts(key, years):
    """days > 64.5 mm per year for one mandal, read straight from the raw files (Hyderabad-area districts only, mean of duplicate rows per day)"""
    out = {}
    for y in years:
        n = 0
        for m in (6, 7, 8, 9, 10):
            d = pd.read_csv(M / f"w_{y}_{m:02d}.csv", encoding="latin-1"); d.columns = [c.strip().lower() for c in d.columns]
            rc = [c for c in d.columns if c.startswith(("rain", "cumm"))][0]
            nm = d["mandal"].astype(str).str.upper().str.replace(r"[^A-Z_]", "", regex=True)
            ds = d["district"].astype(str).str.upper().str.replace(r"[^A-Z]", "", regex=True)
            g = d[(nm == key) & (ds.str.startswith(("HYDERABAD", "RANGAREDDY", "MEDCHAL", "SANGAREDDY")))].copy()
            g["dt"] = pd.to_datetime(g["date"].astype(str), format="%Y-%m-%d", errors="coerce").fillna(pd.to_datetime(g["date"].astype(str), format="%d-%b-%y", errors="coerce"))
            g = g[(g.dt.dt.year == y) & (g.dt.dt.month == m)]
            n += int((g.groupby("dt")[rc].mean() > 64.5).sum())
        out[y] = n
    return out

rows = []
print("| place | tanks within 2 km (app / raw) | capacity Mm3 (app / raw) | nearest stream m, order (app / raw) | heavy days per monsoon, years 2018-2024 (app / raw) |")
print("|---|---|---|---|---|")
bad = []
for name, e in eng.items():
    la, lo = e["lat"], e["lon"]; p = prj(Point(lo, la))
    ins = [(t, p.distance(t["g"])) for t in T]; ins = [(t, d) for t, d in ins if d <= 2000]
    n_raw = len(ins); cap_raw = sum(t["vol"] for t, d in ins if t["vol"]) / 1e6
    sd = [(p.distance(g), o) for g, o in ST]; sd = min(sd) if sd else (None, None)
    s_app = e["stream"]; sapp = f"{s_app['d']:.0f}, {s_app['o']}" if s_app else "none <=500 m"
    sraw = f"{sd[0]:.0f}, {sd[1]:.0f}" if sd[0] is not None and sd[0] <= 500 else "none <=500 m"
    tank_ok = abs(e["tanks"]["n2"] - n_raw) <= 2 and abs(e["tanks"]["capM3"] / 1e6 - cap_raw) <= max(0.05 * cap_raw, 0.02)
    st_ok = (s_app is None and sd[0] > 500) or (s_app is not None and sd[0] is not None and abs(s_app["d"] - sd[0]) <= 25 and s_app["o"] == int(sd[1]))
    rain_txt = "n/a (outside the 145 wards)"; rain_ok = True
    if e["rain"]:
        key = re.sub(r"[^A-Z_]", "", e["rain"]["mandal"].upper()); yrs = [p[0] for p in e["rain"]["per_year"]]
        raw = raw_year_counts(key, yrs); app = {p[0]: p[1] for p in e["rain"]["per_year"]}
        rain_ok = all(app[y] == raw[y] for y in yrs); rain_txt = " ".join(f"{app[y]}/{raw[y]}" for y in yrs) + f" (mean {e['rain']['mean_over']})"
    print(f"| {name} | {e['tanks']['n2']} / {n_raw} | {e['tanks']['capM3']/1e6:.2f} / {cap_raw:.2f} | {sapp} / {sraw} | {rain_txt} |")
    if not (tank_ok and st_ok and rain_ok): bad.append((name, tank_ok, st_ok, rain_ok))
print("\nMISMATCHES:", bad if bad else "none")
