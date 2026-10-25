"""p27_tanks_streams.py — mapped tank capacity records and natural stream order from the Telangana State GIS (TGRAC) -> web/data/tanks.json

Source layers (MapServer TIS_Folder/HMDA_ORR_GHMC_Water_Bodies):
  13  HMDA ORR GHMC Water Bodies   polygons with Area (m2), Bund_Heigh (m), Volume (m3), WBS_2011 / WBS_2023 status, WB_Source, Cons_Year
  14  HMDA ORR GHMC Stream Order    polylines with ORDSH (stream order), RIVNAME
Layer 12 ("Totally Encroached Water Bodies") was checked and is an exact duplicate of layer 13 (same 2,050 records), so it is NOT used (summing both would double count).
What the numbers are (validated on the full set):
  * Volume = Area x Bund_Heigh / 2 for every record that has one, so it is a formula-based ESTIMATE of design capacity, not a measured storage
  * only 751 of 2,050 records have a bund height, so most tanks have no capacity figure at all
  * Area_Total is the same area expressed in acres (Area ha x 2.471), NOT an original or pre-encroachment extent, so it is not used
Geometry is simplified (~9 m). Run: .venv/Scripts/python pipeline/p27_tanks_streams.py"""
import json, time
from pathlib import Path
import requests
from shapely.geometry import Polygon, LineString
from shapely.strtree import STRtree
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "research" / "gov_cache"
H = {"User-Agent": "SETU-sideproject/0.1"}
B = "https://tgrac.telangana.gov.in/arcgis/rest/services/TIS_Folder/HMDA_ORR_GHMC_Water_Bodies/MapServer"
ENV = "78.20,17.20,78.75,17.70"

def get(params, lid, tries=4):
    for a in range(tries):
        try:
            r = requests.get(f"{B}/{lid}/query", params=params, headers=H, timeout=120)
            if r.status_code == 200 and "error" not in r.json(): return r.json()
        except Exception: pass
        time.sleep(3 + 4 * a)
    raise RuntimeError("failed layer %s" % lid)

def fetch(key, lid, fields, simplify):
    cf = CACHE / f"tank_{key}.json"
    if cf.exists(): return json.loads(cf.read_text(encoding="utf-8"))
    base = {"f": "json", "geometry": ENV, "geometryType": "esriGeometryEnvelope", "inSR": 4326, "outSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": ",".join(fields), "returnGeometry": "true", "maxAllowableOffset": simplify}
    ids = sorted(get({**base, "returnIdsOnly": "true", "returnGeometry": "false"}, lid).get("objectIds") or [])
    feats = []
    for i in range(0, len(ids), 150):
        feats += get({**base, "objectIds": ",".join(map(str, ids[i:i + 150]))}, lid).get("features", []); print(f"   {key}: {len(feats)}/{len(ids)}", flush=True); time.sleep(0.4)
    cf.write_text(json.dumps(feats), encoding="utf-8"); return feats
num = lambda v: (lambda s: float(s) if s.replace(".", "", 1).replace("-", "", 1).isdigit() else None)(str(v).strip()) if v is not None else None
txt = lambda v: (str(v).strip() or None) if v is not None else None

F = ["FID", "Area", "Bund_Heigh", "Volume", "WBS_2011", "WBS_2023", "WB_Source", "Cons_Year", "WB_Type", "WB_Name", "Village", "Mandal"]
tk = fetch("wb13", 13, F, 0.00008)
STAT = {"Live Water Bodies": "L", "Partially Encroached  Water Bodies": "P", "Totally Encroached Water Bodies": "T", "Dead Water Bodies (Not Encroached, but no water storage)": "D"}
recs = []
for f in tk:
    g = (f.get("geometry") or {}).get("rings")
    a = f["attributes"]
    if not g: continue
    ring = [[round(p[1], 5), round(p[0], 5)] for p in g[0]]
    if len(ring) < 4: continue
    area, bund, vol = num(a.get("Area")), num(a.get("Bund_Heigh")), num(a.get("Volume"))
    if vol is not None and area and bund and abs(vol - area * bund / 2) / vol > 0.02: vol = None      # only trust volumes that follow the documented formula
    recs.append({"id": a["FID"], "r": [ring] + [[[round(p[1], 5), round(p[0], 5)] for p in rg] for rg in g[1:2] if len(rg) >= 4][:0],
                 "a": [txt(a.get("WB_Name")), area, bund, vol, STAT.get(txt(a.get("WBS_2011")) or "", None), STAT.get(txt(a.get("WBS_2023")) or "", None), txt(a.get("WB_Source")), txt(a.get("Cons_Year")), txt(a.get("WB_Type")), txt(a.get("Village")), txt(a.get("Mandal"))]})
# de-duplicate: drop a polygon that is mostly covered by a larger one (overlapping or repeated records)
polys = [Polygon([(p[1], p[0]) for p in r["r"][0]]).buffer(0) for r in recs]
order = sorted(range(len(recs)), key=lambda i: -polys[i].area); tree = STRtree(polys); drop = set()
for i in order:
    if i in drop: continue
    for j in tree.query(polys[i]):
        if j == i or j in drop or polys[j].area > polys[i].area: continue
        if polys[j].area > 0 and polys[i].intersection(polys[j]).area / polys[j].area > 0.6: drop.add(j)
recs = [r for k, r in enumerate(recs) if k not in drop]
print(f"water-body records {len(tk)} -> with geometry {len(polys)} -> after de-duplication {len(recs)} (dropped {len(drop)} overlapping)")

S = fetch("stream14", 14, ["RILCODE", "RIVNAME", "ORDSH"], 0.00008)
streams = []
for f in S:
    pa = (f.get("geometry") or {}).get("paths") or []
    a = f["attributes"]; o = num(a.get("ORDSH"))
    if not pa: continue
    streams.append({"p": [[[round(p[1], 5), round(p[0], 5)] for p in path] for path in pa], "o": int(o) if o is not None else None, "n": txt(a.get("RIVNAME"))})
print("stream segments", len(streams), "| orders", sorted({s["o"] for s in streams if s["o"] is not None}))

out = {"meta": {"source": "Telangana State GIS (TGRAC) — HMDA/ORR/GHMC water-body and stream-order layers, fetched Oct 2026",
                "tank_note": "capacity = Area x bund height / 2 (the source's own formula); only tanks with a bund height have one; this is estimated design capacity, not measured storage",
                "status_codes": {"L": "live", "P": "partially encroached", "T": "totally encroached", "D": "dead (not encroached, no storage)"},
                "tank_fields": ["name", "area_m2", "bund_m", "capacity_m3", "status_2011", "status_2023", "map_source", "origin_period", "type", "village", "mandal"],
                "dedupe": f"{len(drop)} overlapping records dropped; layer 12 is an exact duplicate of layer 13 and is not used",
                "stream_note": "stream order from a terrain-derived stream network; it does not prove a buried channel or plot-level flood risk"},
       "tanks": recs, "streams": streams}
(ROOT / "web" / "data" / "tanks.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
with_cap = sum(1 for r in recs if r["a"][3]); print(f"tanks with a capacity figure {with_cap}/{len(recs)} | total estimated capacity {sum(r['a'][3] or 0 for r in recs)/1e6:.0f} Mm3")
