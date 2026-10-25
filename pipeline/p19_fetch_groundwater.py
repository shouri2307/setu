"""p19_fetch_groundwater.py — download Telangana Ground Water Department monthly water-level files and the pre/post-monsoon
water-quality files from Open Data Telangana (DKAN API) into research/external/groundwater/. Cached; re-run is cheap.
Run:  .venv/Scripts/python pipeline/p19_fetch_groundwater.py"""
import re, sys, time, requests
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research" / "external" / "groundwater"; OUT.mkdir(parents=True, exist_ok=True)
H = {"User-Agent": "SETU-sideproject/0.1"}

def get(u, **kw):
    err = None
    for a in range(4):
        try:
            r = requests.get(u, headers=H, timeout=120, **kw)
            if r.status_code == 200: return r
            err = r.status_code
        except Exception as e: err = e
        time.sleep(3 + 4 * a)
    print("   FAILED", u[:90], str(err)[:60]); return None

def datasets():
    r = get("https://data.telangana.gov.in/api/1/search", params={"fulltext": "Ground Water Department", "page-size": 20})
    res = r.json().get("results", {}); return list(res.values()) if isinstance(res, dict) else res

for ds in datasets():
    t = ds.get("title", "")
    if "Ground Water" not in t: continue
    kind = "level" if "Level" in t else "quality_pre" if "Pre monsoon" in t else "quality_post" if "Post monsoon" in t else "other"
    print(t, "|", len(ds.get("distribution", [])), "files ->", kind)
    for d in ds.get("distribution", []):
        url = d.get("downloadURL"); 
        if not url: continue
        name = kind + "__" + re.sub(r"[^A-Za-z0-9_.-]+", "_", (d.get("title") or url.split("/")[-1])) + ".csv"
        f = OUT / name
        if f.exists() and f.stat().st_size > 200: continue
        r = get(url)
        if r is not None: f.write_bytes(r.content); print("   ", name, len(r.content))
