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

    # --- illustrative real-world cost & build-time estimates ---
    # Order-of-magnitude planning figures, NOT a quantity survey. Grounded in comparable Indian
    # urban stormwater/infrastructure unit-cost ranges (drain/tunnel/basin/RWH-mandate benchmarks).
    # scale: 'length' -> effective corridor length = sqrt(ward area); 'area' -> ward area directly;
    # 'household' -> estimated households from ward area x an assumed density band; 'flat' -> fixed,
    # not ward-scaled (shared/admin infrastructure).
    COST_MODEL = {
        "underground_reservoir":     ("length",    120, 220),   # Rs crore per km of tunnel corridor
        "mega_discharge_channel":    ("length",    280, 450),
        "multipurpose_retention_basin": ("area_frac", 0.03, 15, 30),  # footprint frac of ward, Rs cr/hectare
        "schoolyard_park_storage":   ("sites",     1.5, 3.0),   # Rs crore per site, ~1 site per 3km2
        "building_rainwater_storage": ("household", 18000, 35000),  # Rs per household (India RWH mandate range)
        "permeable_pavement":        ("length",    2, 4),
        "infiltration_inlets":       ("length",    0.4, 0.9),
        "super_levee":               ("length",    70, 130),
        "river_widening":            ("length",    35, 70),
        "sabo_check_dam":            ("flat",      2.5, 6),
        "hazard_maps":               ("flat",      0.08, 0.25),
        "xrain_radar":               ("flat_shared", 3, 6),
        "basin_flood_management":    ("area",      4, 9),       # Rs crore per km2 of ward
        "comprehensive_flood_control": ("area",    6, 12),
    }
    DENSITY_PPL_KM2 = {"dense": 25000, "mixed": 12000}   # assumed GHMC ward density band (stated assumption)
    TIME_RANGES = {
        ("months", "small"): "8-14 months", ("months", "medium"): "10-16 months", ("months", "large"): "12-20 months",
        ("years", "small"): "2-3 years", ("years", "medium"): "2.5-4 years", ("years", "large"): "3-5 years",
        ("decade", "small"): "6-10 years", ("decade", "medium"): "8-11 years", ("decade", "large"): "8-12 years",
    }

    def cost_time_estimate(iv_id, time_band, area_km2, size_class, density_class):
        m = COST_MODEL.get(iv_id)
        time_label = TIME_RANGES.get((time_band, size_class), TIME_RANGES.get((time_band, "medium")))
        if not m:
            return None
        kind = m[0]
        if kind == "length":
            length_km = max(0.3, area_km2 ** 0.5)
            lo, hi = length_km * m[1], length_km * m[2]
        elif kind == "area_frac":
            _, frac, cr_lo, cr_hi = m
            ha = area_km2 * 100 * frac
            lo, hi = ha * cr_lo, ha * cr_hi
        elif kind == "sites":
            n = max(1, round(area_km2 / 3))
            lo, hi = n * m[1], n * m[2]
        elif kind == "household":
            hh = (area_km2 * DENSITY_PPL_KM2.get(density_class, 12000)) / 4.5
            lo, hi = hh * m[1] / 1e7, hh * m[2] / 1e7   # Rs crore
        elif kind == "area":
            lo, hi = area_km2 * m[1], area_km2 * m[2]
        elif kind in ("flat", "flat_shared"):
            lo, hi = m[1], m[2]
        else:
            return None
        lo, hi = max(lo, 0.02), max(hi, lo * 1.3)
        if hi < 1:
            cost_label = f"Rs {lo*100:.0f}-{hi*100:.0f} lakh"
        else:
            cost_label = f"Rs {lo:.1f}-{hi:.1f} crore" if hi < 20 else f"Rs {lo:.0f}-{hi:.0f} crore"
        if kind == "flat_shared":
            cost_label += " (shared citywide network, allocated share)"
        return {"cost_label": cost_label, "time_label": time_label}

    zones_area = {int(f["properties"]["zone_id"]): float(f["properties"]["area_m2"]) / 1e6
                  for f in json.loads((config.DATA / "zones_enriched.geojson").read_text(encoding="utf-8"))["features"]}

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
        area_km2 = zones_area.get(int(zid), 3.0)
        prof = r["profile"]
        for x in r["ranked"][:5]:
            what = explain.get(x["id"]) or lib.get(x["id"], {}).get("mechanism") or ""
            if not what:
                missing_what += 1
            est = cost_time_estimate(x["id"], x["time_to_build"], area_km2,
                                      prof.get("size_class", "medium"), prof.get("density_class", "mixed"))
            ranked_out.append({"id": x["id"], "name_en": x["name_en"], "name_jp": x["name_jp"],
                        "romaji": x["romaji"], "category": x["category"],
                        "example": x["example"], "operator": x["operator"],
                        "cost_band": x["cost_band"], "time_to_build": x["time_to_build"],
                        "impact": x["impact"], "score": x["score"], "why": x["why"],
                        "what": what, "est": est,
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

    # --- documented evidence per ward: real news citations (link out, never re-host images —
    # avoids copyright/misrepresentation risk of embedding press photos on a public deployment) ---
    import csv
    ev_rows = list(csv.DictReader(open(config.ROOT / "research" / "labels.csv", encoding="utf-8")))
    evidence = {}
    for row in ev_rows:
        z = row["ward_id"]
        urls = [u.strip() for u in row["source_urls"].split("|") if u.strip().startswith("http")]
        if not urls:
            continue
        evidence.setdefault(z, []).append({
            "event": row["event"], "locality": row["locality_named"],
            "rain_note": row["city_rain_mm_note"], "sources": urls,
        })
    (WEB_DATA / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] evidence.json  ({len(evidence)} wards with a documented news report)")

    # --- validation ---
    # v4: the 2020 view uses inundation-only labels harvested in research/labels.csv.
    # "high_conf" = ward also named as flooded in a DIFFERENT event (repeat flooder).
    import csv
    val = json.loads((config.DATA / "validation_2020.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader(open(config.ROOT / "research" / "labels.csv", encoding="utf-8")))
    ev20 = {int(r["ward_id"]) for r in rows if r["event"] == "2020-10-13"}
    other = {int(r["ward_id"]) for r in rows if r["event"] != "2020-10-13"}
    vslim = {
        "event": "October 2020 Hyderabad floods (inundation reports only)",
        "rainfall_mm": val["rainfall_reference"]["imd_begumpet_24h_mm"],
        "flooded_ids": sorted(ev20),
        "high_conf_ids": sorted(ev20 & other),
        "outside": [o["area"] for o in val["flooded_areas_outside_modeled_wards"]],
    }
    (WEB_DATA / "validation.json").write_text(json.dumps(vslim), encoding="utf-8")
    print(f"[ok] validation.json  ({len(vslim['flooded_ids'])} documented flooded wards, "
          f"{len(vslim['high_conf_ids'])} also flooded in another event)")

    # --- meta: limitations text for the panel ---
    p = scen["params"]
    v = scen.get("validation", {})
    ev_txt = ", ".join(sorted(v.get("events_used", {}).keys()))
    meta = {
        "title": "SETU — Hyderabad Monsoon Flood & Japanese Intervention Planner",
        "resolution": "145 GHMC wards (open data; the city's 16 stormwater zones are not public)",
        "limitations": [
            "Modelled at ward resolution, not street level — needs GHMC's private drain network for finer.",
            f"Which wards flood first is LEARNED from terrain & drainage features using flooded localities from {len(v.get("events_used", {}))} real floods ({ev_txt}).",
            f"Tested on floods it never saw (leave-one-event-out): AUC {v.get('loeo_auc_mean','?')} (0.5 = coin flip), and {v.get('loeo_auc_within_size_mean','?')} when comparing wards of similar size, so it is not just 'big wards get named more'. One event (Jun-2026 junction waterlogging in central wards) scored near chance. Useful for ranking, not exact prediction.",
            f"Independent check against GHMC's own published chronic-waterlogging lists (never used in training): AUC {v.get('independent_ghmc_chronic_auc','?')}.",
            f"Independent check against GHMC's official list of 248 flood-vulnerable localities: only weak-to-moderate agreement (AUC {v.get('vulnerable_localities_top_quartile_auc','?')} for the densest quarter of wards) — that list reflects who lives near water, not only where water rose.",
            "The 2020 validation map is NOT independent — 2020 is one of the events the model learned from.",
            "The rainfall scale is anchored to documented extents (~3% of wards at 50 mm, ~20% at 192 mm, ~55% at 300 mm) — an assumption, not learned.",
            "Rain is assumed equal over all wards ('what if X mm fell everywhere'); real storms are uneven (Oct 2020: ~197 mm Begumpet vs ~320 mm Ghatkesar).",
            "Flood records are news-reported place names (presence-only, ~60 ward mentions); unnamed wards are unknown, not dry.",
            "Flood depths are shallow ward-averages; severity is relative to the city distribution.",
            "Intervention 'after' effect is a modelled estimate, not a hydraulic re-simulation.",
            "Water bodies, nalas & roads from OpenStreetMap — some may be unmapped.",
        ],
    }
    meta["tests"] = {
        "by_event": v.get("loeo_auc_by_event", {}),
        "mean": v.get("loeo_auc_mean"),
        "independent_ghmc": v.get("independent_ghmc_chronic_auc"),
        "within_size": v.get("loeo_auc_within_size_mean"),
        "vulnerable_localities": v.get("vulnerable_localities_top_quartile_auc"),
        "old_model": 0.49,
    }
    (WEB_DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] meta.json")

    # size report
    total = sum((WEB_DATA / f).stat().st_size for f in
                ["zones.json","model.json","reco.json","validation.json","meta.json","evidence.json"])
    print(f"[done] web/data total: {total/1000:.0f} KB")


if __name__ == "__main__":
    main()