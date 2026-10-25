"""p22_civic_layers.py — civic/environment layers from the Lakeer open-GIS repository (Telangana/GHMC/TSPCB sources) -> web/data/civic.json
Inputs live in research/external/lakeer/. Every layer keeps its own date: several are old (power breakdowns are FY2017-18; lake/STP quality 2017; noise 2018)
and the app labels them as dated evidence rather than current conditions.
Run: .venv/Scripts/python pipeline/p22_civic_layers.py"""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "research" / "external" / "lakeer"
BOX = (17.15, 17.70, 78.15, 78.75)
def feats(f): return json.loads((R / f).read_text(encoding="utf-8"))["features"]
def pt(x, latk=None, lonk=None):
    g = x.get("geometry"); p = x["properties"]
    if g and g["type"] == "Point": return g["coordinates"][1], g["coordinates"][0]
    try: return float(p[latk]), float(p[lonk])
    except Exception: return None
def inbox(la, lo): return la is not None and BOX[0] <= la <= BOX[1] and BOX[2] <= lo <= BOX[3]
def num(v):
    try: return float(v)
    except Exception: return None
out = {"meta": {}}
# landfills / dump yards (polygons -> [lat,lon] rings)
L = []
for x in feats("landfill.geojson"):
    g = x["geometry"]; polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    rings = [[[round(c[1], 5), round(c[0], 5)] for c in poly[0]] for poly in polys]
    L.append({"name": x["properties"].get("Dumpyard"), "rings": rings})
out["landfill"] = L; out["meta"]["landfill"] = "Lakeer open-GIS 'Landfills and Dumpyards Location' (Telangana open data); undated"
# power breakdowns FY2017-18 -> 0.005 deg cells
b = pd.DataFrame([dict(lat=num(x["properties"].get("Lat")), lon=num(x["properties"].get("Long")), dur=x["properties"].get("DURATION"), volt=str(x["properties"].get("VOLTAGE")).upper(), sub=x["properties"].get("SUBSTATION")) for x in feats("breakdowns.geojson")])
b = b[b.lat.between(*BOX[:2]) & b.lon.between(*BOX[2:])].copy()
mins = pd.to_timedelta(b.dur.astype(str) + ":00", errors="coerce").dt.total_seconds() / 60
b["min"] = mins; b = b[(b["min"].isna()) | ((b["min"] >= 0) & (b["min"] < 24 * 60))]
b["ci"] = (b.lat / 0.005).round().astype(int); b["cj"] = (b.lon / 0.005).round().astype(int)
cells = b.groupby(["ci", "cj"]).agg(n=("min", "size"), med=("min", "median"), subs=("sub", "nunique")).reset_index()
out["power"] = [[round(r.ci * 0.005, 4), round(r.cj * 0.005, 4), int(r.n), None if pd.isna(r.med) else int(r.med), int(r.subs)] for r in cells.itertuples()]
out["meta"]["power"] = f"TSSPDCL/TSNPDCL feeder breakdown log, 1 Apr 2017 - 31 Mar 2018 only ({len(b)} events inside the Hyderabad box, 0.005 deg cells) — DATED, not current reliability"
# traffic choke points, junction improvement plan, flood rehabilitation centres
ch = []
for x in feats("choke.geojson"):
    p = pt(x, "Latitude", "Longitude")
    if p and inbox(*p): ch.append([round(p[0], 5), round(p[1], 5), x["properties"].get("Traffic Congestion"), x["properties"].get("Traffic PS")])
out["choke"] = ch; out["meta"]["choke"] = "Hyderabad Traffic Police congestion points (Lakeer open-GIS); undated"
jn = []
for x in feats("junctions.geojson"):
    p = pt(x, "Latitude", "Longitude")
    if p and inbox(*p): jn.append([round(p[0], 5), round(p[1], 5), x["properties"].get("Junction")])
out["junctions"] = jn; out["meta"]["junctions"] = "GHMC 'Junctions under urban improvement plan' (Lakeer open-GIS); undated"
rh = []
for x in feats("rehab.geojson"):
    p = pt(x, "Latitude", "Longitude")
    if p and inbox(*p): rh.append([round(p[0], 5), round(p[1], 5), x["properties"].get("Rehabilitation centre identified"), x["properties"].get("Name of the Mandal")])
out["rehab"] = rh; out["meta"]["rehab"] = "Flood rehabilitation centres identified for vulnerable localities (GHMC list via Lakeer open-GIS); undated"
# lake / river quality 2017, STP outlets 2017, noise 2018
lw = []
for x in feats("lakewq2017.geojson"):
    p = pt(x, "Latitude", "Longitude"); q = x["properties"]
    if p and inbox(*p): lw.append([round(p[0], 5), round(p[1], 5), q.get("Water Quality Monitoring Station Name"), q.get("Class of Water"), num(q.get("DO (mg/L)")), num(q.get("BOD (mg/L)")), num(q.get("Fecal Coliform (MPN/100ml)")), num(q.get("pH"))])
out["lakewq"] = lw; out["meta"]["lakewq"] = "TSPCB lake/river monitoring, annual average 2017 (Lakeer open-GIS) — DATED"
sp = []
for x in feats("stp2017.geojson"):
    p = pt(x, "Latitude", "Longitude"); q = x["properties"]
    if p and inbox(*p): sp.append([round(p[0], 5), round(p[1], 5), q.get("Name of Sewage Treatment Plant"), num(q.get("BOD (mg/L)")), q.get("Outlet Water Quality Status")])
out["stp"] = sp; out["meta"]["stp"] = "TSPCB sewage-treatment-plant outlet quality, 2017 (Lakeer open-GIS) — DATED"
nz = {}
for tag, f in (("day", "noise_day.geojson"), ("night", "noise_night.geojson")):
    for x in feats(f):
        p = pt(x, "Latitude", "Longitude"); q = x["properties"]
        if not (p and inbox(*p)): continue
        k = (round(p[0], 5), round(p[1], 5)); e = nz.setdefault(k, {"lat": k[0], "lon": k[1], "loc": q.get("Location"), "cat": q.get("Category")})
        e[tag] = num(q.get("Average Day-Time Noise Levels (Decibels)") if tag == "day" else q.get("Average Night-Time Noise Levels")); e[tag + "_status"] = q.get("Day-Time Noise - Status" if tag == "day" else "Night-Time Noise - Status")
out["noise"] = [[e["lat"], e["lon"], e["loc"], e["cat"], e.get("day"), e.get("night"), e.get("day_status"), e.get("night_status")] for e in nz.values()]
out["meta"]["noise"] = "TSPCB noise monitoring, average Jan-Jun 2018 (Lakeer open-GIS), 10 locations — DATED and sparse"
(ROOT / "web" / "data" / "civic.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
print({k: (len(v) if isinstance(v, list) else None) for k, v in out.items() if k != "meta"})
print("power cells", len(out["power"]), "events", int(b.shape[0]), "| median breakdown minutes", int(b["min"].median()))
