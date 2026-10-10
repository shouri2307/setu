"""
p15c_hmda_geocode.py — place HMDA's Hyderabad-district lakes on the map by geocoding their names (Photon / OSM).

A result is accepted only if (a) it lies inside the Hyderabad study box, and (b) its name shares the lake's distinctive
word(s) (e.g. "Salkam", "Mir Alam"). Everything else stays unplaced rather than guessed.
Run:  .venv/Scripts/python pipeline/p15c_hmda_geocode.py
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "web" / "data" / "hmda_lakes.json"
H = {"User-Agent": "Mozilla/5.0 (SETU hackathon project)"}
BOX = (78.20, 17.20, 78.65, 17.60)   # lon_min, lat_min, lon_max, lat_max
STOP = {"cheruvu", "kunta", "kuntaa", "lake", "tank", "talab", "pond", "cheru", "the", "of", "ghat", "house"}


def words(s):
    return [w for w in re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split() if len(w) > 2 and w not in STOP]


def photon(q):
    r = requests.get("https://photon.komoot.io/api/", params={"q": q, "lat": 17.40, "lon": 78.45, "limit": 6, "lang": "en"}, headers=H, timeout=30)
    return r.json().get("features", [])


def main():
    doc = json.loads(FILE.read_text(encoding="utf-8"))
    n_ok = n_try = 0
    for lk in doc["lakes"]:
        if lk["district"] != "Hyderabad":
            continue
        n_try += 1
        key = words(lk["name"]) or words(lk["village"])
        found = None
        for q in (f"{lk['name']} Hyderabad", f"{lk['name']} {lk['village']} Hyderabad", f"{lk['village']} {lk['mandal']} Hyderabad lake"):
            try:
                for f in photon(q):
                    lon, lat = f["geometry"]["coordinates"]
                    nm = (f["properties"].get("name") or "")
                    if not (BOX[0] <= lon <= BOX[2] and BOX[1] <= lat <= BOX[3]):
                        continue
                    if key and any(w in nm.lower() for w in key):
                        found = (lat, lon, nm)
                        break
            except Exception as e:
                print("  err", e)
            time.sleep(1.1)
            if found:
                break
        if found:
            lk["lat"], lk["lon"], lk["geo_name"] = round(found[0], 5), round(found[1], 5), found[2]
            n_ok += 1
            print(f"  placed  {lk['name']:30} -> {found[2]} ({found[0]:.4f},{found[1]:.4f})")
        else:
            print(f"  UNPLACED {lk['name']} ({lk['village']}, {lk['mandal']})")
    FILE.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"placed {n_ok} of {n_try}")


if __name__ == "__main__":
    sys.exit(main())
