"""Step 2 validation: tank survey numbers (HYDRAA 'Base_Syno') and the lake-side parcel layer (HYDRAA Fourth_Window), at 20 lakes.
Selection rule (fixed before looking at results; one change after the first run: the same tank polygon-pair listed twice, e.g. Jalla Kunta, is now counted once): HYDRAA tanks that have a name AND a Base_Syno, ranked by outline area, 20 taken at evenly spaced ranks (so small and large lakes are both tested).
For each lake we ask the two parcel layers for every parcel touching the lake outline + 150 m and record:
  * how many parcels each layer returns (does Fourth_Window fill gaps in the main cadastral layer?)
  * does a parcel whose number equals Base_Syno (or its sub-survey, e.g. 81/1) exist among them? (matched by number + position, NOT by village name: the first run matched village names
    and wrongly reported 'no' where only the spelling differs, e.g. Qutubullapur / Quthbullapur; the village-name agreement is reported separately)
  * does that parcel overlap or touch the lake outline, and how much of the outline does it cover?
Nothing here says anything about Full Tank Level: the outline is the satellite water-body polygon and a parcel is a survey-record polygon.
.venv/Scripts/python research/v8/step2_validate.py"""
import json, re, sys, time
from pathlib import Path
import requests
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent.parent
H = {"User-Agent": "SETU-sideproject/0.1 (validation)"}; B = "https://tgrac.telangana.gov.in/arcgis/rest/services"
MAIN = B + "/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/0/query"; FOURTH = B + "/Hydra_Folder/Fourth_Window/MapServer/0/query"
clean = lambda s: re.sub(r"\s+", " ", str(s or "")).strip()
M_PER_DEG = 111000

def q(url, env, fields, tries=4):
    p = {"f": "json", "where": "1=1", "geometry": ",".join(f"{v:.6f}" for v in env), "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
         "outFields": fields, "returnGeometry": "true", "outSR": 4326, "maxAllowableOffset": 0.00001}
    for k in range(tries):
        try:
            r = requests.get(url, params=p, headers=H, timeout=120).json()
            if "features" in r: return r
        except Exception: pass
        time.sleep(2 + 2 * k)
    return None

def polys(f):
    out = []
    for r in (f.get("geometry") or {}).get("rings", []):
        if len(r) >= 4:
            try: out.append(Polygon(r).buffer(0))
            except Exception: pass
    return unary_union(out) if out else None

tanks = json.load(open(ROOT / "research/gov_cache/hydraa_second_window.json", encoding="utf-8"))
cand = []
for f in tanks:
    a = f["attributes"]; nm, sy = clean(a.get("WB_Name")), clean(a.get("Base_Syno"))
    if not nm or not sy or sy == "88805": continue          # 88805 appears 12 times: a placeholder, not a survey number
    g = polys(f)
    if g is None or g.is_empty: continue
    if any(c[1] == nm and c[2] == sy and c[3] == clean(a.get("Village")) for c in cand): continue
    cand.append((g.area * M_PER_DEG * M_PER_DEG * 0.96, nm, sy, clean(a.get("Village")), clean(a.get("Mandal")), clean(a.get("WBS_2023")), g))
cand.sort(key=lambda t: -t[0])
print(f"tanks with a name and a usable Base_Syno: {len(cand)} of {len(tanks)}")
pick = [cand[round(i * (len(cand) - 1) / 19)] for i in range(20)]

def same_no(parcel_no, syn):
    p, s = clean(parcel_no).upper(), clean(syn).upper()
    return bool(p) and (p == s or p.split("/")[0] == s.split("/")[0])

rows = []
print("\n| # | lake (village) | ~area ha | Base_Syno | main layer: parcels / has Base_Syno / touches lake | Fourth_Window: parcels / has Base_Syno / touches lake |\n|---|---|---|---|---|---|")
for n, (area, nm, sy, vil, man, st, g) in enumerate(pick, 1):
    x0, y0, x1, y1 = g.bounds; pad = 150 / M_PER_DEG; env = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    res = {}
    for key, url, fields in (("main", MAIN, "Parcel_num,V_Name,Remarks"), ("fourth", FOURTH, "Parcel_num,V_Name,Remarks")):
        r = q(url, env, fields)
        if r is None: res[key] = None; continue
        fs = r["features"]; trunc = bool(r.get("exceededTransferLimit"))
        withno = [f for f in fs if clean(f["attributes"].get("Parcel_num"))]
        vnorm = lambda s: re.sub(r"[^a-z]", "", clean(s).lower())
        hit = [f for f in withno if same_no(f["attributes"].get("Parcel_num"), sy)]
        vname = sum(1 for f in hit if vnorm(f["attributes"].get("V_Name")) == vnorm(vil))
        touch, cover = 0, 0.0
        for f in hit:
            pg = polys(f)
            if pg is not None and pg.intersects(g):
                touch += 1; cover = max(cover, pg.intersection(g).area / g.area)
        res[key] = {"parcels": len(fs), "numbered": len(withno), "has_syn": len(hit), "village_same": vname, "touches": touch, "cover": round(cover, 2), "truncated": trunc}
    rows.append({"lake": nm, "village": vil, "mandal": man, "area_ha": round(area / 10000, 1), "base_syno": sy, "status_2023": st, "main": res["main"], "fourth": res["fourth"]})
    f = lambda d: "failed" if d is None else f"{d['numbered']} / {'yes' if d['has_syn'] else 'no'} / {'yes ' + str(int(d['cover'] * 100)) + '%' if d['touches'] else 'no'}{' (truncated)' if d['truncated'] else ''}"
    print(f"| {n} | {nm} ({vil}) | {area / 10000:.1f} | {sy} | {f(res['main'])} | {f(res['fourth'])} |", flush=True)
    time.sleep(0.5)

ok = [r for r in rows if r["main"] and r["fourth"]]
print(f"\nlakes tested: {len(rows)}; both layers answered: {len(ok)}")
print("Fourth_Window returns more numbered parcels than the main layer at:", sum(1 for r in ok if r["fourth"]["numbered"] > r["main"]["numbered"]), "lakes; fewer at:", sum(1 for r in ok if r["fourth"]["numbered"] < r["main"]["numbered"]), "; equal at:", sum(1 for r in ok if r["fourth"]["numbered"] == r["main"]["numbered"]))
print("main layer has a parcel with the tank's survey number nearby:", sum(1 for r in ok if r["main"]["has_syn"]), "| and it touches the lake outline:", sum(1 for r in ok if r["main"]["touches"]))
print("Fourth_Window has a parcel with the tank's survey number nearby:", sum(1 for r in ok if r["fourth"]["has_syn"]), "| and it touches the lake outline:", sum(1 for r in ok if r["fourth"]["touches"]))
print("village spelling identical in the matching parcel (main layer):", sum(1 for r in ok if r["main"]["has_syn"] and r["main"]["village_same"]), "of", sum(1 for r in ok if r["main"]["has_syn"]))
print("either layer touches:", sum(1 for r in ok if r["main"]["touches"] or r["fourth"]["touches"]))
json.dump(rows, open(ROOT / "research/v8/step2_validate.json", "w"), indent=1, ensure_ascii=False)
