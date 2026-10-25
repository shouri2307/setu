"""p24b_access_grid.py — road-network travel distance and estimated driving time from every ~220 m grid cell to the nearest hospital, metro/rail
station, bus stop, school and market -> web/data/access.json.

Network: main and collector roads from OpenStreetMap (research/osm_cache/roads_full/, residential streets are NOT included).
Cost model: typical urban average speeds by road class, no traffic signals, no one-way rules (roads are treated as two-way) — so the
time is an estimate of order, not a routing-app answer. Each cell adds a straight-line last leg from the cell centre to its nearest network node
(at 15 km/h, only if that node is within 700 m, otherwise the cell is left empty). POIs are snapped to the nearest network node within 600 m.
Validation: a sample of routes is compared with OSRM's public demo server at the end.
Run: .venv/Scripts/python pipeline/p24b_access_grid.py"""
import json, sys, time, random
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
ROOT = Path(__file__).resolve().parent.parent
TILES = ROOT / "research" / "osm_cache" / "roads_full"
SPEED = {"motorway": 55, "motorway_link": 35, "trunk": 40, "trunk_link": 30, "primary": 30, "primary_link": 25, "secondary": 25, "secondary_link": 22,
         "tertiary": 20, "tertiary_link": 18, "unclassified": 15, "residential": 14, "living_street": 10}
B = json.loads((ROOT / "web/data/zones.json").read_text())["bounds"]          # lon0, lat0, lon1, lat1
BB = [B[0] - .01, B[1] - .01, B[2] + .01, B[3] + .01]
CELL = 0.002
K = 111320.0; LAT0 = (BB[1] + BB[3]) / 2; KX = K * np.cos(np.radians(LAT0)); KY = 110540.0

ways = {}
for f in TILES.glob("t_*.json"):
    for e in json.loads(f.read_text(encoding="utf-8")):
        if e.get("type") == "way" and e.get("geometry") and e["tags"].get("highway") in SPEED: ways[e["id"]] = e
print("tiles", len(list(TILES.glob('t_*.json'))), "| ways", len(ways), flush=True)
if len(ways) < 500: sys.exit("too few ways — wait for the download to finish")

nid, coords, U, V, L, T = {}, [], [], [], [], []
def node(lon, lat):
    k = (round(lon, 6), round(lat, 6))
    if k not in nid: nid[k] = len(coords); coords.append(k)
    return nid[k]
for e in ways.values():
    sp = SPEED[e["tags"]["highway"]]
    pts = [(p["lon"], p["lat"]) for p in e["geometry"] if p]
    for a, b in zip(pts, pts[1:]):
        m = np.hypot((a[0] - b[0]) * KX, (a[1] - b[1]) * KY)
        if m < 0.5: continue
        u, v = node(*a), node(*b); U.append(u); V.append(v); L.append(m); T.append(m / (sp * 1000 / 60))      # minutes
n = len(coords); print("nodes", n, "edges", len(U), flush=True)
def mat(w):
    M = csr_matrix((w + w, (U + V, V + U)), shape=(n, n)); return M
Gd, Gt = mat(L), mat(T)
xy = np.array([[(c[0] - BB[0]) * KX, (c[1] - BB[1]) * KY] for c in coords]); tree = cKDTree(xy)

poi = json.loads((ROOT / "web/data/geo.json").read_text(encoding="utf-8"))["poi"]
CATS = {"hospital": "hospital", "metro": "metro", "bus": "bus", "school": "school", "market": "market"}
nx, ny = int(np.ceil((BB[2] - BB[0]) / CELL)), int(np.ceil((BB[3] - BB[1]) / CELL))
gx = BB[0] + (np.arange(nx) + .5) * CELL; gy = BB[3] - (np.arange(ny) + .5) * CELL
GX, GY = np.meshgrid(gx, gy); cells = np.column_stack([((GX - BB[0]) * KX).ravel(), ((GY - BB[1]) * KY).ravel()])
snap_d, snap_i = tree.query(cells); okc = snap_d <= 700
print("grid", nx, "x", ny, "| cells with a node within 700 m:", int(okc.sum()), "of", len(okc), flush=True)
out = {"meta": {"bbox": BB, "cell_deg": CELL, "nx": nx, "ny": ny, "cats": list(CATS),
                "method": "shortest path on OpenStreetMap main/collector roads (no residential streets), typical urban speeds, two-way roads, plus a straight-line last leg from the cell centre (15 km/h, node within 700 m)",
                "source": "OpenStreetMap (ODbL) road network and POIs, Oct 2026"}, "cats": {}}
for k, pk in CATS.items():
    P = np.array([[(p[1] - BB[0]) * KX, (p[0] - BB[1]) * KY] for p in poi.get(pk, []) if BB[0] <= p[1] <= BB[2] and BB[1] <= p[0] <= BB[3]])
    d, i = tree.query(P); src = np.unique(i[d <= 600])
    dist = dijkstra(Gd, directed=False, indices=src, min_only=True); tim = dijkstra(Gt, directed=False, indices=src, min_only=True)
    dd = np.where(okc, dist[snap_i] + snap_d, np.inf); tt = np.where(okc, tim[snap_i] + snap_d / (15000 / 60), np.inf)
    ok = np.isfinite(dd) & (dd < 60000)
    out["cats"][k] = {"d": [int(round(x)) if o else None for x, o in zip(dd, ok)], "t": [int(round(x * 10)) if o else None for x, o in zip(tt, ok)]}
    print(f"{k:9s} POIs snapped {len(src):5d}/{len(P)} | cells filled {int(ok.sum()):6d} | median road distance {np.median(dd[ok]):.0f} m, median time {np.median(tt[ok]):.1f} min", flush=True)
(ROOT / "web/data/access.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
print("written access.json")

# ---- validation against OSRM's public demo server (independent routing engine) ----
import requests
random.seed(3); idx = [j for j in range(len(okc)) if okc[j] and out["cats"]["hospital"]["d"][j] is not None]
hp = np.array([[p[0], p[1]] for p in poi["hospital"]])
res = []
for j in random.sample(idx, min(10, len(idx))):
    la, lo = GY.ravel()[j], GX.ravel()[j]
    sl = np.hypot((hp[:, 1] - lo) * KX, (hp[:, 0] - la) * KY); h = hp[np.argsort(sl)[:3]]      # compare against the nearest few hospitals by straight line
    best = None
    for hh in h:
        try:
            r = requests.get(f"https://router.project-osrm.org/route/v1/driving/{lo:.5f},{la:.5f};{hh[1]:.5f},{hh[0]:.5f}?overview=false", timeout=20, headers={"User-Agent": "SETU-sideproject/0.1"}).json()
            if r.get("routes"): d_ = r["routes"][0]["distance"]; t_ = r["routes"][0]["duration"] / 60; best = (d_, t_) if best is None or d_ < best[0] else best
        except Exception: pass
        time.sleep(1.1)
    if best: res.append((out["cats"]["hospital"]["d"][j], best[0], out["cats"]["hospital"]["t"][j] / 10, best[1]))
if res:
    a = np.array(res); print(f"\nvalidation vs OSRM ({len(a)} routes to the nearest few hospitals): median ratio of our road distance to OSRM's = {np.median(a[:, 0] / a[:, 1]):.2f}; median ratio of our time to OSRM's = {np.median(a[:, 2] / a[:, 3]):.2f}")
    for r_ in res: print(f"   ours {r_[0]:6.0f} m {r_[2]:5.1f} min | OSRM {r_[1]:6.0f} m {r_[3]:5.1f} min")
