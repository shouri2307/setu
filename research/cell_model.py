"""Colony-scale flood-susceptibility model trained on GHMC's official 'Vulnerable Localities' (exact lat/lon).
Builds 30 m terrain/drainage rasters, samples them at each vulnerable point vs background cells,
evaluates (a) spatial CV on the points, (b) ward-level AUC on the 8 news flood events + GHMC chronic list
(which the model never sees), and writes research/cell_susceptibility.csv (ward score from the point model).
Run: python research/cell_model.py
"""
import sys, json, warnings, os
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio import features as rfeat
from rasterio.windows import from_bounds
from rasterio.warp import reproject, Resampling
from shapely.geometry import LineString, shape
from sklearn.neighbors import KDTree
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")
if not hasattr(np, "in1d"): np.in1d = np.isin
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research"))
import config, water_utils
EXT = ROOT / "research" / "external"
DEM = os.environ.get("DEM_PATH") or str(config.RAW / "hyderabad_dem.tif")
CACHE = Path(os.environ["TEMP"]) / ("cell_rasters_" + Path(DEM).stem + ".npz")

wards = gpd.read_file(config.DATA / "zones_enriched.geojson").set_crs("EPSG:4326", allow_override=True)
ids = wards.zone_id.astype(int).tolist()

def build_rasters():
    from pysheds.grid import Grid
    grid = Grid.from_raster(DEM); dem = grid.read_raster(DEM)
    filled = grid.fill_depressions(grid.fill_pits(dem)); infl = grid.resolve_flats(filled)
    fdir = grid.flowdir(infl); acc = grid.accumulation(fdir)
    A = np.asarray(acc, "float64"); hand = np.asarray(grid.compute_hand(fdir, infl, acc > 400), "float64")
    z = np.asarray(dem, "float64"); sink = np.clip(np.asarray(filled, "float64") - z, 0, None)
    gy, gx = np.gradient(z, 30.7, 29.5); slope = np.hypot(gx, gy)
    twi = np.log((A * 30.7) / np.maximum(slope, 0.005))
    tr = grid.affine; H, W = z.shape
    def box(a, k):                                   # mean filter via integral image
        p = k // 2; ap = np.pad(a, p, mode="edge"); c = np.cumsum(np.cumsum(ap, 0), 1); c = np.pad(c, ((1, 0), (1, 0)))
        return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k])[:H, :W] / (k * k)
    rel15 = z - box(z, 15); rel61 = z - box(z, 61)
    # distance rasters (metres) to channels / water bodies
    ys, xs = np.mgrid[0:H, 0:W]; lon = tr.c + (xs + .5) * tr.a; lat = tr.f + (ys + .5) * tr.e
    X = np.c_[(lon.ravel() - 78.45) * 111320 * np.cos(np.radians(17.4)), (lat.ravel() - 17.4) * 110574]
    def dist_to(mask):
        t = KDTree(X[mask.ravel()]); return t.query(X, k=1)[0].reshape(H, W)
    lines = []
    for el in json.loads((ROOT / "research/osm_waterways.json").read_text())["elements"]:
        g = el.get("geometry")
        if g and len(g) > 1: lines.append(LineString([(p["lon"], p["lat"]) for p in g]))
    for fn in ["channels_strahler3.geojson", "stream_segments.geojson"]:
        for f in json.load(open(EXT / fn, encoding="utf-8"))["features"]:
            try:
                g = shape(f["geometry"]); lines += list(g.geoms) if g.geom_type.startswith("Multi") else [g]
            except Exception: pass
    chan = rfeat.rasterize([(l, 1) for l in lines if l.length > 0], out_shape=(H, W), transform=tr, fill=0, dtype="uint8", all_touched=True).astype(bool)
    polys = []
    wu = water_utils._load_water_union("EPSG:4326")           # metric arg only used for CRS of union
    wgdf = gpd.GeoSeries([wu], crs="EPSG:4326") if wu is not None else None
    wb = json.load(open(EXT / "waterbodies.geojson", encoding="utf-8"))["features"]
    shapes = [(shape(f["geometry"]), 1) for f in wb if f.get("geometry")]
    water = rfeat.rasterize(shapes, out_shape=(H, W), transform=tr, fill=0, dtype="uint8", all_touched=True).astype(bool)
    d_chan = dist_to(chan); d_wat = dist_to(water)
    with rasterio.open("/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N15E078_Map.tif") as ds:
        w = from_bounds(*wards.total_bounds, ds.transform); wc = ds.read(1, window=w); wtr = ds.window_transform(w)
    bu = np.zeros((H, W), "float32")
    reproject((wc == 50).astype("float32"), bu, src_transform=wtr, src_crs="EPSG:4326", dst_transform=tr, dst_crs="EPSG:4326", resampling=Resampling.average)
    lab = rfeat.rasterize([(g, int(i)) for g, i in zip(wards.geometry, ids)], out_shape=(H, W), transform=tr, fill=-1, dtype="int32")
    R = dict(hand=hand, sink=sink, twi=twi, acc=np.log10(A + 1), slope=slope, rel15=rel15, rel61=rel61,
             dchan=np.log1p(d_chan), dwat=np.log1p(d_wat), builtup=bu, lab=lab)
    np.savez_compressed(CACHE, transform=np.array(tr)[:6], **{k: v.astype("float32") if k != "lab" else v for k, v in R.items()})
    return R, tr

