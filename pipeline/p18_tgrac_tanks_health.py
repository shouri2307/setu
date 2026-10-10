"""
p18_tgrac_tanks_health.py — two more public TGRAC layers (Telangana GIS ArcGIS service, no login):

 1. HYDRAA water-body assessment  (Hydra_Folder/Second_Window/0 "ORR Tanks", ~1,192 polygons around GHMC + ORR):
      named tanks with village/mandal, origin period (WBCP) and satellite-assessed status in 2014 and 2023:
      Live | Partially Encroached - Built-up/Agriculture | Totally Encroached - Built-up/Agriculture
    -> web/data/hydraa_tanks.json
 2. Government health + emergency points (GovtHospitals_Folder/Health_Facilities_Mapping):
      district/area hospitals, medical colleges, CHC/PHC/UPHC, Basti Dawakhana, existing ambulance stations (EMRI/Govt)
    -> research/tgrac_health.json (merged into geo.json by p12_merge_places.py)

Raw responses are cached in research/gov_cache/. Polite pacing. Run:  .venv/Scripts/python pipeline/p18_tgrac_tanks_health.py
"""
import json
import sys
import time
from pathlib import Path

import requests
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "research" / "gov_cache"
CACHE.mkdir(parents=True, exist_ok=True)
B = "https://tgrac.telangana.gov.in/arcgis/rest/services"
H = {"User-Agent": "Mozilla/5.0 (SETU hackathon project)"}
BOX = (78.10, 17.10, 78.80, 17.80)
STAT = {"Live": "L", "Partially Encroached - Built-up": "PB", "Totally Encroached - Built-up": "TB",
        "Partially Encroached - Agriculture": "PA", "Totally Encroached - Agriculture": "TA"}


def get(url, params, tries=4):
    for a in range(tries):
        try:
            r = requests.get(url, params=params, headers=H, timeout=90)
            if r.status_code == 200 and "error" not in r.json():
                return r.json()
        except Exception as e:
            print("   retry", e, flush=True)
        time.sleep(2 + 3 * a)
    raise RuntimeError("failed " + url)


def fetch(service, layer, tag, geometry=True, step=150):
    cf = CACHE / f"{tag}.json"
    if cf.exists():
        return json.loads(cf.read_text(encoding="utf-8"))
    base = f"{B}/{service}/MapServer/{layer}/query"
    ids = sorted(get(base, {"where": "1=1", "returnIdsOnly": "true", "f": "json"}).get("objectIds") or [])
    feats = []
    for i in range(0, len(ids), step):
        j = get(base, {"objectIds": ",".join(map(str, ids[i:i + step])), "outFields": "*", "returnGeometry": str(geometry).lower(), "outSR": 4326, "f": "json"})
        feats += j.get("features", [])
        print(f"   {tag}: {len(feats)}/{len(ids)}", flush=True)
        time.sleep(0.4)
    cf.write_text(json.dumps(feats), encoding="utf-8")
    return feats


def main():
    print("HYDRAA tanks…", flush=True)
    tanks = []
    for f in fetch("Hydra_Folder/Second_Window", 0, "hydraa_second_window"):
        a, g = f["attributes"], f.get("geometry") or {}
        rings = []
        for ring in g.get("rings", []):
            if len(ring) >= 4:
                pg = Polygon(ring).simplify(0.00004)
                if not pg.is_empty and pg.geom_type == "Polygon":
                    rings.append([[round(y, 5), round(x, 5)] for x, y in pg.exterior.coords])
        if not rings:
            continue
        tanks.append({"name": (a.get("WB_Name") or "").strip(), "mandal": (a.get("Mandal") or "").strip(), "village": (a.get("Village") or "").strip(),
                      "admin": (a.get("Admin") or "").strip(), "origin": (a.get("WBCP") or "").strip(),
                      "s14": STAT.get((a.get("WBS_2014") or "").strip(), "?"), "s23": STAT.get((a.get("WBS_2023") or "").strip(), "?"), "rings": rings})
    (ROOT / "web" / "data" / "hydraa_tanks.json").write_text(json.dumps({"source": "TGRAC / HYDRAA water-body assessment (Telangana State GIS, public service)", "fetched": time.strftime("%Y-%m-%d"),
        "legend": {"L": "Live", "PB": "Partially encroached (built-up)", "TB": "Totally encroached (built-up)", "PA": "Partially encroached (agriculture)", "TA": "Totally encroached (agriculture)"}, "tanks": tanks},
        separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print("tanks:", len(tanks), "named:", sum(1 for t in tanks if t["name"]), "status 2023:", dict(Counter(t["s23"] for t in tanks)))

    print("health + ambulance points…", flush=True)
    layers = {"ambulance": [20], "govhospital": [9, 10, 8], "govclinic": [13, 15, 16, 17]}
    out = {k: [] for k in layers}
    for cat, ids in layers.items():
        for lid in ids:
            for f in fetch("GovtHospitals_Folder/Health_Facilities_Mapping", lid, f"health_{lid}"):
                a, g = f.get("attributes") or {}, f.get("geometry") or {}
                if "x" not in g:
                    continue
                lat, lon = g["y"], g["x"]
                if not (BOX[0] <= lon <= BOX[2] and BOX[1] <= lat <= BOX[3]):
                    continue
                nm = next((str(v).strip() for k, v in a.items() if v and any(w in k.lower() for w in ("name", "facility", "hospital", "station")) and isinstance(v, str)), "")
                out[cat].append([round(lat, 5), round(lon, 5), nm[:60]])
    (ROOT / "research" / "tgrac_health.json").write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print({k: len(v) for k, v in out.items()})


if __name__ == "__main__":
    sys.exit(main())
