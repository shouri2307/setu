"""p32_network.py — HMWSSB mapped water-supply pipes, sewer lines and service sections from the Telangana State GIS (TCUR service) -> web/data/network.json

What this is: where the state GIS MAPS a water-supply pipe or a sewer line, in coarse ~100 m cells (length of pipe and largest diameter per cell), plus the 110 HMWSSB operating sections.
What it is NOT: a connection record. A mapped pipe in a cell does not mean the property is connected, that water flows, or how often; no mapped pipe does not mean no supply (mapping completeness is
uneven: 900 m boxes hold from 0 to more than 700 supply segments, and sewer lines are mapped for the 'core city' only). Pipe geometry is deliberately NOT stored or redistributed.
Filters: supply status must read "IN USE" (99.9% do); sewer status "IN USE"/"INUSE" (all). The ENABLED flag is not used (37% of supply segments read 0 and its meaning is not documented).
Service document created 2025-05-24; survey dates are not published.
Run: .venv/Scripts/python pipeline/p32_network.py"""
import json, re, sys, math, time
import requests
from pathlib import Path
import numpy as np, pyproj
from shapely.geometry import Polygon
sys.path.insert(0, str(Path(__file__).resolve().parent))
from p31_parcels import fetch_env, q   # reuse the quadtree fetcher
ROOT = Path(__file__).resolve().parent.parent
BASE = "https://tgrac.telangana.gov.in/arcgis/rest/services/TCUR_Folder/TCUR_Telangana_Core_Urban_Region_V2/MapServer"
BBOX = [78.24184, 17.26164, 78.65123, 17.59083]; CELL = 0.0009
NX = math.ceil((BBOX[2] - BBOX[0]) / CELL); NY = math.ceil((BBOX[3] - BBOX[1]) / CELL)
tr = pyproj.Transformer.from_crs(4326, 32644, always_xy=True).transform
INUSE = re.compile(r"^IN\s?USE", re.I)

def tiles(step=0.03):
    x = BBOX[0]
    while x < BBOX[2]:
        y = BBOX[1]
        while y < BBOX[3]: yield (x, y, min(x + step, BBOX[2]), min(y + step, BBOX[3])); y += step
        x += step

def rasterise(layer, dia_field, label):
    url = f"{BASE}/{layer}/query"; seen = {}; t = time.time()
    meta = requests.get(f"{BASE}/{layer}", params={"f": "json"}, headers={"User-Agent": "SETU-sideproject/0.1"}, timeout=60).json(); oid = next(f["name"] for f in meta["fields"] if f["type"] == "esriFieldTypeOID")
    total_expected = 0
    for n, env in enumerate(tiles()):
        got = fetch_env(url, "1=1", f"SP_STATUS,{dia_field}", env, oid=oid)
        # NOTE: the server's returnCountOnly OVER-counts line layers (509 counted, 472 returned, and a shapely test finds exactly 472 lines intersecting that tile), so tile completeness for this
        # layer is checked geometrically in research/v7/validate_network.py instead of against the count.
        for f in got: seen[f["attributes"][oid]] = f
        if n % 30 == 0: print(label, n, "tiles", len(seen), "segments", f"{time.time() - t:.0f}s", flush=True)
    length = {}; maxd = {}; kept = dropped = 0
    for f in seen.values():
        a = f["attributes"]
        if not INUSE.match(str(a.get("SP_STATUS") or "").strip()): dropped += 1; continue
        dia = a.get(dia_field); dia = float(dia) if dia not in (None, "") else 0.0
        for path in (f.get("geometry") or {}).get("paths", []):
            if len(path) < 2: continue
            xs, ys = tr([p[0] for p in path], [p[1] for p in path]); xs, ys = np.array(xs), np.array(ys)
            seg = np.hypot(np.diff(xs), np.diff(ys)); tot = float(seg.sum())
            if tot <= 0: continue
            k = max(1, int(tot // 20)); d = np.linspace(0, tot, k + 1)[:-1] + tot / (2 * k); cum = np.concatenate([[0], np.cumsum(seg)])
            for dd in d:                                              # a sample every ~20 m; each sample carries its share of the length
                s = min(np.searchsorted(cum, dd, side="right") - 1, len(seg) - 1); fr = (dd - cum[s]) / seg[s] if seg[s] else 0
                lon = path[s][0] + fr * (path[s + 1][0] - path[s][0]); lat = path[s][1] + fr * (path[s + 1][1] - path[s][1])
                i = int((lon - BBOX[0]) // CELL); j = int((lat - BBOX[1]) // CELL)
                if 0 <= i < NX and 0 <= j < NY:
                    c = j * NX + i; length[c] = length.get(c, 0) + tot / k; maxd[c] = max(maxd.get(c, 0), dia)
        kept += 1
    print(label, "segments fetched", len(seen), "| kept (in use)", kept, "| dropped (not in use)", dropped, "| cells", len(length), f"{time.time() - t:.0f}s")
    return [[c, int(round(length[c])), int(maxd[c])] for c in sorted(length)], len(seen), kept, dropped

def sections():
    r = q(f"{BASE}/36/query", {"f": "json", "where": "1=1", "outFields": "NAME,DIVISION_N,sec_code", "returnGeometry": "true", "outSR": 4326, "maxAllowableOffset": 0.0002, "geometryPrecision": 5})
    out = []
    for f in r["features"]:
        a = f["attributes"]; ps = []
        for ring in f["geometry"]["rings"]:
            if len(ring) >= 4 and Polygon(ring).buffer(0).area > 1e-8: ps.append([[round(p[1], 5), round(p[0], 5)] for p in ring])
        if ps: out.append({"n": (a.get("NAME") or "").strip(), "d": str(a.get("DIVISION_N") or "").strip(), "c": str(a.get("sec_code") or "").strip(), "rings": ps})
    return out

if __name__ == "__main__":
    sup, ns, ks, ds = rasterise(32, "SIZE_IN_MM", "supply")
    sew, ns2, ks2, ds2 = rasterise(39, "SP_PIPE_DI", "sewer")
    secs = sections()
    meta = {"source": "Telangana State GIS (TGRAC) TCUR service: HMWSSB supply lines (layer 32), core-city sewer lines (layer 39), section boundaries (layer 36); fetched Oct 2026", "service_created": "2025-05-24",
            "bbox": BBOX, "cell_deg": CELL, "nx": NX, "ny": NY, "encoding": "[cell index = row*nx+col (row 0 at the south edge), mapped length m, largest diameter mm]",
            "supply_segments": {"fetched": ns, "in_use_kept": ks, "dropped": ds}, "sewer_segments": {"fetched": ns2, "in_use_kept": ks2, "dropped": ds2},
            "note": "Where the GIS MAPS a pipe, in ~100 m cells. Not a connection record. No mapped pipe never means no supply. Pipe geometry is not redistributed. Sewer lines are mapped for the 'core city' only."}
    (ROOT / "web" / "data" / "network.json").write_text(json.dumps({"meta": meta, "supply": sup, "sewer": sew, "sections": secs}, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print("sections", len(secs), "| bytes", (ROOT / "web" / "data" / "network.json").stat().st_size)
