"""Feasibility probe: Sentinel-1 flood mask for Khammam / Munneru, 1 Sep 2024 (open Planetary Computer archive, anonymous signing).
Change detection on VV backscatter: post-event pass vs the nearest earlier pass on the SAME relative orbit."""
import requests, json, numpy as np, rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
H = {"User-Agent": "SETU-sideproject/0.1"}
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
BB = [80.05, 17.15, 80.30, 17.35]       # Khammam town + Munneru floodplain
def search(a, b):
    r = requests.post(STAC, json={"collections": ["sentinel-1-rtc"], "bbox": BB, "datetime": f"{a}T00:00:00Z/{b}T23:59:59Z", "limit": 50}, headers=H, timeout=90)
    return r.json()["features"]
def sign(href):
    r = requests.get("https://planetarycomputer.microsoft.com/api/sas/v1/sign", params={"href": href}, headers=H, timeout=60); r.raise_for_status()
    return r.json()["href"]
post = [f for f in search("2024-09-01", "2024-09-01")]
print("post-event items:", [(f["id"][:40], f["properties"]["datetime"], f["properties"].get("sat:relative_orbit"), f["properties"].get("sat:orbit_state")) for f in post])
pre_all = search("2024-08-10", "2024-08-31")
print("candidate pre items:", [(f["properties"]["datetime"][:16], f["properties"].get("sat:relative_orbit"), f["properties"].get("sat:orbit_state")) for f in pre_all])

def read(item):
    href = sign(item["assets"]["vv"]["href"])
    with rasterio.open(href) as ds:
        bb = transform_bounds("EPSG:4326", ds.crs, *BB)
        w = from_bounds(*bb, ds.transform); a = ds.read(1, window=w, boundless=False).astype("float32")
        return a, ds.window_transform(w), ds.crs
a1, t1, crs = read(pre_all[0]); a2, t2, _ = read(post[0])
h = min(a1.shape[0], a2.shape[0]); w = min(a1.shape[1], a2.shape[1]); a1, a2 = a1[:h, :w], a2[:h, :w]
print("window shape", a1.shape, "pixel size", t1.a)
db = lambda x: 10 * np.log10(np.clip(x, 1e-6, None))
d1, d2 = db(a1), db(a2)
valid = np.isfinite(d1) & np.isfinite(d2) & (a1 > 0) & (a2 > 0)
water_post = d2 < -17.0                         # open-water-like backscatter after
change = (d2 - d1) < -3.0                       # at least 3 dB drop vs before
perm_water = d1 < -17.0                         # already water before (lakes, river channel)
flood = valid & water_post & change & ~perm_water
pix = abs(t1.a * t1.e)
print(f"valid px {valid.sum():,} | permanent water {((perm_water&valid).sum()*pix/1e6):.1f} km2 | new flood water {(flood.sum()*pix/1e6):.1f} km2 ({100*flood.sum()/valid.sum():.1f}% of window)")
np.save("research/v6/khammam_flood_mask.npy", flood)
import json; json.dump({"crs": str(crs), "transform": list(t1)[:6], "shape": list(flood.shape), "pre": pre_all[0]["id"], "post": post[0]["id"]}, open("research/v6/khammam_flood_meta.json", "w"))
# quick image for eyeballing
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 3, figsize=(15, 5)); lo, hi = -25, 0
ax[0].imshow(d1, cmap="gray", vmin=lo, vmax=hi); ax[0].set_title("VV 20 Aug 2024 (before)")
ax[1].imshow(d2, cmap="gray", vmin=lo, vmax=hi); ax[1].set_title("VV 1 Sep 2024 06:00 IST (flood)")
rgb = np.dstack([np.where(flood, 1, 0.5 * (d2 - lo) / (hi - lo)), 0.5 * (d2 - lo) / (hi - lo), np.where(flood, 1, 0.5 * (d2 - lo) / (hi - lo))])
ax[2].imshow(np.clip(rgb, 0, 1)); ax[2].set_title("new flood water (magenta)")
for x in ax: x.axis("off")
plt.tight_layout(); plt.savefig("research/v6/khammam_flood_probe.png", dpi=70)
