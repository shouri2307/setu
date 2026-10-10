"""Explore the TGRAC ArcGIS directory: list services and layers (with feature counts) for the folders we care about.
Run:  .venv/Scripts/python pipeline/tgrac_explore.py Hydra_Folder HMDA_Folder ...   (read-only, polite)"""
import json
import sys
import time

import requests

B = "https://tgrac.telangana.gov.in/arcgis/rest/services"
H = {"User-Agent": "Mozilla/5.0 (SETU hackathon project)"}


def j(url, **p):
    p["f"] = "json"
    for a in range(3):
        try:
            r = requests.get(url, params=p, headers=H, timeout=40)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(1.5)
    return {}


for folder in sys.argv[1:]:
    d = j(f"{B}/{folder}")
    print(f"\n=== {folder}: {[(s['name'].split('/')[-1], s['type']) for s in d.get('services', [])]}")
    for s in d.get("services", []):
        if s["type"] not in ("MapServer", "FeatureServer"):
            continue
        m = j(f"{B}/{s['name']}/{s['type']}")
        for L in m.get("layers", []):
            c = j(f"{B}/{s['name']}/{s['type']}/{L['id']}/query", where="1=1", returnCountOnly="true").get("count", "?")
            print(f"   {s['name'].split('/')[-1]} / [{L['id']}] {L['name']}  count={c}")
        time.sleep(0.3)
