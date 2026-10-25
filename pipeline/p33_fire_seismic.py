"""p33_fire_seismic.py — two small state-GIS layers from the TCUR service -> web/data/fire.json and web/data/seismic.json

FIRE STATIONS  TCUR layer 61 'Fire Stations' (71 records; service document created 2025-05-24). Each record keeps the SOURCE's own status exactly:
  Type = Existing / Proposed, Remarks = e.g. "Moved". Nothing here decides that a station is operating: a Proposed or Moved record is never counted as a confirmed station.
SEISMIC ZONES  TCUR layer 90 'Sesismic Zones' (3 polygons). The label says which seismic zone the area is in. It says nothing about any building's structural safety.
Run: .venv/Scripts/python pipeline/p33_fire_seismic.py"""
import json, time, collections
from pathlib import Path
import requests
ROOT = Path(__file__).resolve().parent.parent
H = {"User-Agent": "SETU-sideproject/0.1"}; T = "https://tgrac.telangana.gov.in/arcgis/rest/services/TCUR_Folder/TCUR_Telangana_Core_Urban_Region_V2/MapServer"
BOX = [78.0, 16.9, 79.1, 17.9]   # a generous box around the study area, in lon/lat
def q(layer, **p):
    p.update({"f": "json", "where": "1=1", "outSR": 4326, "returnGeometry": "true"})
    for _ in range(3):
        try:
            r = requests.get(f"{T}/{layer}/query", params=p, headers=H, timeout=120).json()
            if "features" in r: return r
        except Exception: time.sleep(2)
    raise SystemExit(f"layer {layer} failed")
clean = lambda s: " ".join(str(s or "").split())

# ---- fire stations: statewide list (71 records), keep all so the app can say "none within X km" honestly ----
fs = q(61, outFields="FS_Dist,FS_Locatio,Remarks,Fire_Station_Id,Type")["features"]
rows = []; skipped = 0
for f in fs:
    a = f["attributes"]; g = f.get("geometry") or {}
    pts = g.get("points") or ([[g["x"], g["y"]]] if "x" in g else [])
    if not pts: skipped += 1; continue
    lon, lat = pts[0][0], pts[0][1]
    rows.append([round(lat, 5), round(lon, 5), clean(a.get("FS_Locatio")), clean(a.get("FS_Dist")), clean(a.get("Type")), clean(a.get("Remarks")), clean(a.get("Fire_Station_Id"))])
print("fire records:", len(fs), "| with a point:", len(rows), "| without geometry:", skipped)
print("Type:", collections.Counter(r[4] for r in rows)); print("Remarks:", collections.Counter(r[5] for r in rows).most_common(10)); print("District:", collections.Counter(r[3] for r in rows).most_common(8))
out = {"meta": {"source": "Telangana State GIS (TGRAC) TCUR layer 61 'Fire Stations', fetched Oct 2026", "service_created": "2025-05-24", "records": len(rows),
                "fields": ["lat", "lon", "location", "district", "status as published (Existing / Proposed)", "remark as published (e.g. Moved)", "station id"],
                "note": "Status and remark are the source's own words. Proposed and Moved records are never treated as confirmed operating stations. Survey date and accuracy are not published."}, "stations": rows}
(ROOT / "web" / "data" / "fire.json").write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

# ---- seismic zones: 3 polygons ----
zs = q(90, outFields="Seismic_zo,Intensity", maxAllowableOffset=0.0005, geometryPrecision=5)["features"]
polys = []
for f in zs:
    a = f["attributes"]; rings = [[[round(p[1], 5), round(p[0], 5)] for p in r] for r in (f.get("geometry") or {}).get("rings", []) if len(r) >= 4]
    polys.append({"zone": clean(a.get("Seismic_zo")), "intensity": clean(a.get("Intensity")), "rings": rings})
print("seismic polygons:", [(p["zone"], p["intensity"], len(p["rings"]), sum(len(r) for r in p["rings"])) for p in polys])
(ROOT / "web" / "data" / "seismic.json").write_text(json.dumps({"meta": {"source": "Telangana State GIS (TGRAC) TCUR layer 90 'Sesismic Zones' (sic), fetched Oct 2026", "service_created": "2025-05-24", "geometry": "server-simplified (~50 m)",
    "note": "Names the seismic zone of an area. It is a regional hazard map and says nothing about any building's structural safety. Edition and date of the underlying zoning are not published."}, "zones": polys}, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
print("bytes:", (ROOT / "web/data/fire.json").stat().st_size, (ROOT / "web/data/seismic.json").stat().st_size)
