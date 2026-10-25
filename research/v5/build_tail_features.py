"""Worst-case (tail) terrain features per ward -> research/v5/tail_features.csv
A ward is 'named flooded' if ANY colony in it floods, but the existing features are ward averages. These use the same DEM and the
same hydrology (pysheds, identical to research/build_features.py) but take the lower tail inside each ward.
Fixed in advance: hand_p10, hand_lt1_frac, sink_p95, twi_p90."""
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
from rasterio import features as rfeat
warnings.filterwarnings("ignore")
if not hasattr(np, "in1d"): np.in1d = np.isin
ROOT = Path(__file__).resolve().parent.parent.parent
from pysheds.grid import Grid
DEM = str(ROOT / "data/raw/hyderabad_dem.tif")
gdf = gpd.read_file(ROOT / "data/zones_enriched.geojson").set_crs("EPSG:4326", allow_override=True)
ids = gdf.zone_id.astype(int).tolist()
grid = Grid.from_raster(DEM); dem = grid.read_raster(DEM)
filled = grid.fill_depressions(grid.fill_pits(dem)); inflated = grid.resolve_flats(filled)
fdir = grid.flowdir(inflated); acc = grid.accumulation(fdir); A = np.asarray(acc, dtype="float64")
hand = np.asarray(grid.compute_hand(fdir, inflated, acc > 400), dtype="float64")
dem_a = np.asarray(dem, dtype="float64"); sink = np.clip(np.asarray(filled, dtype="float64") - dem_a, 0, None)
dy, dx = 30.7, 29.5; gy, gx = np.gradient(dem_a, dy, dx); slope = np.hypot(gx, gy)
twi = np.log((A * dx * dy / dx) / np.maximum(slope, 0.005))
lab = rfeat.rasterize([(g, int(i)) for g, i in zip(gdf.geometry, ids)], out_shape=dem_a.shape, transform=grid.affine, fill=-1, dtype="int32")
rows = []
for i in ids:
    m = (lab == i)
    h = hand[m & np.isfinite(hand)]; s = sink[m & np.isfinite(sink)]; t = twi[m & np.isfinite(twi)]
    rows.append({"ward_id": i, "hand_p10": np.percentile(h, 10) if h.size else np.nan, "hand_lt1_frac": (h < 1).mean() if h.size else np.nan,
                 "sink_p95": np.percentile(s, 95) if s.size else np.nan, "twi_p90": np.percentile(t, 90) if t.size else np.nan})
out = pd.DataFrame(rows).set_index("ward_id"); out.round(4).to_csv(ROOT / "research/v5/tail_features.csv")
print(out.describe().T[["mean", "std", "min", "max"]].round(3)); print("NaN:", int(out.isna().sum().sum()))
