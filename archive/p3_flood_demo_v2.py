"""
p3_flood.py — Cascading bucket flood model for SETU.

For each rainfall scenario, every ward:
  1. turns rainfall into a runoff volume (rain that doesn't soak in),
  2. subtracts what its storm drains carry away,
  3. ponds what its low ground can hold,
  4. spills the leftover downhill into its lowest neighbour (p2's flows_to),
     processed high-elevation -> low so one pass cascades the whole city.

Two GLOBAL knobs are calibrated against the real Oct-2020 flood
(data/validation_2020.json): runoff_coefficient and drain_capacity_mm_per_hr.
They are the SAME for every ward — never tuned per ward. That is the line
between calibration (honest) and rigging (not).

Reads:  data/zones_enriched.geojson, data/validation_2020.json
Writes: data/scenarios.json

Run from project root:  python pipeline/p3_flood.py
"""

import sys
import json
from pathlib import Path

import numpy as np
import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

# Metric CRS for Hyderabad (UTM zone 44N) — for distances/areas in metres.
METRIC_CRS = "EPSG:32644"

# ---- fixed model assumptions (shown in the UI limitations panel) ----
STORM_HOURS = 6.0            # effective storm duration for drain removal
SPILL_DEPTH_M = 0.5          # max ponding depth a ward holds before spilling downhill
FLOOD_THRESHOLD_M = 0.12     # depth at/above which a ward counts as "flooded"

# Low-lying wards drain more slowly: at the bottom of the basin the downstream
# is already full and the hydraulic gradient is flat, so water lingers. This is
# why the Old City / Chandrayangutta flood first in reality. We scale drainage
# effectiveness with each ward's DEM elevation rank — ONE formula, all wards,
# no per-ward numbers. Lowest ward drains at DRAIN_MIN_FACTOR, highest at 1.0.
DRAIN_MIN_FACTOR = 0.35

# Wards next to lakes/tanks are flood-prone: tank overflow and bund breaches
# push water into them (the Oct-2020 Gurram Cheruvu / Hussain Sagar mechanism,
# which every account of that flood emphasises). Because 2020 was tank-breach-
# dominated, water proximity is the DOMINANT susceptibility signal here, weighted
# above elevation. Nearest-water wards drain at WATER_MIN_FACTOR, farthest at 1.0.
# Same formula for every ward. If the water layer can't be read, this term is
# disabled and the model runs on elevation alone (never crashes).
WATER_MIN_FACTOR = 0.30
WATER_WEIGHT = 0.65   # share of the drainage factor driven by water proximity
ELEV_WEIGHT = 1.0 - WATER_WEIGHT

# Observed 2020 extent: ~34 km2 inundated (Grokipedia/HMDA), ~15-30% of the dense
# core wards. We reject calibrations that flood far more than plausibly occurred.
MAX_PLAUSIBLE_FLOOD_FRAC = 0.45

# ---- rainfall scenarios: 25 mm grid + exact 2020 validation point ----
SCENARIOS_MM = list(range(25, 301, 25)) + [192]
SCENARIOS_MM = sorted(set(SCENARIOS_MM))

# ---- calibration search ranges (global params) ----
RUNOFF_GRID = [round(x, 2) for x in np.arange(0.40, 0.96, 0.05)]
DRAIN_GRID = [round(x, 1) for x in np.arange(4.0, 32.1, 2.0)]  # mm/hr


def _load_water_union(metric_crs):
    """Return a shapely geometry of all water bodies in METRIC_CRS, or None.

    Reads config.OSM_WATER, which is raw Overpass JSON (ways with a 'geometry'
    list of {lat,lon}). Fully wrapped: any problem returns None and the model
    runs on elevation alone. Never raises.
    """
    try:
        from shapely.geometry import Polygon, shape
        from shapely.ops import unary_union
        raw = json.loads(Path(config.OSM_WATER).read_text())
        polys = []
        if isinstance(raw, dict) and "elements" in raw:          # Overpass JSON
            for el in raw["elements"]:
                g = el.get("geometry")
                if not g or len(g) < 4:
                    continue
                coords = [(pt["lon"], pt["lat"]) for pt in g]
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                try:
                    p = Polygon(coords)
                    if p.is_valid and p.area > 0:
                        polys.append(p)
                except Exception:
                    continue
        elif isinstance(raw, dict) and raw.get("type") == "FeatureCollection":
            for f in raw["features"]:
                try:
                    polys.append(shape(f["geometry"]))
                except Exception:
                    continue
        if not polys:
            return None
        gs = gpd.GeoSeries(polys, crs="EPSG:4326").to_crs(metric_crs)
        return unary_union(list(gs.geometry))
    except Exception:
        return None


