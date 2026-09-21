"""
p7_roadgraph.py — Export a compact road graph so the browser can recompute
hospital road distances live after a flood intervention is applied.

Same graph, hospital snapping and ward access points as p4_network.py, but
written as flat arrays (main connected component only) to web/data/roadgraph.json.
The browser runs the same multi-source Dijkstra with the same blocking rule.

Run from project root:  python pipeline/p7_roadgraph.py
"""

import sys
import json
from pathlib import Path

import numpy as np
import geopandas as gpd
import networkx as nx
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import p4_network as p4


def main():
    G = p4.build_road_graph(p4._load_overpass(config.OSM_ROADS))
    nodes = list(G.nodes())
    main_cc = max(nx.connected_components(G), key=len)
    main_nodes = [n for n in nodes if n in main_cc]
    main_arr = np.array(main_nodes)
    midx = {n: i for i, n in enumerate(main_nodes)}

    def snap(lon, lat):
        d = (main_arr[:, 0] - lon) ** 2 + (main_arr[:, 1] - lat) ** 2
        return main_nodes[int(np.argmin(d))]

    hosp = sorted({midx[snap(lon, lat)]
                   for lon, lat in p4.parse_hospitals(p4._load_overpass(config.OSM_HOSPITALS))})

    gdf = gpd.read_file(config.DATA / "zones_enriched.geojson")
    if gdf.crs is None:
        gdf.set_crs("EPSG:4326", inplace=True)
    pts = gpd.GeoDataFrame({"i": range(len(main_nodes))},
                           geometry=[Point(n) for n in main_nodes], crs="EPSG:4326")
    joined = gpd.sjoin(pts, gdf[["zone_id", "geometry"]], how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]
    ward = [-1] * len(main_nodes)
    for _, r in joined.iterrows():
        if r["zone_id"] == r["zone_id"]:
            ward[int(r["i"])] = int(r["zone_id"])

    cents = gdf.to_crs(p4.METRIC_CRS).geometry.centroid.to_crs("EPSG:4326")
    access = {}
    for i, (_, r) in enumerate(gdf.iterrows()):
        access[str(int(r["zone_id"]))] = midx[snap(cents.iloc[i].x, cents.iloc[i].y)]

    eu, ev, ew = [], [], []
    for u, v, d in G.edges(data=True):
        if u in midx and v in midx:
            eu.append(midx[u]); ev.append(midx[v]); ew.append(round(d["weight"], 1))

    scen = json.loads((config.DATA / "scenarios.json").read_text())
    thr = float(scen.get("params", {}).get("flood_threshold_m", p4.ROAD_FLOOD_FLOOR_M))
    out = {"road_flood_depth_m": max(thr, p4.ROAD_FLOOD_FLOOR_M), "n": len(main_nodes),
           "ward": ward, "eu": eu, "ev": ev, "ew": ew, "hosp": hosp, "access": access}
    web = config.ROOT / "web" / "data" / "roadgraph.json"
    web.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"[ok] {len(main_nodes)} nodes, {len(eu)} edges, {len(hosp)} hospital nodes -> {web} "
          f"({web.stat().st_size/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
