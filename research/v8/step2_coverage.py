"""Step 2 coverage comparison: numbered survey parcels per 0.03-degree tile of the study box, main cadastral layer vs HYDRAA Fourth_Window.
Uses server-side counts only (returnCountOnly). Counts of polygons that touch a tile edge are counted in each tile they touch, the same way for both layers, so the comparison is fair though not a parcel total.
.venv/Scripts/python research/v8/step2_coverage.py"""
import json, math, time, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent.parent
H = {"User-Agent": "SETU-sideproject/0.1"}; B = "https://tgrac.telangana.gov.in/arcgis/rest/services"
URL = {"main": B + "/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/0/query", "fourth": B + "/Hydra_Folder/Fourth_Window/MapServer/0/query"}
BBOX = [78.24184, 17.26164, 78.65123, 17.59083]; STEP = 0.03
W = "Parcel_num IS NOT NULL AND Parcel_num <> ' ' AND Parcel_num <> ''"
def count(key, env):
    p = {"f": "json", "where": W, "geometry": ",".join(f"{v:.6f}" for v in env), "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "returnCountOnly": "true"}
    for k in range(4):
        try:
            r = requests.get(URL[key], params=p, headers=H, timeout=90).json()
            if "count" in r: return r["count"]
        except Exception: pass
        time.sleep(2 + k)
    return None
nx = math.ceil((BBOX[2] - BBOX[0]) / STEP); ny = math.ceil((BBOX[3] - BBOX[1]) / STEP)
jobs = [(i, j) for i in range(nx) for j in range(ny)]
def job(ij):
    i, j = ij; x0 = BBOX[0] + i * STEP; y0 = BBOX[1] + j * STEP; env = (x0, y0, x0 + STEP, y0 + STEP)
    return ij, count("main", env), count("fourth", env)
with ThreadPoolExecutor(4) as ex: res = list(ex.map(job, jobs))
ok = [(ij, m, f) for ij, m, f in res if m is not None and f is not None]
print(f"tiles: {len(jobs)} | both counts returned: {len(ok)} | any failed: {len(jobs) - len(ok)}")
both0 = [x for x in ok if x[1] == 0 and x[2] == 0]; use = [x for x in ok if x[1] or x[2]]
print(f"tiles with no numbered parcel in either layer: {len(both0)} | tiles with parcels in at least one: {len(use)}")
print("main only (HYDRAA has none):", sum(1 for _, m, f in use if m and not f), "| HYDRAA only (main has none):", sum(1 for _, m, f in use if f and not m))
print("HYDRAA more than 1.25x main:", sum(1 for _, m, f in use if m and f > 1.25 * m), "| main more than 1.25x HYDRAA:", sum(1 for _, m, f in use if f and m > 1.25 * f), "| within 25%:", sum(1 for _, m, f in use if m and f and 1 / 1.25 <= f / m <= 1.25))
tm, tf = sum(m for _, m, f in use), sum(f for _, m, f in use); print(f"sum of tile counts: main {tm}, HYDRAA {tf} (HYDRAA / main = {tf / max(tm, 1):.2f})")
print("tiles where HYDRAA has at least 50 more numbered parcels than main:", [(f"{BBOX[0] + i * STEP:.2f},{BBOX[1] + j * STEP:.2f}", m, f) for (i, j), m, f in sorted(use, key=lambda x: x[1] - x[2]) if f - m >= 50][:12])
tiles_main = json.load(open(ROOT / "web/data/parcels/index.json"))["tiles"]
need = [(ij, m, f) for ij, m, f in use if f and (not m or f > 1.25 * m)]
print("tiles where our shipped parcel tiles would gain from the HYDRAA layer (HYDRAA > 1.25x main or main empty):", len(need), "of", len(use))
json.dump([{"tile": f"{i}_{j}", "main": m, "hydraa": f} for (i, j), m, f in ok], open(ROOT / "research/v8/step2_coverage.json", "w"))