def load_wards():
    gdf = gpd.read_file(config.DATA / "zones_enriched.geojson")
    if gdf.crs is None:
        gdf.set_crs("EPSG:4326", inplace=True)
    gdf_m = gdf.to_crs(METRIC_CRS)

    # distance from each ward to nearest water body (metres); None if no layer
    water = _load_water_union(METRIC_CRS)
    if water is not None:
        dists = [g.distance(water) for g in gdf_m.geometry]
    else:
        dists = [None] * len(gdf_m)

    wards = {}
    for idx, (_, r) in enumerate(gdf.iterrows()):
        zid = int(r["zone_id"])
        nb = r["neighbors"]
        if isinstance(nb, str):
            nb = json.loads(nb)
        if nb is None:
            nb = []
        nb = list(nb)  # numpy array or list -> plain list
        ft = r["flows_to"]
        ft_none = ft is None or (isinstance(ft, float) and np.isnan(ft))
        wards[zid] = {
            "zone_id": zid,
            "name": r["zone_name"],
            "area_m2": float(r["area_m2"]),
            "mean_elev": float(r["mean_elev"]) if r["mean_elev"] is not None else 0.0,
            "ponding_fraction": max(float(r["ponding_fraction"]), 0.01),  # avoid /0
            "neighbors": [int(x) for x in nb],
            "flows_to": None if ft_none else int(ft),
            "water_dist": dists[idx],
        }

    # elevation rank in [0,1]: 0 = lowest ward in the city, 1 = highest.
    elevs = sorted(w["mean_elev"] for w in wards.values())
    lo, hi = elevs[0], elevs[-1]
    span = (hi - lo) or 1.0
    for w in wards.values():
        w["elev_rank"] = (w["mean_elev"] - lo) / span

    # water-distance rank in [0,1]: 0 = closest to water, 1 = farthest.
    # If no water layer, everyone gets 1.0 (water term disabled).
    have_water = any(w["water_dist"] is not None for w in wards.values())
    if have_water:
        dvals = sorted(w["water_dist"] for w in wards.values())
        dlo, dhi = dvals[0], dvals[-1]
        dspan = (dhi - dlo) or 1.0
        for w in wards.values():
            w["water_rank"] = (w["water_dist"] - dlo) / dspan
    else:
        for w in wards.values():
            w["water_rank"] = 1.0

    return wards, have_water


def run_scenario(wards, rainfall_mm, runoff_c, drain_cap):
    """Return {zone_id: flood_depth_m} for one rainfall level and param pair."""
    inflow = {zid: 0.0 for zid in wards}   # accumulated spill from upstream (m3)
    depth = {zid: 0.0 for zid in wards}

    # process high elevation -> low so upstream spill reaches downstream in one pass
    order = sorted(wards, key=lambda z: wards[z]["mean_elev"], reverse=True)

    for zid in order:
        w = wards[zid]
        area = w["area_m2"]
        runoff_vol = rainfall_mm * area * runoff_c * 0.001          # m3
        # drainage effectiveness: low wards AND near-water wards drain slower.
        # Combine the two physical factors (average) — one formula, all wards.
        elev_factor = DRAIN_MIN_FACTOR + (1 - DRAIN_MIN_FACTOR) * w["elev_rank"]
        water_factor = WATER_MIN_FACTOR + (1 - WATER_MIN_FACTOR) * w["water_rank"]
        # water proximity dominates (2020 was tank-breach-driven); if no water
        # layer, water_rank is 1.0 for all wards so this reduces to elevation.
        drain_eff = drain_cap * (ELEV_WEIGHT * elev_factor
                                 + WATER_WEIGHT * water_factor)
        drained_vol = drain_eff * area * STORM_HOURS * 0.001        # m3
        net = runoff_vol + inflow[zid] - drained_vol               # m3
        if net <= 0:
            continue
        ponding_area = area * w["ponding_fraction"]
        storage_cap = ponding_area * SPILL_DEPTH_M                  # m3 held before spill
        if net <= storage_cap:
            depth[zid] = net / ponding_area
        else:
            depth[zid] = SPILL_DEPTH_M
            spill = net - storage_cap
            tgt = w["flows_to"]
            if tgt is not None and tgt in inflow:
                inflow[tgt] += spill
            # if no downhill target, spill leaves the modelled area (edge of city)
    return depth


def flooded_ids(depth):
    return {zid for zid, d in depth.items() if d >= FLOOD_THRESHOLD_M}


