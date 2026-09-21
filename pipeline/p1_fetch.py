"""
p1_fetch.py — Download raw data for SETU into data/raw/.

Pulls:
  1. DEM (elevation) for the Hyderabad bbox from OpenTopography.
  2. Roads, hospitals, and water bodies from OpenStreetMap via Overpass.

Run once. Re-runs skip any file that already exists (delete a file to refetch).
Requires OPENTOPOGRAPHY_API_KEY in .env.
"""

import os
import sys
import json
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# Allow running as `python pipeline/p1_fetch.py` from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

load_dotenv()
OPENTOPO_KEY = os.getenv("OPENTOPOGRAPHY_API_KEY")

# Overpass public mirrors — tried in order. If one returns 406/429/5xx, fall to next.
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# A real User-Agent is required — the default requests UA gets 406'd by Overpass.
HEADERS = {"User-Agent": "SETU-hackathon/1.0 (flood modelling; contact: student@spec.ac.in)"}


def fetch_dem():
    """Download the DEM GeoTIFF from OpenTopography for config.BBOX."""
    if config.DEM_FILE.exists():
        print(f"[skip] DEM already exists: {config.DEM_FILE.name}")
        return

    if not OPENTOPO_KEY or OPENTOPO_KEY == "your_key_here":
        print("[error] OPENTOPOGRAPHY_API_KEY not set in .env — cannot fetch DEM.")
        return

    params = {
        "demtype": config.DEM_TYPE,
        "south": config.BBOX["south"],
        "north": config.BBOX["north"],
        "west": config.BBOX["west"],
        "east": config.BBOX["east"],
        "outputFormat": "GTiff",
        "API_Key": OPENTOPO_KEY,
    }

    print(f"[dem] requesting {config.DEM_TYPE} for Hyderabad bbox ...")
    r = requests.get(config.OPENTOPO_URL, params=params, headers=HEADERS, timeout=120)

    if r.status_code != 200:
        print(f"[error] OpenTopography returned {r.status_code}: {r.text[:300]}")
        return

    config.DEM_FILE.write_bytes(r.content)
    size_mb = config.DEM_FILE.stat().st_size / 1_000_000
    print(f"[dem] saved {config.DEM_FILE.name} ({size_mb:.1f} MB)")


def _overpass_query(query, out_file, label):
    """Run one Overpass query across mirrors and save the raw JSON."""
    if out_file.exists():
        print(f"[skip] {label} already exists: {out_file.name}")
        return

    print(f"[osm] fetching {label} ...")

    for i, url in enumerate(OVERPASS_MIRRORS):
        try:
            r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=180)
        except requests.RequestException as ex:
            print(f"       mirror {i+1} failed ({type(ex).__name__}); trying next ...")
            continue

        if r.status_code == 200:
            try:
                data = r.json()
            except json.JSONDecodeError:
                print(f"       mirror {i+1} returned non-JSON; trying next ...")
                continue
            n = len(data.get("elements", []))
            out_file.write_text(json.dumps(data), encoding="utf-8")
            print(f"[osm] saved {out_file.name} ({n} elements)")
            time.sleep(2)  # be polite between calls
            return

        # 429 = rate limited, 504/5xx = server busy, 406 = header issue on that mirror
        print(f"       mirror {i+1} returned {r.status_code}; trying next ...")
        time.sleep(3)

    print(f"[error] all Overpass mirrors failed for {label}. "
          f"Wait a minute and re-run — the public servers rate-limit.")


def fetch_osm():
    """Fetch roads, hospitals, and water via Overpass for config.BBOX."""
    s, n = config.BBOX["south"], config.BBOX["north"]
    w, e = config.BBOX["west"], config.BBOX["east"]
    bbox = f"{s},{w},{n},{e}"

    roads_q = f"""
    [out:json][timeout:180];
    (
      way["highway"~"^(primary|secondary|trunk|motorway)$"]({bbox});
    );
    out geom;
    """

    hospitals_q = f"""
    [out:json][timeout:180];
    (
      node["amenity"="hospital"]({bbox});
      way["amenity"="hospital"]({bbox});
    );
    out center;
    """

    water_q = f"""
    [out:json][timeout:180];
    (
      way["natural"="water"]({bbox});
      relation["natural"="water"]({bbox});
    );
    out geom;
    """

    _overpass_query(roads_q, config.OSM_ROADS, "roads")
    _overpass_query(hospitals_q, config.OSM_HOSPITALS, "hospitals")
    _overpass_query(water_q, config.OSM_WATER, "water")


def main():
    print("=== SETU p1_fetch ===")
    print(f"bbox: {config.BBOX}")
    print(f"raw dir: {config.RAW}\n")
    fetch_dem()
    print()
    fetch_osm()
    print("\n[done] p1_fetch complete. Check data/raw/")


if __name__ == "__main__":
    main()