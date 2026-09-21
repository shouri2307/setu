"""
p4_network.py — Hospital reachability over the major-road network for SETU.

Question answered (at ward / arterial resolution, NOT street level):
  For each rainfall scenario, if the major roads through flooded wards go
  impassable, can each ward still reach a hospital along the remaining
  arterial network — and how far is the nearest one now?

Method:
  1. Parse major roads (Overpass JSON) -> a graph: vertices are road points,
     edges connect consecutive points, weighted by real distance (metres).
  2. Tag every road vertex with the ward it sits in.
  3. Snap each hospital to its nearest road vertex.
  4. Give each ward an "access vertex" (nearest road vertex to its centroid).
  5. Per scenario: block vertices in wards flooded deeper than a road threshold,
     then from the surviving hospital vertices run one multi-source shortest-path
     to get every ward's nearest reachable hospital. No path => cut off.

Reads:  data/raw/hyderabad_roads.geojson, data/raw/hyderabad_hospitals.geojson,
        data/zones_enriched.geojson, data/scenarios.json
Writes: data/network.json

Run from project root:  python pipeline/p4_network.py
"""

import sys
import json
import math
from pathlib import Path

import numpy as np
import geopandas as gpd
import networkx as nx
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

METRIC_CRS = "EPSG:32644"       # UTM 44N — distances in metres
# Roads through a flooded ward are treated as impassable to normal traffic.
# We sync this to p3's flood threshold (read from scenarios.json) with a small
# floor, so the feature works regardless of how deep the modelled floods run.
ROAD_FLOOD_FLOOR_M = 0.12
COORD_ROUND = 6                 # decimal places to merge shared road vertices (~0.1 m)


def _haversine_m(a, b):
    """Distance in metres between (lon,lat) a and b."""
    lon1, lat1, lon2, lat2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def _load_overpass(path):
    """Return the raw dict for an Overpass JSON (or GeoJSON) file, or None."""
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return None


def build_road_graph(roads_raw):
    """Build a networkx graph from Overpass road ways. Nodes are (lon,lat)."""
    G = nx.Graph()
    if not roads_raw or "elements" not in roads_raw:
        return G
    for el in roads_raw["elements"]:
        geom = el.get("geometry")
        if not geom or len(geom) < 2:
            continue
        pts = [(round(p["lon"], COORD_ROUND), round(p["lat"], COORD_ROUND))
               for p in geom]
        for u, v in zip(pts[:-1], pts[1:]):
            if u == v:
                continue
            w = _haversine_m(u, v)
            # keep the shortest if a duplicate edge appears
            if not G.has_edge(u, v) or G[u][v]["weight"] > w:
                G.add_edge(u, v, weight=w)
    return G


def parse_hospitals(hosp_raw):
    """Return list of (lon,lat) hospital points from Overpass JSON."""
    pts = []
    if not hosp_raw or "elements" not in hosp_raw:
        return pts
    for el in hosp_raw["elements"]:
        if "lat" in el and "lon" in el:                      # node
            pts.append((el["lon"], el["lat"]))
        elif "center" in el:                                  # way/relation
            c = el["center"]
            pts.append((c["lon"], c["lat"]))
    return pts


def nearest_node(nodes_arr, node_list, lon, lat):
    """Index of nearest graph node to (lon,lat) by squared degree distance."""
    d = (nodes_arr[:, 0] - lon)**2 + (nodes_arr[:, 1] - lat)**2
    return int(np.argmin(d))


