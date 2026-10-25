"""p25_heat.py — urban surface heat and greenness from Landsat 8/9 (Microsoft Planetary Computer, open, anonymous signing).
Takes clear-sky dry-season scenes (Mar-May, 2024-2026, cloud < 15%), converts the thermal band to land-surface temperature (deg C),
computes NDVI, takes the per-pixel MEDIAN across scenes, averages to a 150 m grid, and writes web/data/heat.json.
Surface temperature is not air temperature; it shows which places run hotter than their surroundings in the dry season.
Run: .venv/Scripts/python pipeline/p25_heat.py   (slow: remote reads, run in the background)"""
import json, sys, time, warnings, requests
from pathlib import Path
import numpy as np, rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
H = {"User-Agent": "SETU-sideproject/0.1"}
B = json.loads((ROOT / "web/data/zones.json").read_text())["bounds"]          # [lon0, lat0, lon1, lat1]
BB = [B[0] - .03, B[1] - .03, B[2] + .03, B[3] + .03]
CELL = 0.00135                                                                    # ~150 m
def sign(href):
    for a in range(4):
        try:
            r = requests.get("https://planetarycomputer.microsoft.com/api/sas/v1/sign", params={"href": href}, headers=H, timeout=60); r.raise_for_status(); return r.json()["href"]
        except Exception as e: time.sleep(2 + 3 * a)
    raise RuntimeError("sign failed")
items = []
for yr in (2024, 2025, 2026):
    r = requests.post("https://planetarycomputer.microsoft.com/api/stac/v1/search", json={"collections": ["landsat-c2-l2"], "bbox": BB, "datetime": f"{yr}-03-01T00:00:00Z/{yr}-05-31T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": 15}, "platform": {"in": ["landsat-8", "landsat-9"]}}, "limit": 50}, headers=H, timeout=90)
    items += r.json().get("features", [])
print("candidate scenes:", [(f["properties"]["datetime"][:10], f["properties"]["platform"], round(f["properties"]["eo:cloud_cover"], 1), f["properties"].get("landsat:wrs_path"), f["properties"].get("landsat:wrs_row")) for f in items], flush=True)
def read(item, asset, shape=None):
    href = sign(item["assets"][asset]["href"])
    with rasterio.open(href) as ds:
        bb = transform_bounds("EPSG:4326", ds.crs, *BB); w = from_bounds(*bb, ds.transform)
        a = ds.read(1, window=w, boundless=True, fill_value=0).astype("float32"); return a, ds.window_transform(w), ds.crs
nx, ny = int(round((BB[2] - BB[0]) / CELL)), int(round((BB[3] - BB[1]) / CELL))
sts, nds = [], []
for it in items:
    try:
        st, t, crs = read(it, "lwir11"); red, _, _ = read(it, "red"); nir, _, _ = read(it, "nir08"); qa, _, _ = read(it, "qa_pixel")
    except Exception as e:
        print("skip", it["id"], str(e)[:80], flush=True); continue
    h = min(st.shape[0], red.shape[0], nir.shape[0], qa.shape[0]); w = min(st.shape[1], red.shape[1], nir.shape[1], qa.shape[1])
    st, red, nir, qa = st[:h, :w], red[:h, :w], nir[:h, :w], qa[:h, :w].astype(int)
    lst = st * 0.00341802 + 149.0 - 273.15
    refl = lambda x: x * 0.0000275 - 0.2
    ndvi = (refl(nir) - refl(red)) / np.maximum(refl(nir) + refl(red), 1e-6)
    cloudy = ((qa >> 1) & 1) | ((qa >> 3) & 1) | ((qa >> 4) & 1) | ((qa >> 2) & 1)   # dilated cloud, cloud, shadow, cirrus
    bad = (cloudy == 1) | (st == 0) | (lst < 10) | (lst > 70)
    lst[bad] = np.nan; ndvi[bad] = np.nan
    # resample onto the common grid by block mean in lon/lat via the scene transform (UTM -> lon/lat approximated per pixel centre)
    from pyproj import Transformer
    tr = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    ys, xs = np.mgrid[0:h:5, 0:w:5]                                   # 150 m sampling stride on a 30 m grid
    X, Y = rasterio.transform.xy(t, ys.ravel(), xs.ravel(), offset="center"); lon, lat = tr.transform(np.array(X), np.array(Y))
    gi = ((lon - BB[0]) / CELL).astype(int); gj = ((BB[3] - lat) / CELL).astype(int)
    ok = (gi >= 0) & (gi < nx) & (gj >= 0) & (gj < ny)
    a = np.full((ny, nx), np.nan, dtype="float32"); b = np.full((ny, nx), np.nan, dtype="float32")
    # block mean over the 5x5 neighbourhood sampled at each stride point
    from scipy.ndimage import uniform_filter
    ls = np.where(np.isnan(lst), 0, lst); cnt = (~np.isnan(lst)).astype("float32")
    num = uniform_filter(ls, 5, mode="nearest"); den = uniform_filter(cnt, 5, mode="nearest"); lm = np.where(den > .5, num / np.maximum(den, 1e-6), np.nan)
    nv = np.where(np.isnan(ndvi), 0, ndvi); numn = uniform_filter(nv, 5, mode="nearest"); nm = np.where(den > .5, numn / np.maximum(den, 1e-6), np.nan)
    a[gj[ok], gi[ok]] = lm[ys.ravel()[ok], xs.ravel()[ok]]; b[gj[ok], gi[ok]] = nm[ys.ravel()[ok], xs.ravel()[ok]]
    sts.append(a); nds.append(b); print("used", it["properties"]["datetime"][:10], "valid cells", int(np.isfinite(a).sum()), "median LST %.1f C" % np.nanmedian(a), flush=True)
if not sts: sys.exit("no usable scenes")
L = np.nanmedian(np.stack(sts), axis=0); N = np.nanmedian(np.stack(nds), axis=0); nsc = np.sum(np.isfinite(np.stack(sts)), axis=0)
L[nsc < 2] = np.nan; N[nsc < 2] = np.nan                                         # need at least 2 clear looks
enc = lambda A, s, o: [None if not np.isfinite(v) else int(round((v - o) * s)) for v in A.ravel()]
out = {"meta": {"source": "Landsat 8/9 Collection 2 Level-2 (USGS) via Microsoft Planetary Computer", "scenes": len(sts), "dates": sorted({it["properties"]["datetime"][:10] for it in items}), "window": "Mar-May 2024-2026 (dry season), median of clear looks",
                "bbox": BB, "cell_deg": CELL, "nx": nx, "ny": ny, "lst_encoding": "deg C x 10", "ndvi_encoding": "NDVI x 100", "note": "surface temperature, not air temperature"},
       "lst": enc(L, 10, 0), "ndvi": enc(N, 100, 0)}
(ROOT / "web/data/heat.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
print("written heat.json | LST median %.1f C, p10 %.1f, p90 %.1f | NDVI median %.2f | valid cells %d of %d" % (np.nanmedian(L), np.nanpercentile(L, 10), np.nanpercentile(L, 90), np.nanmedian(N), np.isfinite(L).sum(), L.size))
