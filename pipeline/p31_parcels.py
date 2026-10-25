"""p31_parcels.py — survey-parcel outlines from the Telangana State GIS cadastral layer for the Hyderabad study box -> web/data/parcels/*.json (lazy tiles) + web/data/prohib.json

Source: TGRAC ArcGIS Bhunaksha_Folder/Bhunaksha_Cadastral layer 0 "Cadastral 2.5m" (service document created 2025-04-19; survey dates and accuracy not published).
WHAT IS A PARCEL HERE (checked 24 Oct 2026, see research/v7/): the layer holds three kinds of polygon. Only polygons with a filled `Parcel_num` (survey / sub-survey number such as "91/1") are
kept. `SNo` is a VILLAGE serial number, not a survey number, and is not used. Polygons with a blank `Parcel_num` are village-sized placeholders ("Missing Village", "Not Available") or the
single "GHMC ... to be checked" polygon over the old city; they are not parcels and are not stored. Free-text remarks are classified: 1 = the number is flagged duplicate / unreadable at source,
2 = the polygon is a road, canal, stream, tank, rail line etc. rather than a plot, 0 = nothing flagged.
NO owner or personal-data field is requested (outFields is an explicit allow-list).
Second file: Bhunaksha_Folder/Bhunaksha layer 0 ("ULB_Cadastral_Prohibited"): parcels carrying a CATEGORY_OF_PROHIBITORY_LAND text. Its legal basis, date and completeness are not documented, so it is only ever shown as
"listed in a state GIS layer", never as the legal prohibited-property register.
Tiles: 0.03-degree cells starting at the study-box corner; a parcel is stored in every tile it touches. Rings are [lat, lon], 5 decimals (~1 m), simplified server-side.
Run: .venv/Scripts/python pipeline/p31_parcels.py"""
import json, re, time, math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
ROOT = Path(__file__).resolve().parent.parent
H = {"User-Agent": "SETU-sideproject/0.1"}; BASE = "https://tgrac.telangana.gov.in/arcgis/rest/services"
CAD = BASE + "/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/0/query"; PRO = BASE + "/Bhunaksha_Folder/Bhunaksha/MapServer/0/query"
BBOX = [78.24184, 17.26164, 78.65123, 17.59083]; STEP = 0.03
REAL = "Parcel_num IS NOT NULL AND Parcel_num <> ' ' AND Parcel_num <> ''"
PRO_WHERE = "CATEGORY_OF_PROHIBITORY_LAND IS NOT NULL AND CATEGORY_OF_PROHIBITORY_LAND <> ' ' AND CATEGORY_OF_PROHIBITORY_LAND <> ''"
CAD_FIELDS = "OBJECTID_12,Parcel_num,V_Name,M_Name,New_Mandal,Remarks"
PRO_FIELDS = "OBJECTID_12,CATEGORY_OF_PROHIBITORY_LAND,SY_NO,PART__Y_N_,EXTENT,V_Name,M_Name,Parcel_num"
DUP = re.compile(r"duplic|double|repit|repeat|repet|not visible number|^nv$|^ni$|not clear|paradi|mahasura number", re.I)
NONPLOT = re.compile(r"road|canal|stream|river|tank|cheruvu|kunta|water|rail|nala|nalla|vagu|tari|thari|charai|majara|forest|gudem|wada|reservoir|lake|pond|well", re.I)

def q(url, params, tries=4):
    for k in range(tries):
        try:
            r = requests.get(url, params=params, headers=H, timeout=180).json()
            if "features" in r or "count" in r: return r
        except Exception: pass
        time.sleep(2 + 2 * k)
    raise RuntimeError("request failed: " + str(params.get("geometry")))

def env_q(url, where, fields, env):
    p = {"f": "json", "where": where, "geometry": ",".join(f"{v:.6f}" for v in env), "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
         "outFields": fields, "returnGeometry": "true", "outSR": 4326, "maxAllowableOffset": 0.00001, "geometryPrecision": 6}
    return q(url, p)

def fetch_env(url, where, fields, env, depth=0, oid="OBJECTID_12"):
    """all features intersecting env; splits the envelope in four whenever the server hits its transfer limit.
    De-duplicates on the layer's TRUE unique id (`oid`). The plain `OBJECTID` attribute is NOT unique in these TGRAC layers (404 distinct values over 481 supply lines in one test box)."""
    if oid not in fields.split(","): fields = oid + "," + fields
    r = env_q(url, where, fields, env); fs = r.get("features", [])
    if r.get("exceededTransferLimit") and depth < 6:
        x0, y0, x1, y1 = env; mx, my = (x0 + x1) / 2, (y0 + y1) / 2; out = {}
        for e in ((x0, y0, mx, my), (mx, y0, x1, my), (x0, my, mx, y1), (mx, my, x1, y1)):
            for f in fetch_env(url, where, fields, e, depth + 1, oid): out[f["attributes"][oid]] = f
        return list(out.values())
    if r.get("exceededTransferLimit"): print("WARNING transfer limit at max depth", env)
    return fs

