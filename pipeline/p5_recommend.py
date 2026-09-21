"""
p5_recommend.py — Rule-based Japanese-intervention recommender for SETU.

For each ward, score every intervention by HARD constraint checks against the
ward's real attributes (slope, size, water proximity, arterial roads, flood
severity, density proxy), then rank the ones that fit by a weighted blend of
impact / cost / speed. Records WHY each was included and WHY others were
excluded — the exclusion text is what proves the tool isn't giving the same
answer everywhere.

Fully explainable, no LLM. Reads:
  data/zones_enriched.geojson, data/scenarios.json, data/interventions.json,
  data/network.json (optional, for arterial presence)
Writes: data/recommendations.json

Run from project root:  python pipeline/p5_recommend.py
"""

import sys
import json
from pathlib import Path

import numpy as np
import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

METRIC_CRS = "EPSG:32644"

# priority weights (exposed as UI sliders later): impact / cost / speed.
# Impact is weighted highest so a cheap warning can't outrank real flood
# reduction in a severely flooded ward.
DEFAULT_WEIGHTS = {"impact": 0.62, "cost": 0.20, "speed": 0.18}

COST_SCORE = {"very_low": 1.0, "low": 0.8, "medium": 0.55, "high": 0.3, "very_high": 0.1}
SPEED_SCORE = {"months": 1.0, "years": 0.4, "decade": 0.1}
CONF_SCORE = {"high": 1.0, "medium": 0.7, "low": 0.4}
SEV_ORDER = {"none": 0, "mild": 1, "moderate": 2, "severe": 3}


def classify_wards():
    """Attach a real-data profile to every ward."""
    gdf = gpd.read_file(config.DATA / "zones_enriched.geojson")
    if gdf.crs is None:
        gdf.set_crs("EPSG:4326", inplace=True)

    # water proximity: reuse p3's water layer if present, else mark unknown
    water_rank = _water_ranks(gdf)

    # arterial presence per ward from network.json baseline (reachable => has road)
    arterial = _arterial_presence(gdf)
    cutoff = _hospital_cutoff(gdf)   # wards cut off from hospitals at 192mm

    areas = gdf["area_m2"].astype(float).values
    a_lo, a_hi = np.percentile(areas, 33), np.percentile(areas, 66)

    # flood severity per ward from scenarios at the 2020 level (192 mm).
    # RELATIVE severity: rank the flooded wards by depth so the worst-hit become
    # "severe" even though Hyderabad's absolute depths are shallow. Riverfront
    # wards and wards cut off from hospitals are bumped up a level — they are the
    # priority cases that justify the heaviest interventions.
    scen = json.loads((config.DATA / "scenarios.json").read_text(encoding="utf-8"))
    depths192 = scen["scenarios"].get("192", {})
    fthr = scen.get("params", {}).get("flood_threshold_m", 0.12)
    flooded_depths = sorted(float(d) for d in depths192.values() if float(d) >= fthr)
    if flooded_depths:
        q33 = flooded_depths[int(len(flooded_depths)*0.5)]
        q66 = flooded_depths[int(len(flooded_depths)*0.8)]
    else:
        q33 = q66 = 9e9

    wards = {}
    for i, (_, r) in enumerate(gdf.iterrows()):
        zid = int(r["zone_id"])
        area = float(r["area_m2"])
        size_class = "large" if area >= a_hi else ("small" if area < a_lo else "medium")
        slope = float(r["slope_pct"]) if r["slope_pct"] is not None else 0.0
        d = float(depths192.get(str(zid), 0.0))
        # relative base severity
        if d < fthr: severity = "none"
        elif d >= q66: severity = "severe"
        elif d >= q33: severity = "moderate"
        else: severity = "mild"
        wr = water_rank.get(zid, None)
        water_adjacent = bool(wr is not None and wr <= 0.20)   # closest 20% to water
        # boosters: riverfront or hospital-cut-off wards are worse than depth alone
        levels = ["none", "mild", "moderate", "severe"]
        if severity != "none":
            bump = 0
            if water_adjacent: bump += 1
            if cutoff.get(zid, False): bump += 1
            severity = levels[min(levels.index(severity) + bump, 3)]
        # density proxy: small wards are the dense urban core (labelled an estimate)
        density_class = "dense" if size_class == "small" else "mixed"
        wards[zid] = {
            "zone_id": zid, "name": r["zone_name"],
            "area_m2": round(area, 0), "slope_pct": round(slope, 3),
            "size_class": size_class, "slope": slope,
            "severity": severity, "flood_depth_m": round(d, 3),
            "water_adjacent": water_adjacent,
            "has_arterial": bool(arterial.get(zid, True)),
            "cut_off": bool(cutoff.get(zid, False)),
            "density_class": density_class,
        }
    return wards


