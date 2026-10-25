"""How much of the Hyderabad study box does the state cadastral layer cover with REAL survey parcels, and where does it stop?
Bhunaksha_Cadastral layer 0 ("Cadastral 2.5m") holds three kinds of polygon: survey parcels (Parcel_num filled, e.g. '91/1'), village-sized placeholders (Parcel_num blank, remarks such as
'Missing Village') and one 'GHMC ... to be checked' polygon over the old city. `SNo` is a village serial number, NOT a survey number. Only the first kind is a parcel, so that is what is counted.
Counts per 0.03-degree cell via envelope count queries (no attributes are read). A failed request is stored as null and is never read as zero.
Output: research/v7/parcel_coverage.json.   .venv/Scripts/python research/v7/parcel_coverage.py"""
import requests, json, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
H = {"User-Agent": "SETU-sideproject/0.1"}; BASE = "https://tgrac.telangana.gov.in/arcgis/rest/services"
BBOX = [78.24184, 17.26164, 78.65123, 17.59083]; STEP = 0.03
REAL = "Parcel_num IS NOT NULL AND Parcel_num <> ' ' AND Parcel_num <> ''"
LAYERS = {"cad_parcels": ("Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/0", REAL), "cad_any": ("Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/0", "1=1"),
          "ulb_prohibited": ("Bhunaksha_Folder/Bhunaksha/MapServer/0", "CATEGORY_OF_PROHIBITORY_LAND IS NOT NULL AND CATEGORY_OF_PROHIBITORY_LAND <> ' '")}
def count(k, env):
    path, where = LAYERS[k]
    for _ in range(3):
        try:
            r = requests.get(f"{BASE}/{path}/query", params={"f": "json", "where": where, "geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "returnCountOnly": "true"}, headers=H, timeout=90).json()
            if "count" in r: return r["count"]
        except Exception: time.sleep(2)
    return None
cells = []
x = BBOX[0]
while x < BBOX[2]:
    y = BBOX[1]
    while y < BBOX[3]: cells.append((round(x, 5), round(y, 5))); y += STEP
    x += STEP
jobs = [(k, c) for k in LAYERS for c in cells]
def run(j):
    k, (x0, y0) = j
    return k, x0, y0, count(k, f"{x0},{y0},{x0 + STEP},{y0 + STEP}")
t = time.time(); res = []
with ThreadPoolExecutor(8) as ex:
    for i, r in enumerate(ex.map(run, jobs)):
        res.append(r)
        if i % 100 == 0: print(i, "/", len(jobs), f"{time.time() - t:.0f}s", flush=True)
out = {"bbox": BBOX, "step": STEP, "layers": {k: v[0] + " WHERE " + v[1] for k, v in LAYERS.items()}, "cells": [[k, x0, y0, n] for k, x0, y0, n in res]}
(ROOT / "research/v7/parcel_coverage.json").write_text(json.dumps(out), encoding="utf-8")
print("done", f"{time.time() - t:.0f}s")
