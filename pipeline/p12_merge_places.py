"""
p12_merge_places.py — merge OpenStreetMap + Overture places into web/data/geo.json (the `poi` layer).

OSM stays the source of truth for water, underpasses, industry etc. For facility categories we take the union
of OSM and Overture and drop near-duplicates (same category within DEDUPE_M metres, OSM kept first because its
names are community-verified). Overture rows below MIN_CONF are ignored.

Run after p8_geo.py and p11_overture_places.py:
    .venv/Scripts/python pipeline/p12_merge_places.py
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEO = ROOT / "web" / "data" / "geo.json"
OSM_BACKUP = ROOT / "research" / "geo_osm_only.json"
OVT = ROOT / "research" / "overture_places.json"
DEDUPE_M = 40
MIN_CONF = {"hospital": .5, "clinic": .5, "school": .5, "college": .45, "fire": .4, "police": .5, "metro": .5, "bus": .5, "market": .45, "bank": .6, "park": .45, "pharmacy": .5}
MERGE = ["hospital", "clinic", "school", "college", "fire", "police", "metro", "bus", "market", "bank", "park"]
EXTRA = ["pharmacy"]  # categories only Overture provides
HUBS = root_hubs = ROOT / "research" / "overture_roads_hubs.json"
TRANSIT = ROOT / "research" / "open_transit.json"
TGHEALTH = ROOT / "research" / "tgrac_health.json"


def cell(lat, lon):
    return (int(lat / 0.0004), int(lon / 0.0004))   # ~44 m grid


def main():
    if not OVT.exists():
        print("Run p11_overture_places.py first")
        return 2
    if not OSM_BACKUP.exists():       # keep a pristine OSM-only copy so this script is re-runnable
        OSM_BACKUP.write_text(GEO.read_text(encoding="utf-8"), encoding="utf-8")
    geo = json.loads(OSM_BACKUP.read_text(encoding="utf-8"))
    ovt = json.loads(OVT.read_text(encoding="utf-8"))
    out = {}
    for cat in MERGE + EXTRA:
        kept, grid = [], {}

        def add(row, src):
            lat, lon = row[0], row[1]
            ci, cj = cell(lat, lon)
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for (la, lo) in grid.get((ci + di, cj + dj), ()):
                        dy = (lat - la) * 110540
                        dx = (lon - lo) * 111320 * math.cos(math.radians(lat))
                        if dx * dx + dy * dy < DEDUPE_M ** 2:
                            return False
            grid.setdefault((ci, cj), []).append((lat, lon))
            kept.append([row[0], row[1], row[2]])
            return True

        n_osm = n_ovt = 0
        for r in geo["poi"].get(cat, []):
            n_osm += add(r, "osm")
        for r in ovt["poi"].get(cat, []):
            if r[3] >= MIN_CONF.get(cat, .5):
                n_ovt += add(r, "overture")
        out[cat] = kept
        print(f"{cat:9} osm {len(geo['poi'].get(cat, [])):5} + overture {len(ovt['poi'].get(cat, [])):5} -> merged {len(kept):5}  (osm kept {n_osm}, overture added {n_ovt})")
    if HUBS.exists():   # trade routes (road sample points) and demand drivers (IT offices, malls, cinemas)
        h = json.loads(HUBS.read_text(encoding="utf-8"))
        geo["roads"] = h["roads"]
        geo["road_names"] = h.get("road_names", {})
        for cat, rows_ in h["hubs"].items():
            kept, grid = [], {}
            for r in rows_:
                ci, cj = cell(r[0], r[1])
                dup = False
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        for (la, lo) in grid.get((ci + di, cj + dj), ()):
                            dy = (r[0] - la) * 110540
                            dx = (r[1] - lo) * 111320 * math.cos(math.radians(r[0]))
                            if dx * dx + dy * dy < DEDUPE_M ** 2:
                                dup = True
                if not dup:
                    grid.setdefault((ci, cj), []).append((r[0], r[1]))
                    kept.append([r[0], r[1], r[2]])
            out[cat] = kept
            print(f"{cat:9} overture hubs {len(rows_):5} -> {len(kept):5}")
        print("road points:", {k: len(v) for k, v in geo["roads"].items()})
    def fold(cat, rows_, dedupe_m):
        """add official points to out[cat], skipping anything within dedupe_m of a point already there"""
        cur = out.setdefault(cat, [])
        grid = {}
        for r in cur:
            grid.setdefault(cell(r[0], r[1]), []).append((r[0], r[1]))
        added = 0
        for r in rows_:
            ci, cj = cell(r[0], r[1])
            dup = False
            for di in (-2, -1, 0, 1, 2):
                for dj in (-2, -1, 0, 1, 2):
                    for (la, lo) in grid.get((ci + di, cj + dj), ()):
                        dy = (r[0] - la) * 110540
                        dx = (r[1] - lo) * 111320 * math.cos(math.radians(r[0]))
                        if dx * dx + dy * dy < dedupe_m ** 2:
                            dup = True
            if not dup:
                grid.setdefault((ci, cj), []).append((r[0], r[1]))
                cur.append([r[0], r[1], r[2]])
                added += 1
        print(f"{cat:9} official points {len(rows_):5} -> added {added:5} (total {len(cur)})")

    if TRANSIT.exists():
        t = json.loads(TRANSIT.read_text(encoding="utf-8"))
        fold("bus", t.get("bus", []), 25)
        fold("metro", t.get("metro", []), 150)
        fold("police", t.get("police", []), 80)
    if TGHEALTH.exists():
        h2 = json.loads(TGHEALTH.read_text(encoding="utf-8"))
        fold("ambulance", h2.get("ambulance", []), 30)
        fold("hospital", h2.get("govhospital", []), 60)
        fold("clinic", h2.get("govclinic", []), 40)
    for cat in geo["poi"]:
        if cat not in out:
            out[cat] = geo["poi"][cat]
    geo["poi"] = out
    geo["places_sources"] = f"OpenStreetMap contributors (ODbL) + Overture Maps Foundation {ovt['release']} (CDLA Permissive 2.0) + TSRTC / HMRL / Hyderabad Police / Telangana health GIS (public domain)"
    GEO.write_text(json.dumps(geo, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {GEO} ({GEO.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    sys.exit(main())
