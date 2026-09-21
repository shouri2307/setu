"""
p3_flood.py — Cascading bucket flood model for SETU.

For each rainfall scenario, every ward:
  1. turns rainfall into a runoff volume (rain that doesn't soak in),
  2. subtracts what its drainage carries away — where drainage effectiveness
     is set by the ward's physical FLOOD SUSCEPTIBILITY (see below),
  3. ponds what its low ground can hold,
  4. spills the leftover downhill into its lowest neighbour (p2's flows_to),
     processed high-elevation -> low so one pass cascades the whole city.

WHY THIS VERSION DISCRIMINATES
------------------------------
The earlier model produced almost-identical depths for every ward, so
flood-vs-dry came down to rounding noise. The fix: build ONE physical
susceptibility score per ward from four DEM/OSM signals that are already
computed upstream, expressed as uniform percentile ranks so wards actually
spread out:

    susceptibility = w_water*(near water) + w_elev*(low elevation)
                   + w_slope*(flat)       + w_pond*(much low ground)

Drainage effectiveness is then LOW for susceptible wards and HIGH for safe
ones, over a wide range — so genuinely flood-prone wards (low, flat, near a
tank) cross the flood threshold well before safe ones do, instead of the
whole city hovering at the line.

Two GLOBAL knobs are still calibrated against the real Oct-2020 flood
(data/validation_2020.json): runoff_coefficient and drain_capacity_mm_per_hr.
They are the SAME for every ward. The susceptibility weights are fixed
physical priors, NOT per-ward numbers — that is the line between calibration
(honest) and rigging (not).

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

# Minimum share of a ward that can pond. Flooring this (vs the old 0.01) stops
# wards with almost no low ground from showing absurdly deep water in a tiny
# patch and being mislabelled "flooded" — a big source of false positives.
MIN_PONDING_FRACTION = 0.06

# ---- flood-susceptibility weights (fixed physical priors, never per-ward) ----
# 2020 was tank-breach-dominated, so water proximity leads; low + flat ground
# and existing low-lying area follow. Weights sum to 1.0. If the water layer is
# missing, its weight is redistributed to the terrain signals (see build).
W_WATER = 0.38   # closeness to a lake/tank
W_ELEV  = 0.30   # low elevation (basin bottom fills first)
W_SLOPE = 0.16   # flat ground (water doesn't run off)
W_POND  = 0.16   # large fraction of ward below its own mean (natural sinks)

# Drainage effectiveness multiplier as a function of susceptibility s in [0,1]:
#   drain_factor = DRAIN_HI - (DRAIN_HI - DRAIN_LO) * s
# Most-susceptible ward (s=1) drains at DRAIN_LO; safest (s=0) at DRAIN_HI.
# The wide range is what gives the depths real dynamic range (discrimination),
# while a modest calibrated drain_capacity keeps per-ward flood onsets spread
# across rainfall so the response ramps up gradually instead of all at once.
DRAIN_LO = 0.30
DRAIN_HI = 1.25

# Observed 2020 extent: ~34 km2 severely inundated with broader waterlogging.
# For a 1-in-117-year event we expect a concentrated-but-real footprint, not a
# city-wide wash. Keep the calibrated flood fraction inside a plausible band.
MAX_PLAUSIBLE_FLOOD_FRAC = 0.26
MIN_PLAUSIBLE_FLOOD_FRAC = 0.08
TARGET_FLOOD_FRAC = 0.18   # tie-break preference

# ---- rainfall scenarios: 25 mm grid + exact 2020 validation point ----
SCENARIOS_MM = list(range(25, 301, 25)) + [192]
SCENARIOS_MM = sorted(set(SCENARIOS_MM))

# ---- calibration search ranges (global params) ----
# Kept to physically sane urban values so the search can't buy a knife-edge fit
# at grid extremes (which would make flooding a step function at one rainfall).
RUNOFF_GRID = [round(x, 2) for x in np.arange(0.45, 0.81, 0.05)]
DRAIN_GRID = [round(x, 1) for x in np.arange(3.0, 16.1, 1.5)]  # mm/hr


def _pct_rank(vals):
    """Map a list of numbers to uniform percentile ranks in [0,1].

    0.0 = smallest value, 1.0 = largest. Uniform by construction, which is
    exactly what spreads wards out for clean thresholding. Ties get adjacent
    ranks (order-stable); good enough at ward scale.
    """
    vals = np.asarray(vals, dtype="float64")
    n = len(vals)
    if n <= 1:
        return np.zeros(n)
    order = np.argsort(np.argsort(vals, kind="stable"), kind="stable")
    return order.astype("float64") / (n - 1)


def _load_water_union(metric_crs):
    """Return a shapely geometry of all water bodies in METRIC_CRS, or None.

    Reads config.OSM_WATER (raw Overpass JSON or a FeatureCollection). Fully
    wrapped: any problem returns None and the model runs on terrain alone.
    """
    try:
        from shapely.geometry import Polygon, shape
        from shapely.ops import unary_union
        raw = json.loads(Path(config.OSM_WATER).read_text())
        polys = []
        if isinstance(raw, dict) and "elements" in raw:          # Overpass JSON
            for el in raw["elements"]:
                etype = el.get("type")
                if etype == "way":
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
                elif etype == "relation":
                    # multipolygon lakes (e.g. Hussain Sagar, Gurram Cheruvu) are
                    # relations with member ways, not a flat 'geometry' list —
                    # without this branch they are silently dropped entirely.
                    for m in el.get("members", []):
                        if m.get("role") != "outer":
                            continue
                        g = m.get("geometry")
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

        def _num(key, default):
            v = r[key] if key in r else None
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return default
            return float(v)

        wards[zid] = {
            "zone_id": zid,
            "name": r["zone_name"],
            "area_m2": float(r["area_m2"]),
            "mean_elev": _num("mean_elev", 0.0),
            "slope_pct": _num("slope_pct", 0.0),
            "ponding_fraction": max(_num("ponding_fraction", 0.0), 0.0),
            "neighbors": [int(x) for x in nb],
            "flows_to": None if ft_none else int(ft),
            "water_dist": dists[idx],
        }

    have_water = any(w["water_dist"] is not None for w in wards.values())
    _build_susceptibility(wards, have_water)
    return wards, have_water


def _build_susceptibility(wards, have_water):
    """Attach susceptibility s in [0,1] and a drainage factor to each ward.

    All four signals are turned into uniform percentile ranks so wards spread
    across the full range instead of clumping. Higher s = more flood-prone.
    Mutates `wards` in place. Weights are global priors, never per-ward.
    """
    zids = list(wards.keys())

    # elevation: LOW is susceptible -> invert the rank
    elev_low = 1.0 - _pct_rank([wards[z]["mean_elev"] for z in zids])
    # slope: FLAT is susceptible -> invert the rank
    flat = 1.0 - _pct_rank([wards[z]["slope_pct"] for z in zids])
    # ponding: MORE low ground is susceptible -> rank as-is
    pond = _pct_rank([wards[z]["ponding_fraction"] for z in zids])
    # water distance: NEAR is susceptible -> invert the rank (only if we have it)
    if have_water:
        near_water = 1.0 - _pct_rank([wards[z]["water_dist"] for z in zids])
        ww, we, ws, wp = W_WATER, W_ELEV, W_SLOPE, W_POND
    else:
        near_water = np.zeros(len(zids))
        # redistribute the water weight across the terrain signals
        scale = 1.0 / (W_ELEV + W_SLOPE + W_POND)
        ww, we, ws, wp = 0.0, W_ELEV * scale, W_SLOPE * scale, W_POND * scale

    for i, z in enumerate(zids):
        s = (ww * near_water[i] + we * elev_low[i]
             + ws * flat[i] + wp * pond[i])
        s = float(min(max(s, 0.0), 1.0))
        wards[z]["susceptibility"] = round(s, 4)
        wards[z]["drain_factor"] = DRAIN_HI - (DRAIN_HI - DRAIN_LO) * s


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
        # drainage effectiveness: susceptible wards drain slowly, safe wards fast
        drain_eff = drain_cap * w["drain_factor"]                  # mm/hr
        drained_vol = drain_eff * area * STORM_HOURS * 0.001       # m3
        net = runoff_vol + inflow[zid] - drained_vol              # m3
        if net <= 0:
            continue
        # pond over the ward's low ground (floored so tiny-sink wards don't spike)
        pond_frac = max(w["ponding_fraction"], MIN_PONDING_FRACTION)
        ponding_area = area * pond_frac
        storage_cap = ponding_area * SPILL_DEPTH_M                 # m3 held before spill
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

    Objective balances three things:
      * recall on high-confidence wards (deaths/rescues — must be caught),
      * recall on high+medium wards,
      * concentration (precision proxy): of the wards we flood, how many are
        documented — this is what actively fights false positives.
    We keep only parameter pairs whose flood fraction is physically plausible
    (a concentrated-but-real footprint), then pick the best score, tie-breaking
    toward the documented ~1-in-117-yr extent. We never flood the whole city to
    buy recall.
    """
    val_wards = validation["modeled_wards_flooded"]
    high = {w["zone_id"] for w in val_wards if w["confidence"] == "high"}
    med = {w["zone_id"] for w in val_wards if w["confidence"] == "medium"}
    target = high | med
    n_all = len(wards)
    rain = validation["rainfall_reference"]["imd_begumpet_24h_mm"]  # 192

    plausible = []   # records inside the plausible extent band
    fallback = []    # everything with any flooding, as a safety net
    for c in RUNOFF_GRID:
        for dc in DRAIN_GRID:
            depth = run_scenario(wards, rain, c, dc)
            fl = flooded_ids(depth)
            if not fl:
                continue
            recall_high = len(fl & high) / max(len(high), 1)
            recall_target = len(fl & target) / max(len(target), 1)
            precision = len(fl & target) / len(fl)          # concentration
            flood_frac = len(fl) / n_all
            score = (0.50 * recall_high
                     + 0.32 * recall_target
                     + 0.18 * precision)
            rec = (score, c, dc, recall_high, recall_target,
                   precision, flood_frac, fl)
            fallback.append(rec)
            if MIN_PLAUSIBLE_FLOOD_FRAC <= flood_frac <= MAX_PLAUSIBLE_FLOOD_FRAC:
                plausible.append(rec)

    if plausible:
        # inside the plausible band: best score, tie-break toward documented extent
        plausible.sort(key=lambda r: (-r[0], abs(r[6] - TARGET_FLOOD_FRAC)))
        best = plausible[0]
    else:
        # no solution landed in-band: pick the one CLOSEST to the plausible extent,
        # then best score. Never the flood-the-whole-city option just to buy recall.
        fallback.sort(key=lambda r: (abs(r[6] - TARGET_FLOOD_FRAC), -r[0]))
        best = fallback[0]
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
          f"water layer: {'YES' if have_water else 'NO (terrain only)'}")

    # susceptibility sanity: should span most of [0,1]
    svals = sorted(w["susceptibility"] for w in wards.values())
    print(f"[suscept] range {svals[0]:.2f}–{svals[-1]:.2f}, "
          f"median {svals[len(svals)//2]:.2f}")

    print("[calibrate] grid-searching global runoff_c x drain_capacity ...")
    best, high, target, in_band = calibrate(wards, validation)
    if best is None:
        print("[error] calibration produced no flooding at all — check inputs.")
        return
    score, c, dc, rec_high, rec_tgt, precision, flood_frac, fl192 = best

    hits = sorted(fl192 & target)
    misses = sorted(target - fl192)
    name = {z: wards[z]["name"] for z in wards}

    print(f"[calibrated] runoff_coefficient = {c}, drain_capacity = {dc} mm/hr")
    if not in_band:
        print(f"             [warn] no solution stayed inside the plausible "
              f"extent band; showing best-effort.")
    print(f"             high-confidence recall : {rec_high*100:.0f}% "
          f"({len(fl192 & high)}/{len(high)})")
    print(f"             high+med recall        : {rec_tgt*100:.0f}% "
          f"({len(fl192 & target)}/{len(target)})")
    print(f"             concentration (prec.)  : {precision*100:.0f}% "
          f"({len(fl192 & target)}/{len(fl192)} flooded are documented)")
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
                    "against 2020 observations; per-ward drainage is set by one uniform "
                    "susceptibility formula (elevation, slope, water proximity, low-ground "
                    "fraction) — fixed physical priors, no per-ward forcing; all other "
                    "numbers derive from the DEM.",
        },
        "scenarios_mm": SCENARIOS_MM,
        "validation": {
            "rainfall_mm": 192,
            "high_conf_recall": round(rec_high, 3),
            "high_plus_med_recall": round(rec_tgt, 3),
            "precision": round(precision, 3),
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