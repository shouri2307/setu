"""
p6_export.py — Flatten & shrink pipeline outputs into small web/data/*.json
for the offline SVG demo. Simplifies ward polygons and rounds coordinates.

Reads:  zones_enriched.geojson, scenarios.json, network.json,
        recommendations.json, validation_2020.json, interventions.json
Writes: web/data/zones.json, model.json, reco.json, validation.json, meta.json

Run from project root:  python pipeline/p6_export.py
"""

import sys
import json
from pathlib import Path

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

WEB_DATA = config.ROOT / "web" / "data"
SIMPLIFY_TOL = 0.0004      # ~40 m polygon simplification
COORD_DP = 5


def _parse_hospitals():
    """Return list of {name,lon,lat} for hospitals that have a name."""
    path = Path(config.OSM_HOSPITALS)
    if not path.exists():
        print(f"[WARN] hospitals: file not found at {path}")
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] hospitals: failed to parse {path}: {e}")
        return []
    elements = raw.get("elements")
    if elements is None:
        print(f"[WARN] hospitals: {path} has no 'elements' key "
              f"(top-level keys found: {list(raw.keys())}) — is this Overpass JSON?")
        return []
    out = []
    skipped_no_name = 0
    skipped_no_coords = 0
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            skipped_no_name += 1
            continue
        if "lat" in el and "lon" in el:
            out.append({"name": name, "lon": el["lon"], "lat": el["lat"]})
        elif "center" in el:
            out.append({"name": name, "lon": el["center"]["lon"], "lat": el["center"]["lat"]})
        else:
            skipped_no_coords += 1
    print(f"[hospitals] {len(elements)} elements -> {len(out)} named+located "
          f"(skipped {skipped_no_name} unnamed, {skipped_no_coords} without coords)")
    if not out:
        print("[WARN] hospitals: parsed the file but got zero usable hospitals — "
              "check that elements actually have 'tags.name' and lat/lon or center.")
    return out


def rings_from_geom(geom):
    """Return list of rings; each ring a list of [lng,lat] rounded."""
    out = []
    gtype = geom.geom_type
    polys = [geom] if gtype == "Polygon" else list(geom.geoms) if gtype == "MultiPolygon" else []
    for p in polys:
        ring = [[round(x, COORD_DP), round(y, COORD_DP)] for x, y in p.exterior.coords]
        out.append(ring)
    return out


