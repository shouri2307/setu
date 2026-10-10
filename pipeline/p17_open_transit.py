"""
p17_open_transit.py — official public-domain transit and police data for Hyderabad (via OpenCity / Telangana open data):
  * TSRTC bus stops (CSV)           * HMRL Hyderabad Metro stations (GTFS stops.txt)           * Hyderabad police stations (GeoJSON)
Writes research/open_transit.json; p12_merge_places.py folds it into web/data/geo.json.
Run:  .venv/Scripts/python pipeline/p17_open_transit.py
"""
import csv
import io
import json
import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research" / "open_transit.json"
H = {"User-Agent": "Mozilla/5.0 (SETU hackathon project)"}
BASE = "https://data.opencity.in/dataset/"
URLS = {
    "bus_csv": BASE + "88e2d145-7ec6-4666-88dd-6cf18b18312e/resource/1f531384-0f96-4d5f-b2ec-f5a2c772d758/download/hyd_stops.csv",
    "hmrl_zip": BASE + "4e72c202-4cdb-4437-a629-ffcbe9519f73/resource/5fa250e1-3104-4ca7-ad31-4fa3321f6255/download/telangana_opendata_gtfs_hmrl_03_july_2026.zip",
    "police": BASE + "fc638a1b-342b-46e1-bb2f-15a1c425b86c/resource/0b46c486-3a6f-47e8-aaf3-2f3b878ed104/download/hyd_police_stations.geojson",
}
BOX = (78.10, 17.10, 78.80, 17.80)


def inbox(lat, lon):
    return BOX[1] <= lat <= BOX[3] and BOX[0] <= lon <= BOX[2]


def get(url):
    r = requests.get(url, headers=H, timeout=120)
    r.raise_for_status()
    return r.content


def main():
    out = {"source": "TSRTC / HMRL / Hyderabad Police via data.opencity.in (Government of Telangana open data, public domain)"}

    raw = get(URLS["bus_csv"]).decode("utf-8-sig", errors="replace")
    rd = list(csv.DictReader(io.StringIO(raw)))
    print("bus csv columns:", list(rd[0].keys()), "rows", len(rd))
    la_k = next(k for k in rd[0] if k.lower() in ("lat", "latitude", "stop_lat", "y"))
    lo_k = next(k for k in rd[0] if k.lower() in ("lon", "lng", "longitude", "stop_lon", "x"))
    nm_k = next((k for k in rd[0] if "name" in k.lower()), None)
    bus = []
    for r in rd:
        try:
            la, lo = float(r[la_k]), float(r[lo_k])
        except Exception:
            continue
        if inbox(la, lo):
            bus.append([round(la, 5), round(lo, 5), (r.get(nm_k) or "")[:60] if nm_k else ""])
    out["bus"] = bus
    print("bus stops in box:", len(bus))

    z = zipfile.ZipFile(io.BytesIO(get(URLS["hmrl_zip"])))
    print("hmrl files:", z.namelist())
    stops = list(csv.DictReader(io.StringIO(z.read("stops.txt").decode("utf-8-sig"))))
    print("stops.txt columns:", list(stops[0].keys()), "rows", len(stops))
    metro = []
    for r in stops:
        if r.get("location_type") not in (None, "", "0", "1"):
            continue
        try:
            la, lo = float(r["stop_lat"]), float(r["stop_lon"])
        except Exception:
            continue
        if inbox(la, lo):
            metro.append([round(la, 5), round(lo, 5), (r.get("stop_name") or "")[:60]])
    out["metro"] = metro
    print("metro stops:", len(metro), [m[2] for m in metro[:6]])

    gj = json.loads(get(URLS["police"]).decode("utf-8"))
    police = []
    for f in gj.get("features", []):
        g, p = f.get("geometry") or {}, f.get("properties") or {}
        if g.get("type") == "Point":
            lo, la = g["coordinates"][:2]
            if inbox(la, lo):
                nm = next((str(v) for k, v in p.items() if "name" in k.lower() and v), "")
                police.append([round(la, 5), round(lo, 5), nm[:60]])
    out["police"] = police
    print("police stations:", len(police), [x[2] for x in police[:5]])
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    sys.exit(main())