def _water_ranks(gdf):
    """Per-ward closeness-to-water rank in [0,1] (0=closest). {} if no layer."""
    try:
        from shapely.geometry import Polygon, shape
        from shapely.ops import unary_union
        raw = json.loads(Path(config.OSM_WATER).read_text(encoding="utf-8"))
        polys = []
        if isinstance(raw, dict) and "elements" in raw:
            for el in raw["elements"]:
                g = el.get("geometry")
                if not g or len(g) < 4: continue
                c = [(p["lon"], p["lat"]) for p in g]
                if c[0] != c[-1]: c.append(c[0])
                try:
                    p = Polygon(c)
                    if p.is_valid and p.area > 0: polys.append(p)
                except Exception: continue
        if not polys: return {}
        wu = unary_union(list(gpd.GeoSeries(polys, crs="EPSG:4326").to_crs(METRIC_CRS)))
        gm = gdf.to_crs(METRIC_CRS)
        dists = np.array([g.distance(wu) for g in gm.geometry])
        lo, hi = dists.min(), dists.max()
        span = (hi - lo) or 1.0
        return {int(gdf.iloc[i]["zone_id"]): (dists[i]-lo)/span for i in range(len(gdf))}
    except Exception:
        return {}


def _arterial_presence(gdf):
    """True if the ward sits on the main road network (from network.json)."""
    try:
        net = json.loads((config.DATA / "network.json").read_text(encoding="utf-8"))
        base = net["baseline_km"]
        # a ward with a finite baseline distance is on the arterial network
        return {int(z): (v is not None) for z, v in base.items()}
    except Exception:
        return {}


def _hospital_cutoff(gdf):
    """True if the ward is cut off from hospitals at the 192 mm scenario."""
    try:
        net = json.loads((config.DATA / "network.json").read_text(encoding="utf-8"))
        cut = set(net["scenarios"]["192"]["cut_off_ids"])
        return {int(z): (int(z) in cut) for z in
                [int(r["zone_id"]) for _, r in gdf.iterrows()]}
    except Exception:
        return {}


def check(interv, w):
    """Return (suitable_bool, reasons_pass, reason_fail)."""
    req = interv.get("requires", {})
    passes, fail = [], None

    if req.get("needs_arterial") and not w["has_arterial"]:
        return False, [], "needs an arterial road corridor; ward has none"
    if req.get("needs_arterial") and w["has_arterial"]:
        passes.append("has arterial road access")

    if "max_slope_pct" in req:
        if w["slope"] > req["max_slope_pct"]:
            return False, [], f"needs slope below {req['max_slope_pct']}%; ward is {w['slope_pct']}%"
        passes.append(f"slope {w['slope_pct']}% within limit")
    if "min_slope_pct" in req:
        if w["slope"] < req["min_slope_pct"]:
            return False, [], f"needs slope above {req['min_slope_pct']}% (steep terrain); ward is {w['slope_pct']}%"
        passes.append(f"slope {w['slope_pct']}% steep enough")

    if "min_size_class" in req:
        order = {"small": 0, "medium": 1, "large": 2}
        if order[w["size_class"]] < order[req["min_size_class"]]:
            return False, [], f"needs a {req['min_size_class']} area; ward is {w['size_class']}"
        passes.append(f"{w['size_class']} area")
    if req.get("needs_open_land") and w["size_class"] != "large":
        return False, [], "needs open land; ward has little spare space"

    if req.get("needs_water_adjacent") and not w["water_adjacent"]:
        return False, [], "needs to be river/lake-adjacent; ward is not"
    if req.get("needs_water_adjacent") and w["water_adjacent"]:
        passes.append("adjacent to water body")

    if "min_severity" in req:
        if SEV_ORDER[w["severity"]] < SEV_ORDER[req["min_severity"]]:
            return False, [], f"aimed at {req['min_severity']}+ flooding; ward is {w['severity']}"
        passes.append(f"{w['severity']} flooding justifies it")
    if "max_severity" in req:
        if SEV_ORDER[w["severity"]] > SEV_ORDER[req["max_severity"]]:
            return False, [], f"suited to {req['max_severity']}-or-milder flooding; ward is {w['severity']}"
        passes.append(f"{w['severity']} flooding suits it")

    if req.get("min_density_class") == "dense" and w["density_class"] != "dense":
        return False, [], "aimed at dense built-up areas; ward is more mixed"
    if req.get("min_density_class") == "dense" and w["density_class"] == "dense":
        passes.append("dense built-up area")

    if not passes:
        passes.append("no blocking site constraints")
    return True, passes, None