def calibrate(wards, validation):
    """Grid-search the two global params against Oct-2020 observations.

    Honest objective: among parameter pairs that flood a PLAUSIBLE fraction of
    the city (<= MAX_PLAUSIBLE_FLOOD_FRAC, matching the documented ~34 km2
    extent), pick the one that best reproduces the known-flooded wards. We do
    NOT let the search flood the whole city just to guarantee recall — a model
    that floods 78% of Hyderabad proves nothing, even if it "catches" every
    validation ward.
    """
    val_wards = validation["modeled_wards_flooded"]
    high = {w["zone_id"] for w in val_wards if w["confidence"] == "high"}
    med = {w["zone_id"] for w in val_wards if w["confidence"] == "medium"}
    target = high | med
    n_all = len(wards)
    rain = validation["rainfall_reference"]["imd_begumpet_24h_mm"]  # 192

    plausible = []   # (score, c, dc, recall_high, recall_target, flood_frac, flooded)
    fallback = []    # if nothing lands in the plausible band, keep the best-effort
    for c in RUNOFF_GRID:
        for dc in DRAIN_GRID:
            depth = run_scenario(wards, rain, c, dc)
            fl = flooded_ids(depth)
            if not fl:
                continue
            recall_high = len(fl & high) / max(len(high), 1)
            recall_target = len(fl & target) / max(len(target), 1)
            flood_frac = len(fl) / n_all
            # reward catching known-flooded wards; gently prefer a tighter extent
            score = 0.7 * recall_high + 0.3 * recall_target - 0.10 * flood_frac
            rec = (score, c, dc, recall_high, recall_target, flood_frac, fl)
            fallback.append(rec)
            if flood_frac <= MAX_PLAUSIBLE_FLOOD_FRAC:
                plausible.append(rec)

    pool = plausible if plausible else fallback
    # best score; tie-break toward the tighter (smaller) flood extent
    pool.sort(key=lambda r: (-r[0], r[5]))
    best = pool[0]
    in_band = bool(plausible)
    return best, high, target, in_band


def main():
    print("=== SETU p3_flood ===")
    enr = config.DATA / "zones_enriched.geojson"
    val = config.DATA / "validation_2020.json"
    if not enr.exists():
        print(f"[error] {enr} not found. Run p2_zones first.")
        return
    if not val.exists():
        print(f"[error] {val} not found. Add validation_2020.json first.")
        return

    wards, have_water = load_wards()
    validation = json.loads(val.read_text())
    print(f"[load] {len(wards)} wards; "
          f"{len(validation['modeled_wards_flooded'])} validation wards; "
          f"water layer: {'YES' if have_water else 'NO (elevation only)'}")

    print("[calibrate] grid-searching global runoff_c x drain_capacity ...")
    best, high, target, in_band = calibrate(wards, validation)
    if best is None:
        print("[error] calibration produced no flooding at all — check inputs.")
        return
    score, c, dc, rec_high, rec_tgt, flood_frac, fl192 = best

    hits = sorted(fl192 & target)
    misses = sorted(target - fl192)
    name = {z: wards[z]["name"] for z in wards}

    print(f"[calibrated] runoff_coefficient = {c}, drain_capacity = {dc} mm/hr")
    if not in_band:
        print(f"             [warn] no solution kept flooding under "
              f"{MAX_PLAUSIBLE_FLOOD_FRAC*100:.0f}%; showing best-effort.")
    print(f"             high-confidence recall : {rec_high*100:.0f}% "
          f"({len(fl192 & high)}/{len(high)})")
    print(f"             high+med recall        : {rec_tgt*100:.0f}% "
          f"({len(fl192 & target)}/{len(target)})")
    print(f"             wards flooded at 192mm : {len(fl192)}/{len(wards)} "
          f"({flood_frac*100:.0f}%)")
    if misses:
        print(f"             MISSED (reported honestly): "
              f"{[name[z] for z in misses][:8]}")

    # run every scenario with the calibrated params
    scenarios = {}
    for r in SCENARIOS_MM:
        depth = run_scenario(wards, r, c, dc)
        scenarios[str(r)] = {str(z): round(d, 3) for z, d in depth.items() if d > 0.001}

    out = {
        "params": {
            "runoff_coefficient": c,
            "drain_capacity_mm_per_hr": dc,
            "storm_hours": STORM_HOURS,
            "spill_depth_m": SPILL_DEPTH_M,
            "flood_threshold_m": FLOOD_THRESHOLD_M,
            "water_proximity_used": have_water,
            "calibrated_against": "October 2020 floods (192 mm, IMD Begumpet)",
            "note": "runoff_coefficient and drain_capacity are GLOBAL and tuned only "
                    "against 2020 observations; drainage also scales with each ward's "
                    "DEM elevation and distance-to-water by one uniform formula; all "
                    "other numbers derive from the DEM.",
        },
        "scenarios_mm": SCENARIOS_MM,
        "validation": {
            "rainfall_mm": 192,
            "high_conf_recall": round(rec_high, 3),
            "high_plus_med_recall": round(rec_tgt, 3),
            "flood_fraction": round(flood_frac, 3),
            "hits": [{"zone_id": z, "name": name[z]} for z in hits],
            "misses": [{"zone_id": z, "name": name[z]} for z in misses],
        },
        "scenarios": scenarios,
    }
    (config.DATA / "scenarios.json").write_text(json.dumps(out))
    print(f"[ok] wrote scenarios.json ({len(SCENARIOS_MM)} scenarios)")

    # sanity: flooding should rise with rainfall
    counts = [(r, len(flooded_ids(run_scenario(wards, r, c, dc)))) for r in SCENARIOS_MM]
    print("[check] wards flooded by rainfall:",
          ", ".join(f"{r}mm:{n}" for r, n in counts if r in (25, 100, 192, 300)))


if __name__ == "__main__":
    main()