if CACHE.exists():
    z = np.load(CACHE); R = {k: z[k] for k in z.files if k != "transform"}; a, b, c, d, e, f = z["transform"]
    from affine import Affine; tr = Affine(a, b, c, d, e, f)
else:
    R, tr = build_rasters()
FEATS = ["hand", "sink", "twi", "acc", "slope", "rel15", "rel61", "dchan", "dwat", "builtup"]
lab = R["lab"]; H, W = lab.shape

# ---- points: official vulnerable localities ----
vl = json.load(open(EXT / "vulnerable_localities.geojson", encoding="utf-8"))["features"]
pts = []
for f in vl:
    lon, lat = f["geometry"]["coordinates"]
    col, row = ~tr * (lon, lat); col, row = int(col), int(row)
    if 0 <= row < H and 0 <= col < W and lab[row, col] >= 0: pts.append((row, col, int(lab[row, col])))
P = np.array(pts); print(f"vulnerable points used: {len(P)} (inside wards)")
Xall = np.stack([R[k] for k in FEATS], -1).astype("float64")
Xall = np.nan_to_num(Xall, nan=0.0, posinf=0.0, neginf=0.0)
Xp = Xall[P[:, 0], P[:, 1]]
rng = np.random.default_rng(0)
inw = np.argwhere(lab >= 0); bg_idx = inw[rng.choice(len(inw), 40000, replace=False)]
Xb = Xall[bg_idx[:, 0], bg_idx[:, 1]]; wb = lab[bg_idx[:, 0], bg_idx[:, 1]]; wp = P[:, 2]

def fit(Xp_, Xb_):
    X = np.vstack([Xp_, Xb_]); y = np.r_[np.ones(len(Xp_)), np.zeros(len(Xb_))]
    sc = StandardScaler().fit(X)
    lg = LogisticRegression(C=0.3, class_weight="balanced", max_iter=3000).fit(sc.transform(X), y)
    rf = RandomForestClassifier(300, min_samples_leaf=25, max_depth=6, class_weight="balanced_subsample", random_state=0, n_jobs=-1).fit(X, y)
    return sc, lg, rf
rk = lambda s: pd.Series(np.asarray(s)).rank().values / len(s)
def cell_score(sc, lg, rf, X):
    return rk(lg.decision_function(sc.transform(X))) + rk(rf.predict_proba(X)[:, 1])

# ---- (a) spatial CV on points: hold out whole wards ----
folds = rng.integers(0, 5, len(ids)); fold_of = dict(zip(ids, folds)); aucs = []
for k in range(5):
    trp = np.array([fold_of[w] != k for w in wp]); trb = np.array([fold_of[w] != k for w in wb])
    sc, lg, rf = fit(Xp[trp], Xb[trb])
    s = cell_score(sc, lg, rf, np.vstack([Xp[~trp], Xb[~trb]])); y = np.r_[np.ones((~trp).sum()), np.zeros((~trb).sum())]
    aucs.append(roc_auc_score(y, s))
print("spatial-CV AUC (point vs random cell, held-out wards):", np.round(aucs, 3), "mean", round(float(np.mean(aucs)), 3))

# ---- final fit on all points; score every cell; aggregate to wards ----
sc, lg, rf = fit(Xp, Xb)
flat = lab.ravel() >= 0; idx = np.where(flat)[0]
Xc = Xall.reshape(-1, len(FEATS))[idx]
score = np.zeros(len(idx)); B = 200000
raw_lg = np.concatenate([lg.decision_function(sc.transform(Xc[i:i + B])) for i in range(0, len(Xc), B)])
raw_rf = np.concatenate([rf.predict_proba(Xc[i:i + B])[:, 1] for i in range(0, len(Xc), B)])
score = rk(raw_lg) + rk(raw_rf); wl = lab.ravel()[idx]
df = pd.DataFrame({"w": wl, "s": score})
agg = pd.DataFrame({"S_mean": df.groupby("w").s.mean(), "S_top25": df.groupby("w").s.apply(lambda v: np.sort(v.values)[-max(1, len(v) // 4):].mean())})
for c in agg.columns: agg[c] = agg[c].rank() / len(agg)
agg.index.name = "ward_id"; agg.reindex(ids).round(4).to_csv(ROOT / "research" / "cell_susceptibility.csv")

# ---- (b) INDEPENDENT test: ward-level AUC vs news events + chronic list (never used in training) ----
L = pd.read_csv(ROOT / "research/labels.csv"); C = set(pd.read_csv(ROOT / "research/labels_chronic.csv").ward_id)
print("\nWard-level AUC of the point-trained model on labels it never saw:")
for col in ["S_mean", "S_top25"]:
    s = agg[col].reindex(ids)
    per = {e: round(roc_auc_score([i in set(g.ward_id) for i in ids], s), 3) for e, g in L.groupby("event")}
    big = ["2016-09", "2020-10-13", "2025-07-18", "2025-09-18", "2026-06-09"]
    print(f"  {col:8s} events {per}\n           mean(big 5) {np.mean([per[e] for e in big]):.3f} | GHMC chronic {roc_auc_score([i in C for i in ids], s):.3f}")
ev = ns = None
