"""p26_tgrac_land_layers.py — land, geology and utility layers from the Telangana State GIS (TGRAC ArcGIS server) for the Hyderabad study box -> web/data/land.json

Layers (all public MapServer layers, queried with an envelope; raw pages cached in research/gov_cache/land_*.json):
  gwp        Groundwater_Potential/12  hydro-geomorphological units: recharge, suggested wells, depth/yield ranges, success rate, water quality, remarks
  lost       HMDA_ORR_GHMC_Water_Bodies/16  'Water Bodies - Disappeared' (tanks that no longer exist on the ground)
  forest     TCUR_Telangana_Core_Urban_Region_V2/4  forest boundary polygons
  tx / sub   TCUR_.../12 and /13  electric transmission lines and substations
  endow      EndowmentLands_Admin_2026/14  endowment (temple) properties, Hyderabad
Not used, deliberately: the Digital Land Survey owner layers (personal data), and Bhunaksha 'ULB_Cadastral_Prohibited' (its meaning is not documented in the service,
so it is not shown as a legal restriction). Parcels with survey numbers exist for peri-urban villages (e.g. Medchal) but not inside the core GHMC area.
Geometry is simplified server-side (~3 m). Run: .venv/Scripts/python pipeline/p26_tgrac_land_layers.py"""
import json, time
from pathlib import Path
import requests
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "research" / "gov_cache"; CACHE.mkdir(parents=True, exist_ok=True)
H = {"User-Agent": "SETU-sideproject/0.1"}; BASE = "https://tgrac.telangana.gov.in/arcgis/rest/services"
ENV = "78.20,17.20,78.75,17.70"
T = "TIS_Folder/HMDA_ORR_GHMC_Water_Bodies"; TC = "TCUR_Folder/TCUR_Telangana_Core_Urban_Region_V2"

def get(u, params, tries=4):
    for a in range(tries):
        try:
            r = requests.get(u, params=params, headers=H, timeout=120)
            if r.status_code == 200:
                j = r.json()
                if "error" not in j: return j
        except Exception as e: pass
        time.sleep(3 + 4 * a)
    raise RuntimeError("failed " + u)

def fetch(key, svc, lid, fields, geom=True, simplify=0.00003):
    cf = CACHE / f"land_{key}.json"
    if cf.exists(): return json.loads(cf.read_text(encoding="utf-8"))
    u = f"{BASE}/{svc}/MapServer/{lid}/query"
    base = {"f": "json", "geometry": ENV, "geometryType": "esriGeometryEnvelope", "inSR": 4326, "outSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": ",".join(fields), "returnGeometry": "true" if geom else "false"}
    if geom: base["maxAllowableOffset"] = simplify
    # the server ignores resultOffset (it returns the same first page again), so fetch by object id like p14 does
    ids = sorted(get(u, {**base, "returnIdsOnly": "true", "returnGeometry": "false"}).get("objectIds") or [])
    feats = []
    for i in range(0, len(ids), 150):
        j = get(u, {**base, "objectIds": ",".join(map(str, ids[i:i + 150]))})
        feats += j.get("features", []); print(f"   {key}: {len(feats)}/{len(ids)}", flush=True); time.sleep(0.4)
    cf.write_text(json.dumps(feats), encoding="utf-8"); return feats

def rings(g):  # esri polygon rings -> [[lat, lon], ...] (outer rings only, lat/lon order like the other gov layers)
    out = []
    for r in (g or {}).get("rings", []):
        out.append([[round(p[1], 5), round(p[0], 5)] for p in r])
    return out
def paths(g):
    return [[[round(p[1], 5), round(p[0], 5)] for p in r] for r in (g or {}).get("paths", [])]
clean = lambda v: None if v is None or str(v).strip() in ("", "0") else str(v).strip()

