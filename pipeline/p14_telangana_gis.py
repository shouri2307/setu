"""
p14_telangana_gis.py — download GHMC's public nala / drainage / tank / inundation layers from the Telangana GIS
ArcGIS service and write a compact web/data/gov.json for the browser.

Source (public, no login): https://tgrac.telangana.gov.in/arcgis/rest/services/GHMCNalas_Folder/GHMCNalas_vul/MapServer
Layers used: 1 Inundation Areas (points) · 2 Nala (lines + encroachment stats) · 5 Segments (widths) ·
             11 CANAL_DRAIN (lines) · 12 RIVER_STREAM (polygons) · 13 TANKS (polygons)

We download politely (small chunks, raw responses cached in research/gov_cache/), and we do not alter the records.
Run:  .venv/Scripts/python pipeline/p14_telangana_gis.py
"""
import json
import sys
import time
from pathlib import Path

import requests
from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "research" / "gov_cache"
CACHE.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "web" / "data" / "gov.json"
BASE = "https://tgrac.telangana.gov.in/arcgis/rest/services/GHMCNalas_Folder/GHMCNalas_vul/MapServer"
H = {"User-Agent": "Mozilla/5.0 (SETU hackathon project; contact via github)"}


def get(url, params, tries=4):
    for a in range(tries):
        try:
            r = requests.get(url, params=params, headers=H, timeout=90)
            if r.status_code == 200:
                j = r.json()
                if "error" not in j:
                    return j
        except Exception as e:
            print("   retry:", e, flush=True)
        time.sleep(2 + 3 * a)
    raise RuntimeError("failed " + url)


def fetch_layer(layer):
    cf = CACHE / f"layer{layer}.json"
    if cf.exists():
        return json.loads(cf.read_text(encoding="utf-8"))
    ids = get(f"{BASE}/{layer}/query", {"where": "1=1", "returnIdsOnly": "true", "f": "json"})
    oids = sorted(ids.get("objectIds") or [])
    feats, step = [], 150
    for i in range(0, len(oids), step):
        chunk = oids[i:i + step]
        j = get(f"{BASE}/{layer}/query", {"objectIds": ",".join(map(str, chunk)), "outFields": "*", "returnGeometry": "true", "outSR": 4326, "f": "json"})
        feats += j.get("features", [])
        print(f"   layer {layer}: {len(feats)}/{len(oids)}", flush=True)
        time.sleep(0.4)
    cf.write_text(json.dumps(feats), encoding="utf-8")
    return feats


def line_paths(g, tol=0.00003):
    out = []
    for path in g.get("paths", []):
        if len(path) < 2:
            continue
        ls = LineString(path).simplify(tol)
        out.append([[round(y, 5), round(x, 5)] for x, y in ls.coords])   # stored as [lat, lon]
    return out


def poly_rings(g, tol=0.00004):
    out = []
    for ring in g.get("rings", []):
        if len(ring) < 4:
            continue
        pg = Polygon(ring).simplify(tol)
        if pg.is_empty or pg.geom_type != "Polygon":
            continue
        out.append([[round(y, 5), round(x, 5)] for x, y in pg.exterior.coords])
    return out


def main():
    res = {"source": "Telangana State GIS — GHMC Nalas & Vulnerability map (public ArcGIS service)", "fetched": time.strftime("%Y-%m-%d")}

    print("inundation areas…", flush=True)
    inund = []
    for f in fetch_layer(1):
        g, a = f.get("geometry") or {}, f.get("attributes") or {}
        if "x" in g:
            inund.append([round(g["y"], 5), round(g["x"], 5), (a.get("Name") or "").strip()[:80]])
    res["inundation"] = inund

    print("nalas…", flush=True)
    nalas = []
    for f in fetch_layer(2):
        a, paths = f.get("attributes") or {}, line_paths(f.get("geometry") or {})
        if not paths:
            continue
        nalas.append({"id": a.get("Nala_ID"), "name": (a.get("Nala_Name") or "").strip(), "circle": a.get("Circle"), "zone": a.get("ZONE_NAME"),
                      "len_m": a.get("Length_m"), "govt_encr": a.get("Govt_Encr"), "pvt_encr": a.get("Pvt_Encr"), "rel_encr": a.get("Rel_Encr"),
                      "total_encr": a.get("Total_Encr"), "court": a.get("Court_Case"), "segs": a.get("Total_Seg"), "paths": paths})
    res["nalas"] = nalas

    print("segments (widths)…", flush=True)
    segs = []
    for f in fetch_layer(5):
        a, paths = f.get("attributes") or {}, line_paths(f.get("geometry") or {}, 0.00006)
        if not paths:
            continue
        segs.append({"nala": a.get("Nala_Name"), "nala_id": a.get("Nala_ID"), "prop_w": a.get("Prop_Width"), "ext_w": a.get("Ext_Width"),
                     "encr": a.get("Total_Encr"), "court": a.get("Court_Case"), "mandal": a.get("Mandal"), "village": a.get("Village"), "paths": paths})
    res["segments"] = segs

    print("drains…", flush=True)
    drains = []
    for f in fetch_layer(11):
        for p in line_paths(f.get("geometry") or {}, 0.00006):
            drains.append(p)
    res["drains"] = drains

    for name, layer in (("tanks", 13), ("rivers", 12)):
        print(name + "…", flush=True)
        items = []
        for f in fetch_layer(layer):
            a, rings = f.get("attributes") or {}, poly_rings(f.get("geometry") or {})
            if rings:
                nm = " ".join(str(a.get(k) or "").strip() for k in ("Descr_1", "Descr_2", "Descr_3")).strip()
                items.append({"name": nm[:80], "rings": rings, "area": a.get("Shape_Area")})
        res[name] = items

    OUT.write_text(json.dumps(res, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print({k: (len(v) if isinstance(v, list) else v) for k, v in res.items()})
    print("wrote", OUT, f"({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    sys.exit(main())
