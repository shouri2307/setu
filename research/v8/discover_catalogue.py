"""Source discovery, step 1: catalogue EVERY folder, service and layer on the Telangana State GIS ArcGIS server (names and geometry types only; no data is downloaded),
then search the catalogue for the evidence we still lack. Light on the server: 4 threads, one request per service.
Output: research/v8/tgrac_catalogue.json and a printed keyword report.   .venv/Scripts/python research/v8/discover_catalogue.py"""
import requests, json, re, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent
H = {"User-Agent": "SETU-sideproject/0.1"}; B = "https://tgrac.telangana.gov.in/arcgis/rest/services"
def get(u, **p):
    p["f"] = "json"
    for k in range(3):
        try: return requests.get(u, params=p, headers=H, timeout=60).json()
        except Exception: time.sleep(2)
    return {}
root = get(B); folders = root.get("folders", []); services = [(None, s) for s in root.get("services", [])]
for f in folders:
    for s in get(f"{B}/{f}").get("services", []): services.append((f, s))
print("folders", len(folders), "| services", len(services))
def svc(item):
    f, s = item; name = s["name"]; typ = s["type"]
    j = get(f"{B}/{name}/{typ}")
    layers = [(l["id"], l["name"]) for l in j.get("layers", [])] + [(t["id"], t["name"]) for t in j.get("tables", [])]
    return {"service": name, "type": typ, "folder": f, "layers": layers, "created": None}
with ThreadPoolExecutor(4) as ex: cat = list(ex.map(svc, services))
(ROOT / "tgrac_catalogue.json").write_text(json.dumps(cat, indent=0), encoding="utf-8")
print("layers catalogued:", sum(len(c["layers"]) for c in cat))
KEYS = {"FTL / lake boundary / buffer": r"\bftl\b|full tank|buffer|lake|tank|water ?bod|cheruvu|encroach|hydra",
        "master plan / zoning / land use": r"master ?plan|zon(e|ing)|land ?use|lulc|landuse|development plan|cdp|\bclu\b",
        "fire / emergency": r"\bfire\b|ambulance|emergency|108|police|disaster|shelter",
        "flood / inundation": r"flood|inundat|water ?logg|vulnerab",
        "parcel / revenue / survey": r"cadastr|parcel|survey|revenue|pahani|village boundary|dharani|bhu",
        "groundwater / geology": r"ground ?water|geolog|lithol|lineament|aquifer|watershed|drainage|stream|geomorph|soil",
        "air / pollution": r"air|pollut|aqi|noise|emission"}
for k, rx in KEYS.items():
    print(f"\n== {k}")
    seen = 0
    for c in cat:
        hit = [(i, n) for i, n in c["layers"] if re.search(rx, n, re.I)] or ([(None, c["service"])] if re.search(rx, c["service"], re.I) else [])
        for i, n in hit[:4]:
            print(f"   {c['service']:58s} layer {i}: {n[:60]}"); seen += 1
            if seen > 45: break
        if seen > 45: print("   ..."); break
