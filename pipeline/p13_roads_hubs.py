"""
p13_roads_hubs.py — trade routes and demand drivers from Overture Maps (free, no key).

* roads : main roads (motorway = ORR/expressways, trunk = national highways, primary = arterials), sampled as points
          every ~120 m so the browser can find "distance to the nearest ORR / highway / arterial" instantly.
* hubs  : IT / software offices (jobs), malls, and cinemas — the demand drivers buyers and agents ask about.

Writes research/overture_roads_hubs.json; run p12_merge_places.py afterwards (it folds these into web/data/geo.json).
Run:  .venv/Scripts/python pipeline/p13_roads_hubs.py [--release 2026-09-23.1]
"""
import argparse
import json
import math
import sys
from pathlib import Path

import duckdb
from shapely import wkt
from shapely.geometry import LineString, MultiLineString

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research" / "overture_roads_hubs.json"
W, S, E, N = 78.17, 17.17, 78.72, 17.70
STEP_M = 120

HUB_CATS = {
    "work": {"software_development", "information_technology_company", "computer_hardware_company", "data_processing_company", "coworking_space", "internet_service_provider_and_hosting", "engineering_services", "research_institute"},
    "mall": {"shopping_mall", "department_store"},
    "cinema": {"movie_theater", "cinema", "multiplex"},
}
REV = {c: k for k, v in HUB_CATS.items() for c in v}


def sample(geom, step_m):
    out = []
    lines = geom.geoms if isinstance(geom, MultiLineString) else [geom]
    for ln in lines:
        if not isinstance(ln, LineString) or ln.length == 0:
            continue
        mid_lat = ln.coords[0][1]
        step_deg = step_m / 110540.0
        n = max(1, int(ln.length / step_deg))
        for i in range(n + 1):
            p = ln.interpolate(i / n, normalized=True)
            out.append((round(p.y, 5), round(p.x, 5)))
    return out


def latest_release():
    import re
    import urllib.request
    xml = urllib.request.urlopen("https://overturemaps-us-west-2.s3.amazonaws.com/?prefix=release/&delimiter=/", timeout=30).read().decode()
    return sorted(re.findall(r"<Prefix>release/([^/<]+)/</Prefix>", xml))[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", default=None)
    args = ap.parse_args()
    rel = args.release or latest_release()
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
    base = f"s3://overturemaps-us-west-2/release/{rel}/theme="

    print("roads…", flush=True)
    rows = con.execute(f"""
      SELECT class, names.primary AS name, ST_AsText(geometry) AS g
      FROM read_parquet('{base}transportation/type=segment/*', hive_partitioning=1)
      WHERE subtype = 'road' AND class IN ('motorway', 'trunk', 'primary')
        AND bbox.xmin < {E} AND bbox.xmax > {W} AND bbox.ymin < {N} AND bbox.ymax > {S}
    """).fetchall()
    roads = {"motorway": [], "trunk": [], "primary": []}
    names = {"motorway": set(), "trunk": set(), "primary": set()}
    for cls, name, g in rows:
        pts = sample(wkt.loads(g), STEP_M)
        for la, lo in pts:
            if S <= la <= N and W <= lo <= E:
                roads[cls].append([la, lo])
        if name:
            names[cls].add(name)
    for k in roads:  # de-duplicate shared vertices
        roads[k] = [list(p) for p in sorted(set(map(tuple, roads[k])))]
    print({k: len(v) for k, v in roads.items()}, "segments:", len(rows))
    print("sample motorway/trunk names:", sorted(names["motorway"])[:8], sorted(names["trunk"])[:8])

    print("hubs…", flush=True)
    hub_rows = con.execute(f"""
      SELECT names.primary AS name, taxonomy.primary AS cat, basic_category AS cat2, operating_status AS st, confidence,
             ST_Y(geometry) AS lat, ST_X(geometry) AS lon
      FROM read_parquet('{base}places/type=place/*', hive_partitioning=1)
      WHERE bbox.xmin BETWEEN {W} AND {E} AND bbox.ymin BETWEEN {S} AND {N}
    """).fetchall()
    hubs = {k: [] for k in HUB_CATS}
    for name, cat, cat2, st, conf, lat, lon in hub_rows:
        if st and st != "open":
            continue
        k = REV.get(cat) or REV.get(cat2)
        if k and (conf or 0) >= 0.4 and name:
            hubs[k].append([round(lat, 5), round(lon, 5), name[:60], round(conf or 0, 2)])
    print({k: len(v) for k, v in hubs.items()})
    OUT.write_text(json.dumps({"release": rel, "roads": roads, "road_names": {k: sorted(v)[:60] for k, v in names.items()}, "hubs": hubs}, separators=(",", ":")), encoding="utf-8")
    print("wrote", OUT, f"({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    sys.exit(main())