# scale of each intervention — impact peaks when scale matches flood severity
SCALE = {
    "underground_reservoir": "large", "mega_discharge_channel": "large",
    "multipurpose_retention_basin": "large", "super_levee": "large",
    "river_widening": "large", "basin_flood_management": "large",
    "comprehensive_flood_control": "large",
    "sabo_check_dam": "medium", "xrain_radar": "medium",
    "permeable_pavement": "medium", "building_rainwater_storage": "medium",
    "schoolyard_park_storage": "small", "infiltration_inlets": "small",
    "hazard_maps": "small",
}
# how well a given scale fits a given severity (big works are overkill for mild
# flooding; small measures can't solve severe flooding)
SCALE_FIT = {
    "severe":   {"large": 1.0, "medium": 0.65, "small": 0.35},
    "moderate": {"large": 0.75, "medium": 1.0, "small": 0.7},
    "mild":     {"large": 0.4, "medium": 0.8, "small": 1.0},
    "none":     {"large": 0.3, "medium": 0.4, "small": 0.5},
}


def impact_score(interv, w):
    """How much this intervention helps THIS ward (0..1). Peaks when the
    intervention's scale matches the ward's flood severity and its mechanism
    matches the ward's flood driver."""
    base = CONF_SCORE[interv["effect"]["confidence"]]
    red = interv["effect"]["reduces"]
    match = 0.6
    if red == "river_overflow" and w["water_adjacent"]: match = 1.0
    elif red in ("peak_volume", "runoff_volume"): match = 0.85
    elif red == "exposure": match = 0.4   # warning/policy: real but not volume removal
    fit = SCALE_FIT[w["severity"]][SCALE.get(interv["id"], "medium")]
    return round(base * match * fit, 3)


def score_ward(w, interventions, weights):
    ranked, excluded = [], []
    for iv in interventions:
        ok, passes, fail = check(iv, w)
        if not ok:
            excluded.append({"id": iv["id"], "name_en": iv["name_en"], "reason": fail})
            continue
        imp = impact_score(iv, w)
        cost = COST_SCORE[iv["cost_band"]]
        speed = SPEED_SCORE[iv["time_to_build"]]
        final = round(weights["impact"]*imp + weights["cost"]*cost + weights["speed"]*speed, 3)
        ranked.append({
            "id": iv["id"], "name_en": iv["name_en"], "name_jp": iv["name_jp"],
            "romaji": iv["romaji"], "category": iv["category"],
            "example": iv["real_example"]["name"], "operator": iv["real_example"]["operator"],
            "cost_band": iv["cost_band"], "time_to_build": iv["time_to_build"],
            "impact": imp, "score": final,
            "why": f"{iv['name_en']} ranked here for {w['name']}: " + "; ".join(passes) + ".",
        })
    ranked.sort(key=lambda x: -x["score"])
    return ranked, excluded


def main():
    print("=== SETU p5_recommend ===")
    for f in [config.DATA / "zones_enriched.geojson", config.DATA / "scenarios.json",
              config.DATA / "interventions.json"]:
        if not Path(f).exists():
            print(f"[error] missing {f}."); return

    wards = classify_wards()
    lib = json.loads((config.DATA / "interventions.json").read_text(encoding="utf-8"))["interventions"]
    print(f"[load] {len(wards)} wards, {len(lib)} interventions")

    recs = {}
    top_counter = {}
    for zid, w in wards.items():
        ranked, excluded = score_ward(w, lib, DEFAULT_WEIGHTS)
        recs[str(zid)] = {
            "zone_id": zid, "name": w["name"],
            "profile": {k: w[k] for k in ["size_class","slope_pct","severity",
                                          "water_adjacent","has_arterial","density_class"]},
            "ranked": ranked, "excluded": excluded,
        }
        if ranked:
            top_counter[ranked[0]["id"]] = top_counter.get(ranked[0]["id"], 0) + 1

    out = {
        "weights": DEFAULT_WEIGHTS,
        "top_pick_distribution": top_counter,
        "recommendations": recs,
    }
    (config.DATA / "recommendations.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] wrote recommendations.json")

    # DIVERSITY REPORT — proves it's not one-size-fits-all
    print(f"\n[diversity] {len(top_counter)} different interventions appear as the #1 pick:")
    id2name = {iv["id"]: iv["name_en"] for iv in lib}
    for iid, n in sorted(top_counter.items(), key=lambda x: -x[1]):
        print(f"     {n:3d} wards -> {id2name[iid]}")


if __name__ == "__main__":
    main()