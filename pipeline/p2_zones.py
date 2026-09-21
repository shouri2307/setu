"""
p2_zones.py — Enrich zones.geojson with per-ward terrain + adjacency.

Reads:
  data/zones.geojson   (145 GHMC wards, from p1 setup)
  data/raw/hyderabad_dem.tif   (elevation, from p1_fetch)

Computes per ward:
  mean_elev, min_elev   — metres, zonal statistics over the DEM
  slope_pct             — mean slope inside the ward (rise/run, %)
  area_m2               — polygon area in square metres (projected)
  ponding_fraction      — fraction of ward lower than (mean_elev - 1 m)
  neighbors             — list of zone_ids that share a boundary
  flows_to              — neighbor zone_id water spills to (lowest lower neighbour)

Writes:
  data/zones_enriched.geojson

Run from project root:  python pipeline/p2_zones.py
"""

import sys
import json
from pathlib import Path

import numpy as np
import geopandas as gpd
import rasterio
from rasterio.mask import mask as rio_mask

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

# Metric CRS for Hyderabad (UTM zone 44N) — needed for area & slope in metres.
METRIC_CRS = "EPSG:32644"


def _slope_pct_from_window(elev, px_x, px_y, nodata):
    """Mean slope (%) over an elevation array, given pixel size in metres.

    nodata cells (and any non-finite) are set to NaN *before* differencing so the
    huge jump from real elevation to the fill value doesn't create fake cliffs.
    """
    elev = elev.astype("float64").copy()
    if nodata is not None:
        elev[elev == nodata] = np.nan
    elev[~np.isfinite(elev)] = np.nan
    if np.count_nonzero(np.isfinite(elev)) < 4:
        return 0.0
    gy, gx = np.gradient(elev, px_y, px_x)  # metres rise per metre run
    slope = np.sqrt(gx**2 + gy**2)
    with np.errstate(invalid="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            val = np.nanmean(slope) * 100.0
    return float(val) if np.isfinite(val) else 0.0


def main():
    print("=== SETU p2_zones ===")
    zones_path = config.DATA / "zones.geojson"
    if not zones_path.exists():
        print(f"[error] {zones_path} not found. Put the wards file there first.")
        return
    if not config.DEM_FILE.exists():
        print(f"[error] {config.DEM_FILE} not found. Run p1_fetch first.")
        return

    gdf = gpd.read_file(zones_path)
    if gdf.crs is None:
        gdf.set_crs("EPSG:4326", inplace=True)
    print(f"[load] {len(gdf)} wards from zones.geojson")

    # Projected copy for area + metric slope
    gdf_m = gdf.to_crs(METRIC_CRS)
    gdf["area_m2"] = gdf_m.geometry.area.round(1)

    mean_elev, min_elev, slope_pct, ponding = [], [], [], []

    with rasterio.open(config.DEM_FILE) as src:
        dem_crs = src.crs
        # pixel size in metres — approximate from the metric reprojection of the bounds
        # (DEM is in degrees; convert one pixel's degree size to metres at this latitude)
        deg_px_x = abs(src.transform.a)
        deg_px_y = abs(src.transform.e)
        lat = (config.BBOX["south"] + config.BBOX["north"]) / 2
        m_per_deg_lat = 111_320.0
        m_per_deg_lon = 111_320.0 * np.cos(np.radians(lat))
        px_x = deg_px_x * m_per_deg_lon
        px_y = deg_px_y * m_per_deg_lat

        # Reproject wards to the DEM's CRS for masking
        gdf_dem = gdf.to_crs(dem_crs)

        for geom in gdf_dem.geometry:
            try:
                arr, _ = rio_mask(src, [geom.__geo_interface__], crop=True,
                                  filled=True, nodata=src.nodata)
                band = arr[0].astype("float64")
                nod = src.nodata if src.nodata is not None else -9999
                valid = band[(band != nod) & np.isfinite(band)]
            except Exception:
                valid = np.array([])

            if valid.size == 0:
                mean_elev.append(None); min_elev.append(None)
                slope_pct.append(0.0); ponding.append(0.0)
                continue

            me = float(np.mean(valid))
            mn = float(np.min(valid))
            mean_elev.append(round(me, 2))
            min_elev.append(round(mn, 2))
            slope_pct.append(round(_slope_pct_from_window(band, px_x, px_y, nod), 3))
            # ponding: fraction of valid cells more than 1 m below the ward mean
            low = np.count_nonzero(valid < (me - 1.0))
            ponding.append(round(low / valid.size, 3))

    gdf["mean_elev"] = mean_elev
    gdf["min_elev"] = min_elev
    gdf["slope_pct"] = slope_pct
    gdf["ponding_fraction"] = ponding

    # --- adjacency: which wards share a boundary ---
    print("[calc] building adjacency ...")
    sindex = gdf_m.sindex
    neighbors = [[] for _ in range(len(gdf))]
    geoms = list(gdf_m.geometry)
    ids = list(gdf["zone_id"])
    for i, g in enumerate(geoms):
        for j in sindex.query(g, predicate="touches"):
            if j == i:
                continue
            neighbors[i].append(int(ids[j]))
    gdf["neighbors"] = [sorted(set(n)) for n in neighbors]

    # --- flow direction: water spills to the lowest lower-elevation neighbour ---
    elev_by_id = {int(ids[i]): (mean_elev[i] if mean_elev[i] is not None else 9e9)
                  for i in range(len(gdf))}
    flows_to = []
    for i in range(len(gdf)):
        my_elev = mean_elev[i] if mean_elev[i] is not None else 9e9
        lower = [(elev_by_id[n], n) for n in gdf["neighbors"].iloc[i]
                 if elev_by_id[n] < my_elev]
        flows_to.append(int(min(lower)[1]) if lower else None)
    gdf["flows_to"] = flows_to

    out = config.DATA / "zones_enriched.geojson"
    # geopandas can't write list columns to GeoJSON — stash them as JSON strings,
    # then post-process the file back into real arrays for the web app.
    gdf_out = gdf.copy()
    gdf_out["neighbors"] = gdf_out["neighbors"].apply(json.dumps)
    gdf_out.to_file(out, driver="GeoJSON")

    # Post-process the written file:
    #  - neighbors was stashed as a JSON string -> restore to a real array
    #  - flows_to got coerced to float by pandas (None in column) -> back to int
    data = json.loads(out.read_text())
    for feat in data["features"]:
        p = feat["properties"]
        if isinstance(p.get("neighbors"), str):
            p["neighbors"] = json.loads(p["neighbors"])
        ft = p.get("flows_to")
        p["flows_to"] = int(ft) if ft is not None else None
    out.write_text(json.dumps(data))

    # --- quick report ---
    n_flood_prone = sum(1 for p in ponding if p > 0.1)
    print(f"[ok] wrote {out.name}")
    print(f"     mean_elev range: "
          f"{min(e for e in mean_elev if e is not None):.1f} - "
          f"{max(e for e in mean_elev if e is not None):.1f} m")
    print(f"     wards with >10% ponding area: {n_flood_prone}")
    print(f"     avg neighbours per ward: "
          f"{np.mean([len(n) for n in gdf['neighbors']]):.1f}")


if __name__ == "__main__":
    main()