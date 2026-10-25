"""Step 2: do the two parcel layers agree where both have data? 300 random points (fixed seed) in tiles where both layers have numbered parcels.
For each point we ask each layer which numbered parcel contains it, and compare the village + number. Disagreement is recorded, not hidden.
.venv/Scripts/python research/v8/step2_agree.py"""
import json, random, re, sys, time
from pathlib import Path
import requests
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent.parent
H = {"User-Agent": "SETU-sideproject/0.1"}; B = "https://tgrac.telangana.gov.in/arcgis/rest/services"
URL = {"main": B + "/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/0/query", "fourth": B + "/Hydra_Folder/Fourth_Window/MapServer/0/query"}
BBOX = [78.24184, 17.26164, 78.65123, 17.59083]; STEP = 0.03
cov = json.load(open(ROOT / "research/v8/step2_coverage.json"))
both = [c for c in cov if c["main"] >= 50 and c["hydraa"] >= 50]
print("tiles where both layers have at least 50 numbered parcels:", len(both))
rnd = random.Random(20261025); pts = []
for _ in range(300):
    c = rnd.choice(both); i, j = map(int, c["tile"].split("_")); pts.append((BBOX[1] + (j + rnd.random()) * STEP, BBOX[0] + (i + rnd.random()) * STEP))
clean = lambda s: re.sub(r"\s+", " ", str(s or "")).strip()
norm = lambda s: re.sub(r"[^a-z]", "", clean(s).lower())
def at(key, la, lo):
    p = {"f": "json", "where": "Parcel_num IS NOT NULL AND Parcel_num <> ' ' AND Parcel_num <> ''", "geometry": f"{lo:.6f},{la:.6f}", "geometryType": "esriGeometryPoint", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": "Parcel_num,V_Name", "returnGeometry": "false"}
    for k in range(4):
        try:
            r = requests.get(URL[key], params=p, headers=H, timeout=60).json()
            if "features" in r: return sorted({(clean(f["attributes"]["Parcel_num"]), norm(f["attributes"]["V_Name"])) for f in r["features"]})
        except Exception: pass
        time.sleep(1.5 + k)
    return None
res = {"both_none": 0, "only_main": 0, "only_fourth": 0, "same_number": 0, "same_number_other_village": 0, "different": 0, "failed": 0}; diffs = []
for la, lo in pts:
    m, f = at("main", la, lo), at("fourth", la, lo)
    if m is None or f is None: res["failed"] += 1; continue
    if not m and not f: res["both_none"] += 1
    elif m and not f: res["only_main"] += 1
    elif f and not m: res["only_fourth"] += 1
    elif set(m) & set(f): res["same_number"] += 1
    elif {a for a, _ in m} & {a for a, _ in f}: res["same_number_other_village"] += 1
    else: res["different"] += 1; diffs.append({"lat": round(la, 5), "lon": round(lo, 5), "main": m, "fourth": f})
print(res)
both_have = res["same_number"] + res["same_number_other_village"] + res["different"]
print(f"where both layers have a parcel at the point: {both_have} | same village+number: {res['same_number']} ({100 * res['same_number'] / max(both_have, 1):.0f}%) | same number, village spelled differently: {res['same_number_other_village']} | different number: {res['different']}")
for d in diffs[:10]: print("  different:", d)
json.dump({"result": res, "different": diffs}, open(ROOT / "research/v8/step2_agree.json", "w"), indent=1, ensure_ascii=False)
