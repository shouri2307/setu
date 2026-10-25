"""p34_tank_survey.py — for every HYDRAA tank that records its own survey number ('Base_Syno'), find the survey parcel(s) carrying that number next to the tank outline -> web/data/tank_syn.json

WHAT THIS IS: the state water-body layer says "tank X, survey no. N". This script looks in two parcel layers for the parcel(s) numbered N that touch or lie within 150 m of the tank outline:
  * Bhunaksha_Cadastral layer 0 (the layer behind our survey-plot matching), and
  * Hydra_Folder/Fourth_Window layer 0 (HYDRAA's 'Cadastral Parcels', 63,686 polygons; the same schema, mostly the same parcels, but it differs at a few lakes: 4 of 20 tested had more numbered parcels).
A parcel is matched on number + position, never on village name (village spellings differ between the two layers: Qutubullapur / Quthbullapur, Pothaipally / Pothaipalle).
WHAT THIS IS NOT: it does not say where the legal Full Tank Level is, and a parcel with the tank's number is not "inside the FTL". The official FTL polygons could not be retrieved (FTL_Tanks / Topo_Tanks sub-layers do not serve).
Only 313 of 1,192 tank records carry a usable survey number; the rest are left without one (the report says so).
No owner or personal-data field is requested.
Run: .venv/Scripts/python pipeline/p34_tank_survey.py   (about 600 requests, paced; research/v8/step2_validate.py is the 20-lake check)"""
import json, re, time, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
from shapely.geometry import Polygon
from shapely.ops import unary_union
ROOT = Path(__file__).resolve().parent.parent
H = {"User-Agent": "SETU-sideproject/0.1"}; B = "https://tgrac.telangana.gov.in/arcgis/rest/services"
LAYERS = (("main", B + "/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/0/query"), ("fourth", B + "/Hydra_Folder/Fourth_Window/MapServer/0/query"))
M = 111000; PAD = 150
clean = lambda s: re.sub(r"\s+", " ", str(s or "")).strip()

def q(url, env, tries=4):
    p = {"f": "json", "where": "Parcel_num IS NOT NULL AND Parcel_num <> ' ' AND Parcel_num <> ''", "geometry": ",".join(f"{v:.6f}" for v in env), "geometryType": "esriGeometryEnvelope", "inSR": 4326,
         "spatialRel": "esriSpatialRelIntersects", "outFields": "Parcel_num,V_Name", "returnGeometry": "true", "outSR": 4326, "maxAllowableOffset": 0.00001, "geometryPrecision": 6}
    for k in range(tries):
        try:
            r = requests.get(url, params=p, headers=H, timeout=120).json()
            if "features" in r: return r
        except Exception: pass
        time.sleep(2 + 2 * k)
    return None

def geom(rings):
    out = []
    for r in rings:
        if len(r) >= 4:
            try: out.append(Polygon(r).buffer(0))
            except Exception: pass
    return unary_union(out) if out else None

def number_matches(parcel_no, syns):
    p = clean(parcel_no).upper().split("/")[0]
    return p and any(p == s.split("/")[0] for s in syns)

def job(t):
    syns = t["syn"].split("_"); g = geom([[(p[1], p[0]) for p in r] for r in t["rings"]])
    if g is None or g.is_empty: return t["id"], None
    x0, y0, x1, y1 = g.bounds; env = (x0 - PAD / M, y0 - PAD / M, x1 + PAD / M, y1 + PAD / M); zone = g.buffer(PAD / M)
    found = {}; failed = []
    for src, url in LAYERS:
        r = None
        for _ in range(2):
            r = q(url, env)
            if r: break
        if r is None: failed.append(src); continue
        if r.get("exceededTransferLimit"): failed.append(src + " (truncated)")
        for f in r["features"]:
            a = f["attributes"]
            if not number_matches(a.get("Parcel_num"), syns): continue
            rings = f.get("geometry", {}).get("rings", [])
            pg = geom(rings)
            if pg is None or not pg.intersects(zone): continue
            touch = pg.intersects(g); cov = round(pg.intersection(g).area / g.area, 3) if touch else 0.0
            key = (clean(a.get("Parcel_num")).upper(), round(pg.centroid.x, 4), round(pg.centroid.y, 4))
            if key in found: found[key]["src"] += "+" + src; continue          # the same polygon in both layers
            found[key] = {"no": clean(a.get("Parcel_num")), "v": clean(a.get("V_Name")), "src": src, "touch": touch, "cov": cov,
                          "rings": [[[round(p[1], 5), round(p[0], 5)] for p in r] for r in rings if len(r) >= 4]}
    par = sorted(found.values(), key=lambda x: (-x["touch"], -x["cov"]))[:8]
    return t["id"], {"par": par, "failed": failed}

if __name__ == "__main__":
    t0 = time.time()
    hy = json.load(open(ROOT / "web/data/hydraa_tanks.json", encoding="utf-8"))["tanks"]
    todo = [t for t in hy if t["syn"]]
    print("tanks with a usable survey number:", len(todo), "of", len(hy))
    out, failed = {}, []
    with ThreadPoolExecutor(3) as ex:
        for n, (tid, res) in enumerate(ex.map(job, todo)):
            if res is None or res["failed"]: failed.append(tid)
            if res is not None and not res["failed"]: out[str(tid)] = res["par"]
            if n % 40 == 0: print(n, "/", len(todo), f"{time.time() - t0:.0f}s", flush=True)
    matched = sum(1 for v in out.values() if v); touching = sum(1 for v in out.values() if any(p["touch"] for p in v))
    print(f"queried ok: {len(out)} | a same-numbered parcel found within {PAD} m: {matched} | one touches the tank outline: {touching} | failed or truncated (left out, not stored as 'none'): {len(failed)}")
    meta = {"source": "Telangana State GIS: HYDRAA water-body layer (tank survey number 'Base_Syno') matched to Bhunaksha_Cadastral layer 0 and Hydra_Folder/Fourth_Window layer 0 parcels, fetched Oct 2026",
            "service_created": "2025-04-19 (cadastral); tank layer undated", "tanks_total": len(hy), "tanks_with_survey_number": len(todo), "queried_ok": len(out), "with_matching_parcel": matched, "touching_outline": touching, "failed": len(failed),
            "match_rule": f"parcel number equals the tank's survey number (sub-survey 81/1 counts as 81) AND the parcel lies within {PAD} m of the tank outline; village names are not used",
            "note": "A parcel carrying a tank's survey number is not the legal Full Tank Level and says nothing about encroachment. Parcels shown are survey-record polygons, not owner or title information."}
    (ROOT / "web" / "data" / "tank_syn.json").write_text(json.dumps({"meta": meta, "par": out}, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print("bytes:", (ROOT / "web/data/tank_syn.json").stat().st_size, f"| {time.time() - t0:.0f}s")
