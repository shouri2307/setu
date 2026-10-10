"""
p8_geo.py — fetch the open-map layers that turn a pin into a property report.

Pulls points of interest and water features for the Hyderabad bounding box from
OpenStreetMap (Overpass), with mirror fallback + retries because the public
servers are often busy. Writes a compact web/data/geo.json the browser queries
instantly (no live map calls during a demo).

Run:  .venv/Scripts/python pipeline/p8_geo.py
"""
import json
import sys
import time
from pathlib import Path

import requests
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data" / "geo.json"
CACHE = ROOT / "research" / "osm_cache"
CACHE.mkdir(exist_ok=True)

# west, south, east, north — matches web/data/zones.json bounds
W, S, E, N = 78.27, 17.29, 78.62, 17.56
BBOX = f"{S},{W},{N},{E}"

MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
]
HEADERS = {"User-Agent": "setu-demo/1.0 (hackathon project; contact via github)"}

# category -> overpass selector list (applied to nodes and ways, center output)
POI = {
    "hospital":  ['["amenity"="hospital"]'],
    "clinic":    ['["amenity"="clinic"]', '["healthcare"="clinic"]'],
    "school":    ['["amenity"="school"]'],
    "college":   ['["amenity"="college"]', '["amenity"="university"]'],
    "fire":      ['["amenity"="fire_station"]'],
    "police":    ['["amenity"="police"]'],
    "metro":     ['["station"="subway"]', '["railway"="station"]'],
    "bus":       ['["amenity"="bus_station"]'],
    "market":    ['["amenity"="marketplace"]', '["shop"="supermarket"]', '["shop"="mall"]'],
    "bank":      ['["amenity"="bank"]'],
    "park":      ['["leisure"="park"]'],
    "industry":  ['["landuse"="industrial"]'],
    "airport":   ['["aeroway"="aerodrome"]'],
    "worship":   ['["amenity"="place_of_worship"]'],
    "underpass": ['["tunnel"="yes"]["highway"]', '["tunnel"="culvert"]'],
}


def overpass(query, label, tries=6):
    cache_file = CACHE / f"{label}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    last = None
    for attempt in range(tries):
        url = MIRRORS[attempt % len(MIRRORS)]
        try:
            r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=120)
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                data = r.json()
                cache_file.write_text(json.dumps(data), encoding="utf-8")
                return data
            last = f"{url} -> HTTP {r.status_code} / non-json"
        except Exception as exc:  # network flake
            last = f"{url} -> {exc}"
        wait = 4 + attempt * 6
        print(f"   retry {label} ({last}); sleeping {wait}s", flush=True)
        time.sleep(wait)
    print(f"!! gave up on {label}: {last}", flush=True)
    return {"elements": []}


def stitch(segments):
    """Join open way segments (lists of [lon,lat]) into closed rings — OSM multipolygon outers are
    often split across several ways (Hussain Sagar, Himayat Sagar...)."""
    segs = [list(sg) for sg in segments if len(sg) >= 2]
    rings = []
    while segs:
        cur = segs.pop(0)
        grew = True
        while grew and cur[0] != cur[-1]:
            grew = False
            for i, sg in enumerate(segs):
                if sg[0] == cur[-1]:
                    cur += sg[1:]
                elif sg[-1] == cur[-1]:
                    cur += sg[::-1][1:]
                elif sg[-1] == cur[0]:
                    cur = sg[:-1] + cur
                elif sg[0] == cur[0]:
                    cur = sg[::-1][:-1] + cur
                else:
                    continue
                segs.pop(i)
                grew = True
                break
        rings.append(cur)
    return rings


def nominatim_polygons(ids):
    """Outer rings for OSM relations via Nominatim's polygon output (a separate service from Overpass,
    which is the one that keeps timing out)."""
    out = {}
    ids = sorted(ids)
    for i in range(0, len(ids), 25):
        chunk = ids[i:i + 25]
        cache_file = CACHE / f"nomi_{chunk[0]}_{len(chunk)}.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text(encoding="utf-8"))
        else:
            data = None
            for attempt in range(4):
                try:
                    r = requests.get("https://nominatim.openstreetmap.org/lookup", headers=HEADERS, timeout=90, params={
                        "osm_ids": ",".join(f"R{x}" for x in chunk), "format": "jsonv2",
                        "polygon_geojson": 1, "polygon_threshold": 0.00003})
                    if r.status_code == 200:
                        data = r.json()
                        cache_file.write_text(json.dumps(data), encoding="utf-8")
                        break
                except Exception as exc:
                    print("   nominatim retry:", exc, flush=True)
                time.sleep(3 + attempt * 4)
            if data is None:
                continue
        for row in data:
            g = row.get("geojson") or {}
            polys = g.get("coordinates", []) if g.get("type") == "MultiPolygon" else [g.get("coordinates", [])] if g.get("type") == "Polygon" else []
            rings = [[[round(x, 5), round(y, 5)] for x, y in poly[0]] for poly in polys if poly]
            if rings:
                out[row["osm_id"]] = rings
        time.sleep(1.2)
    return out