def rings(g):
    out = []
    for r in (g or {}).get("rings", []):
        if len(r) >= 4: out.append([[round(p[1], 5), round(p[0], 5)] for p in r])
    return out
clean = lambda s: re.sub(r"\s+", " ", str(s or "")).strip()
def rem_code(rm):
    rm = clean(rm)
    if not rm: return 0
    if DUP.search(rm): return 1
    if NONPLOT.search(rm): return 2
    return 0

def server_count(url, where, env):
    return q(url, {"f": "json", "where": where, "geometry": ",".join(f"{v:.6f}" for v in env), "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "returnCountOnly": "true"})["count"]

def tile_job(ij):
    i, j = ij; x0 = BBOX[0] + i * STEP; y0 = BBOX[1] + j * STEP; env = (x0, y0, x0 + STEP, y0 + STEP)
    fs = fetch_env(CAD, REAL, CAD_FIELDS, env)
    want = server_count(CAD, REAL, env)
    if len(fs) != want: raise RuntimeError(f"tile {i}_{j}: fetched {len(fs)} parcels but the server counts {want}")   # never write an incomplete tile
    vil, man, rows = {}, {}, []
    for f in fs:
        a = f["attributes"]; rg = rings(f.get("geometry"))
        if not rg: continue
        v, m = clean(a.get("V_Name")), clean(a.get("New_Mandal") or a.get("M_Name"))
        vi = vil.setdefault(v, len(vil)); mi = man.setdefault(m, len(man))
        rows.append([clean(a.get("Parcel_num")), vi, mi, rem_code(a.get("Remarks")), clean(a.get("Remarks"))[:28], rg])
    return (i, j), {"v": list(vil), "m": list(man), "p": rows}

if __name__ == "__main__":
    t = time.time()
    nx = math.ceil((BBOX[2] - BBOX[0]) / STEP); ny = math.ceil((BBOX[3] - BBOX[1]) / STEP)
    cov = json.load(open(ROOT / "research/v7/parcel_coverage.json"))
    todo = sorted({(round((x - BBOX[0]) / STEP), round((y - BBOX[1]) / STEP)) for k, x, y, n in cov["cells"] if k == "cad_parcels" and (n is None or n > 0)})
    print("tiles with parcels:", len(todo), "of", nx * ny)
    out = ROOT / "web" / "data" / "parcels"; out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.json"): f.unlink()
    index = {}; total = 0
    with ThreadPoolExecutor(4) as ex:
        for n, ((i, j), tile) in enumerate(ex.map(tile_job, todo)):
            if not tile["p"]: continue
            (out / f"{i}_{j}.json").write_text(json.dumps(tile, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
            index[f"{i}_{j}"] = len(tile["p"]); total += len(tile["p"])
            if n % 10 == 0: print(n, "/", len(todo), f"{time.time() - t:.0f}s", flush=True)
    meta = {"source": "Telangana State GIS (TGRAC) Bhunaksha_Cadastral layer 0 'Cadastral 2.5m', fetched Oct 2026", "service_created": "2025-04-19", "bbox": BBOX, "step": STEP, "nx": nx, "ny": ny,
            "tiles": index, "parcels_stored": total, "geometry": "server-simplified (~1 m), 5 decimals",
            "kept": "polygons with a filled Parcel_num only; SNo is a village serial and is not a survey number",
            "remark_codes": {"0": "nothing flagged", "1": "number flagged duplicate / unreadable at source", "2": "road, canal, stream, tank or similar feature, not a plot"},
            "not_stored": "owner and personal-data fields; village-sized placeholder polygons; the old-city GHMC placeholder"}
    (out / "index.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
    print("parcels stored:", total, "| tiles written:", len(index), f"| {time.time() - t:.0f}s")
    # ---- prohibitory-category layer (study box) ----
    fs = fetch_env(PRO, PRO_WHERE, PRO_FIELDS, tuple(BBOX)); seen = {}
    for f in fs:
        a = f["attributes"]; rg = rings(f.get("geometry"))
        if rg: seen[a["OBJECTID_12"]] = [clean(a.get("CATEGORY_OF_PROHIBITORY_LAND")), clean(a.get("SY_NO") or a.get("Parcel_num")), clean(a.get("PART__Y_N_")), clean(a.get("EXTENT")), clean(a.get("V_Name")), clean(a.get("M_Name")), rg]
    pj = {"meta": {"source": "Telangana State GIS (TGRAC) Bhunaksha layer 0 'ULB_Cadastral_Prohibited', fetched Oct 2026", "service_created": "2025-04-19",
                   "note": "Parcels carrying a CATEGORY_OF_PROHIBITORY_LAND text. Legal basis, date and completeness are not documented. NOT the registration department's prohibited-property register.",
                   "fields": ["category (free text as recorded)", "survey no", "part (Y/N)", "extent", "village", "mandal", "rings"]}, "p": list(seen.values())}
    (ROOT / "web" / "data" / "prohib.json").write_text(json.dumps(pj, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print("prohibitory-category parcels in the box:", len(seen), "| bytes", (ROOT / "web" / "data" / "prohib.json").stat().st_size)