def main():
    print("=== SETU p4_network ===")
    for f in [config.OSM_ROADS, config.OSM_HOSPITALS,
              config.DATA / "zones_enriched.geojson", config.DATA / "scenarios.json"]:
        if not Path(f).exists():
            print(f"[error] missing {f}. Run earlier pipeline steps first.")
            return

    roads_raw = _load_overpass(config.OSM_ROADS)
    hosp_raw = _load_overpass(config.OSM_HOSPITALS)
    G = build_road_graph(roads_raw)
    if G.number_of_nodes() == 0:
        print("[error] road graph is empty — check hyderabad_roads.geojson.")
        return
    print(f"[graph] {G.number_of_nodes()} vertices, {G.number_of_edges()} edges")

    nodes = list(G.nodes())
    nodes_arr = np.array(nodes)                      # (M,2) lon,lat
    node_index = {n: i for i, n in enumerate(nodes)}

    # The OSM extract has small disconnected road fragments (islands). Snapping a
    # hospital or a ward onto one of those would make it permanently unreachable
    # and fake a "cut off" that has nothing to do with flooding. So snap only to
    # the MAIN connected road network.
    main_cc = max(nx.connected_components(G), key=len)
    main_nodes = [n for n in nodes if n in main_cc]
    main_arr = np.array(main_nodes)
    print(f"[graph] main connected component: {len(main_nodes)}/{len(nodes)} vertices")

    def snap(lon, lat):
        d = (main_arr[:, 0] - lon)**2 + (main_arr[:, 1] - lat)**2
        return main_nodes[int(np.argmin(d))]

    # hospitals -> nearest MAIN-network vertex
    hpts = parse_hospitals(hosp_raw)
    hosp_nodes = set()
    for lon, lat in hpts:
        hosp_nodes.add(snap(lon, lat))
    print(f"[hosp] {len(hpts)} hospitals snapped to {len(hosp_nodes)} road vertices")
    if not hosp_nodes:
        print("[error] no hospitals parsed — check hyderabad_hospitals.geojson.")
        return

    # wards: assign each road vertex to a ward, and each ward an access vertex
    gdf = gpd.read_file(config.DATA / "zones_enriched.geojson")
    if gdf.crs is None:
        gdf.set_crs("EPSG:4326", inplace=True)
    node_pts = gpd.GeoDataFrame(
        {"idx": range(len(nodes))},
        geometry=[Point(n) for n in nodes], crs="EPSG:4326")
    joined = gpd.sjoin(node_pts, gdf[["zone_id", "geometry"]],
                       how="left", predicate="within")
    # a node can match >1 ward on a boundary; keep first
    joined = joined[~joined.index.duplicated(keep="first")]
    node_ward = {}
    for _, r in joined.iterrows():
        zid = r["zone_id"]
        node_ward[int(r["idx"])] = int(zid) if zid == zid else None  # NaN check

    # access vertex per ward = nearest MAIN-network vertex to ward centroid
    gdf_m = gdf.to_crs(METRIC_CRS)
    cents = gdf_m.geometry.centroid.to_crs("EPSG:4326")
    ward_access = {}
    for i, (_, r) in enumerate(gdf.iterrows()):
        c = cents.iloc[i]
        ward_access[int(r["zone_id"])] = snap(c.x, c.y)
    ward_ids = [int(z) for z in gdf["zone_id"]]
    ward_name = {int(r["zone_id"]): r["zone_name"] for _, r in gdf.iterrows()}

    # scenarios: flood depth per ward
    scen = json.loads((config.DATA / "scenarios.json").read_text())
    scen_depths = scen["scenarios"]                 # {"192": {ward_id_str: depth}}
    scen_list = scen["scenarios_mm"]
    # sync road-impassable depth to p3's flood threshold (with a floor), so the
    # cutoff feature works whatever the modelled depths look like
    p3_thresh = scen.get("params", {}).get("flood_threshold_m", ROAD_FLOOD_FLOOR_M)
    road_flood_depth = max(float(p3_thresh), ROAD_FLOOD_FLOOR_M)
    print(f"[road] impassable depth = {road_flood_depth} m (synced to flood model)")

    def reach_from_hospitals(blocked_wards):
        """Nearest-hospital distance (m) for every ward, given blocked wards.
        Returns {ward_id: dist_m or None if cut off}."""
        blocked_nodes = {n for n, i in node_index.items()
                         if node_ward.get(i) in blocked_wards}
        # surviving hospital sources
        srcs = [h for h in hosp_nodes if h not in blocked_nodes]
        if not srcs:
            return {z: None for z in ward_ids}
        H = G
        if blocked_nodes:
            H = G.subgraph([n for n in G.nodes() if n not in blocked_nodes])
        # one multi-source Dijkstra from all hospitals at once
        dist = nx.multi_source_dijkstra_path_length(H, srcs, weight="weight")
        out = {}
        for z in ward_ids:
            acc = ward_access[z]
            # if the ward's own access vertex is blocked, it's cut off
            if acc in blocked_nodes:
                out[z] = None
            else:
                out[z] = dist.get(acc)   # None if unreachable
        return out

    # baseline (no flooding)
    baseline = reach_from_hospitals(set())
    base_km = {z: (round(d/1000, 2) if d is not None else None)
               for z, d in baseline.items()}

    # per scenario
    out_scen = {}
    for r in scen_list:
        depths = scen_depths.get(str(r), {})
        blocked = {int(zid) for zid, d in depths.items()
                   if d >= road_flood_depth}
        reach = reach_from_hospitals(blocked)
        wards_out = {}
        cut = []
        for z in ward_ids:
            d = reach[z]
            if d is None:
                wards_out[str(z)] = -1        # cut off
                cut.append(z)
            else:
                wards_out[str(z)] = round(d/1000, 2)
        out_scen[str(r)] = {
            "n_roads_flooded_wards": len(blocked),
            "n_cut_off": len(cut),
            "cut_off_ids": cut,
            "nearest_km": wards_out,
        }

    result = {
        "params": {
            "road_flood_depth_m": road_flood_depth,
            "resolution": "major arterial roads (primary/secondary/trunk/motorway)",
            "hospitals": len(hpts),
            "road_vertices": G.number_of_nodes(),
            "note": "Reachability along the MAJOR-road network only — the roads "
                    "emergency vehicles use. A ward is 'cut off' when no arterial "
                    "path to any hospital survives the flood. Not street-level.",
        },
        "baseline_km": {str(z): base_km[z] for z in ward_ids},
        "scenarios": out_scen,
    }
    (config.DATA / "network.json").write_text(json.dumps(result))
    print(f"[ok] wrote network.json")

    # quick report at the 2020 level
    for r in [100, 192, 250]:
        if str(r) in out_scen:
            s = out_scen[str(r)]
            print(f"     {r}mm: {s['n_roads_flooded_wards']} wards flood roads, "
                  f"{s['n_cut_off']} wards cut off from hospitals")


if __name__ == "__main__":
    main()