def relation_geometry(ids):
    """Tile queries return multipolygon relations as a bounding box only. Fetch the real outlines
    (Hussain Sagar, Himayat Sagar...) from Nominatim."""
    return nominatim_polygons(ids)


def poi_query(selectors, bbox=None):
    bbox = bbox or BBOX
    parts = []
    for sel in selectors:
        parts.append(f"node{sel}({bbox});")
        parts.append(f"way{sel}({bbox});")
    return f"[out:json][timeout:100];({''.join(parts)});out center tags;"


def tiles(n=3):
    """Split the bbox into n x n tiles — big categories (schools) time out as one query."""
    for i in range(n):
        for j in range(n):
            s0 = S + (N - S) * i / n
            s1 = S + (N - S) * (i + 1) / n
            w0 = W + (E - W) * j / n
            w1 = W + (E - W) * (j + 1) / n
            yield f"{s0:.4f},{w0:.4f},{s1:.4f},{w1:.4f}"


def centre(el):
    if el["type"] == "node":
        return el["lat"], el["lon"]
    c = el.get("center")
    return (c["lat"], c["lon"]) if c else (None, None)


def main():
    geo = {"bbox": [W, S, E, N], "poi": {}, "water": [], "source": "OpenStreetMap contributors (ODbL)",
           "fetched": time.strftime("%Y-%m-%d")}

    for cat, sels in POI.items():
        print(f"[{cat}] fetching…", flush=True)
        cache_whole = CACHE / f"{cat}.json"
        if cache_whole.exists():
            data = json.loads(cache_whole.read_text(encoding="utf-8"))
        else:  # smaller tile queries succeed far more often than one city-wide query
            with ThreadPoolExecutor(max_workers=3) as ex:
                futs = [ex.submit(overpass, poi_query(sels, bb), f"{cat}_t{ti}", 8) for ti, bb in enumerate(tiles())]
                els = []
                for f in futs:
                    els += f.result().get("elements", [])
            data = {"elements": els}
        seen, rows = set(), []
        for el in data.get("elements", []):
            lat, lon = centre(el)
            if lat is None:
                continue
            key = (round(lat, 4), round(lon, 4))
            if key in seen:
                continue
            seen.add(key)
            tags = el.get("tags", {})
            name = tags.get("name:en") or tags.get("name") or ""
            rows.append([round(lat, 5), round(lon, 5), name[:48]])
        geo["poi"][cat] = rows
        print(f"   {len(rows)} {cat}", flush=True)

    # water: lakes / ponds / reservoirs as simplified polygons (for buffer distance)
    print("[water] fetching lakes, ponds, reservoirs…", flush=True)
    def wq(bb):
        return (f'[out:json][timeout:120];(way["natural"="water"]({bb});'
                f'way["landuse"="reservoir"]({bb});relation["natural"="water"]({bb}););out geom tags;')
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(overpass, wq(bb), f"water_t{ti}", 8) for ti, bb in enumerate(tiles())]
        seen_w, els = set(), []
        for f in futs:
            for el in f.result().get("elements", []):
                k = (el["type"], el["id"])
                if k not in seen_w:
                    seen_w.add(k); els.append(el)
    wd = {"elements": els}
    rel_ids = [el["id"] for el in els if el["type"] == "relation" and not el.get("members")]
    print(f"   fetching geometry for {len(rel_ids)} multipolygon relations…", flush=True)
    rel_geo = relation_geometry(rel_ids)
    print(f"   got geometry for {len(rel_geo)} of {len(rel_ids)}", flush=True)
    for el in wd.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name:en") or tags.get("name") or ""
        rings = []
        if el["type"] == "way" and el.get("geometry"):
            rings.append([[round(p["lon"], 5), round(p["lat"], 5)] for p in el["geometry"]])
        elif el["type"] == "relation":
            rings = [r for r in rel_geo.get(el["id"], [])]
        rings = [r[:: max(1, len(r) // 80)] for r in rings if len(r) >= 4]  # thin dense outlines
        if rings:
            geo["water"].append({"name": name[:48], "kind": tags.get("water", "water"), "rings": rings})
    print(f"   {len(geo['water'])} water bodies", flush=True)

    OUT.write_text(json.dumps(geo, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    sys.exit(main())