out = {"meta": {"source": "Telangana State GIS (TGRAC ArcGIS server), fetched Oct 2026", "note": "public map-service layers, undated; see pipeline/p26_tgrac_land_layers.py for what was deliberately left out"}}
# groundwater potential
GF = ["Geom", "LG2", "LG_1", "LG_3A", "LG_3B", "LG_4", "LG_5B", "LG_6A", "LG_7A", "LG_8A", "LG_9", "LG_10", "LG_12A", "LG_13"]
f = fetch("gwp", "GWDPotential_Folder/Groundwater_Potential", 12, GF)
out["gwp"] = [{"r": rings(x.get("geometry")), "a": [clean(x["attributes"].get(k)) for k in GF]} for x in f if x.get("geometry")]
# keep only units that carry hydrogeology (drop the plain 'Water Body' units and empty ones): halves the file for the browser
out["gwp"] = [u for u in out["gwp"] if u["a"][1] != "Water Body" and any(u["a"][i] for i in (2, 5, 8, 9))]
# the same attribute set repeats on many units (long remarks): store each distinct set once and reference it by index
from shapely.geometry import Polygon
def simp(rs, tol):
    o = []
    for r in rs:
        pts = [(p[1], p[0]) for p in r]
        if len(pts) < 4: continue
        g = Polygon(pts).simplify(tol, preserve_topology=True)
        if not g.is_empty and g.geom_type == "Polygon": o.append([[round(y, 5), round(x, 5)] for x, y in g.exterior.coords])
    return o
tbl, idx = [], {}
for u in out["gwp"]:
    k = json.dumps(u["a"]); 
    if k not in idx: idx[k] = len(tbl); tbl.append(u["a"])
    u["i"] = idx[k]; u["r"] = simp(u["r"], 0.00008); del u["a"]
out["gwp"] = [u for u in out["gwp"] if u["r"]]; out["gwp_attrs"] = tbl
out["meta"]["gwp_fields"] = ["geom", "landform", "rock", "depth_to_water", "wells_observed", "recharge", "aquifer", "well_type", "well_depth", "yield", "success", "water_quality", "recharge_structures", "remarks"]
# lost water bodies
f = fetch("lost", T, 16, ["TYPE", "AREA_Ha"])
out["lost"] = [{"r": rings(x.get("geometry")), "a": [clean(x["attributes"].get("TYPE")), x["attributes"].get("AREA_Ha")]} for x in f if x.get("geometry")]
# forest boundary
f = fetch("forest", TC, 4, ["FB_Type", "Forest_Nam", "Descript"])
out["forest"] = [{"r": rings(x.get("geometry")), "a": [clean(x["attributes"].get("FB_Type")), clean(x["attributes"].get("Forest_Nam")), clean(x["attributes"].get("Descript"))]} for x in f if x.get("geometry")]
# transmission lines, substations
f = fetch("tx", TC, 12, ["Name_of_th", "begin", "end", "lines_data", "lines_da_1", "lines_da_2"])
out["tx"] = [{"p": paths(x.get("geometry")), "a": [clean(x["attributes"].get(k)) for k in ("Name_of_th", "begin", "end", "lines_data", "lines_da_1", "lines_da_2")]} for x in f if x.get("geometry")]
f = fetch("sub", TC, 13, ["Name_of_Su", "Voltage_le", "Type_of_Su"])
out["sub"] = [{"ll": [round(x["geometry"]["y"], 5), round(x["geometry"]["x"], 5)], "a": [clean(x["attributes"].get(k)) for k in ("Name_of_Su", "Voltage_le", "Type_of_Su")]} for x in f if x.get("geometry") and "x" in x["geometry"]]
# endowment properties
try:
    f = fetch("endow", "EndowmentLands_Folder/EndowmentLands_Admin_2026", 14, ["Village", "Mandal", "District", "Archakas", "Agri_Lease", "Vacant"])
    out["endow"] = [{"ll": [round(x["geometry"]["y"], 5), round(x["geometry"]["x"], 5)], "a": [clean(x["attributes"].get(k)) for k in ("Village", "Mandal", "District")]} for x in f if x.get("geometry") and "x" in x["geometry"]]
except Exception as e:
    print("endowment layer skipped:", e); out["endow"] = []
(ROOT / "web" / "data" / "land.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
print({k: len(v) for k, v in out.items() if isinstance(v, list)})