def main():
    print("=== SETU p6_export ===")
    WEB_DATA.mkdir(parents=True, exist_ok=True)

    # --- zones geometry (simplified) ---
    gdf = gpd.read_file(config.DATA / "zones_enriched.geojson")
    if gdf.crs is None:
        gdf.set_crs("EPSG:4326", inplace=True)
    gdf["geometry"] = gdf.geometry.simplify(SIMPLIFY_TOL, preserve_topology=True)

    feats, bounds = [], [180, 90, -180, -90]
    for _, r in gdf.iterrows():
        rings = rings_from_geom(r.geometry)
        for ring in rings:
            for x, y in ring:
                bounds[0] = min(bounds[0], x); bounds[1] = min(bounds[1], y)
                bounds[2] = max(bounds[2], x); bounds[3] = max(bounds[3], y)
        feats.append({"id": int(r["zone_id"]), "name": r["zone_name"], "rings": rings})
    (WEB_DATA / "zones.json").write_text(
        json.dumps({"bounds": bounds, "wards": feats}), encoding="utf-8")
    print(f"[ok] zones.json  ({len(feats)} wards)")

    # --- model: flood depths + hospital reachability per scenario ---
    scen = json.loads((config.DATA / "scenarios.json").read_text(encoding="utf-8"))
    net = json.loads((config.DATA / "network.json").read_text(encoding="utf-8"))
    model = {
        "scenarios_mm": scen["scenarios_mm"],
        "flood_threshold_m": scen["params"]["flood_threshold_m"],
        "params": scen["params"],
        "validation": scen.get("validation", {}),
        "depths": scen["scenarios"],                 # {mm: {id: depth}}
        "baseline_km": net["baseline_km"],
        "baseline_hospital": net.get("baseline_hospital", {}),
        "cutoffs": {mm: net["scenarios"][mm]["cut_off_ids"] for mm in net["scenarios"]},
        "nearest_km": {mm: net["scenarios"][mm]["nearest_km"] for mm in net["scenarios"]},
    }
    (WEB_DATA / "model.json").write_text(json.dumps(model), encoding="utf-8")
    print(f"[ok] model.json  ({len(model['scenarios_mm'])} scenarios)")

    # --- hospitals: named points + nearest hospital per ward ---
    hospitals = _parse_hospitals()
    ward_nearest_hosp = {}
    if hospitals:
        import numpy as np
        harr = np.array([[h["lon"], h["lat"]] for h in hospitals])
        gm = gdf.to_crs("EPSG:32644")
        cent = gm.geometry.centroid.to_crs("EPSG:4326")
        for i, (_, r) in enumerate(gdf.iterrows()):
            c = cent.iloc[i]
            d2 = (harr[:, 0] - c.x) ** 2 + (harr[:, 1] - c.y) ** 2
            j = int(np.argmin(d2))
            # rough km via equirectangular
            dx = (harr[j, 0] - c.x) * 111.32 * np.cos(np.radians(c.y))
            dy = (harr[j, 1] - c.y) * 110.57
            ward_nearest_hosp[int(r["zone_id"])] = {
                "name": hospitals[j]["name"], "km": round(float((dx*dx+dy*dy)**0.5), 1)}
    else:
        print("[WARN] hospitals: no hospitals parsed, so hospitals.json will be empty "
              "and every ward panel will show '—' for nearest hospital.")
    hpts = [{"name": h["name"], "lng": round(h["lon"], COORD_DP), "lat": round(h["lat"], COORD_DP)}
            for h in hospitals]
    (WEB_DATA / "hospitals.json").write_text(
        json.dumps({"hospitals": hpts, "nearest": ward_nearest_hosp}, ensure_ascii=False),
        encoding="utf-8")
    print(f"[ok] hospitals.json  ({len(hpts)} named hospitals, "
          f"{len(ward_nearest_hosp)} wards with a nearest hospital)")

    # --- recommendations (trim to essentials) + plain explanations ---
    rec = json.loads((config.DATA / "recommendations.json").read_text(encoding="utf-8"))
    try:
        explain = json.loads((config.DATA / "intervention_explain.json").read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] intervention_explain.json failed to load ({e}) — "
              f"'What it is' will fall back to the interventions library mechanism text.")
        explain = {}
    lib = {iv["id"]: iv for iv in
           json.loads((config.DATA / "interventions.json").read_text(encoding="utf-8"))["interventions"]}
    slim = {}
    missing_what = 0
    for zid, r in rec["recommendations"].items():
        ranked_out = []
        for x in r["ranked"][:5]:
            what = explain.get(x["id"]) or lib.get(x["id"], {}).get("mechanism") or ""
            if not what:
                missing_what += 1
            ranked_out.append({"id": x["id"], "name_en": x["name_en"], "name_jp": x["name_jp"],
                        "romaji": x["romaji"], "category": x["category"],
                        "example": x["example"], "operator": x["operator"],
                        "cost_band": x["cost_band"], "time_to_build": x["time_to_build"],
                        "impact": x["impact"], "score": x["score"], "why": x["why"],
                        "what": what,
                        "india": lib.get(x["id"], {}).get("india_relevance", "")})
        slim[zid] = {
            "profile": r["profile"],
            "ranked": ranked_out,
            "excluded": r["excluded"][:8],
        }
    (WEB_DATA / "reco.json").write_text(
        json.dumps({"weights": rec["weights"], "recommendations": slim},
                   ensure_ascii=False), encoding="utf-8")
    if missing_what:
        print(f"[WARN] {missing_what} intervention entries have no 'what' text "
              f"(missing from both intervention_explain.json and interventions.json mechanism field) — "
              f"these will show an empty explanation, not 'undefined'.")
    print(f"[ok] reco.json")

    # --- validation ---
    val = json.loads((config.DATA / "validation_2020.json").read_text(encoding="utf-8"))
    vslim = {
        "event": val["event"],
        "rainfall_mm": val["rainfall_reference"]["imd_begumpet_24h_mm"],
        "flooded_ids": [w["zone_id"] for w in val["modeled_wards_flooded"]],
        "high_conf_ids": [w["zone_id"] for w in val["modeled_wards_flooded"]
                          if w["confidence"] == "high"],
        "outside": [o["area"] for o in val["flooded_areas_outside_modeled_wards"]],
    }
    (WEB_DATA / "validation.json").write_text(json.dumps(vslim), encoding="utf-8")
    print(f"[ok] validation.json  ({len(vslim['flooded_ids'])} documented flooded wards, "
          f"{len(vslim['high_conf_ids'])} high-confidence)")

    # --- meta: limitations text for the panel ---
    p = scen["params"]
    meta = {
        "title": "SETU — Hyderabad Monsoon Flood & Japanese Intervention Planner",
        "resolution": "145 GHMC wards (open data; the city's 16 stormwater zones are not public)",
        "limitations": [
            f"Modelled at ward resolution, not street level — needs GHMC's private drain network for finer.",
            f"Flood model calibrated to the Oct-2020 event ({p.get('calibrated_against','')}).",
            f"runoff_coefficient={p['runoff_coefficient']}, drain_capacity={p['drain_capacity_mm_per_hr']} mm/hr — global, tuned only against 2020.",
            "Drainage scales with elevation & distance-to-water by one uniform formula (no per-ward forcing).",
            "Flood depths are shallow ward-averages; severity is relative to the city distribution.",
            "Intervention 'after' effect is a modelled estimate, not a hydraulic re-simulation.",
            "Water bodies & roads from OpenStreetMap — some tanks (e.g. breached lakes) may be unmapped.",
        ],
    }
    (WEB_DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] meta.json")

    # size report
    total = sum((WEB_DATA / f).stat().st_size for f in
                ["zones.json","model.json","reco.json","validation.json","meta.json"])
    print(f"[done] web/data total: {total/1000:.0f} KB")


if __name__ == "__main__":
    main()