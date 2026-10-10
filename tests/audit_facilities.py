"""
Facility audit — how well does the OpenStreetMap backup agree with Google Places?

Run AFTER the Google keys are in .env:
    .venv/Scripts/python tests/audit_facilities.py [--n 40]

For N ward centroids (fixed seed, spread across the city) it asks Google for the nearest facility of each
category and compares with the nearest in web/data/geo.json (OpenStreetMap). Reported per category:
  * agree      — OSM nearest is within 500 m of Google's nearest, or within 35% of its distance
  * osm_missing— Google found something within 3 km but OSM found nothing within 3 km
  * median_ratio — median of (OSM distance / Google distance); >1 means OSM thinks it's farther away
This is the ground-truth check behind the "85% of facility facts match" target. ~8 Google calls per point.
"""
import argparse
import json
import math
import os
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
import _google  # noqa: E402


def hav(a, b, c, d):
    R = 6371000
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = p2 - p1, math.radians(d - b)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def nearest(rows, lat, lon):
    return min((hav(lat, lon, r[0], r[1]) for r in rows), default=None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    args = ap.parse_args()
    if not _google.server_key():
        print("No GOOGLE_PLACES_SERVER_KEY in .env — nothing to audit against.")
        return 2
    zones = json.loads((ROOT / "web/data/zones.json").read_text(encoding="utf-8"))
    geo = json.loads((ROOT / "web/data/geo.json").read_text(encoding="utf-8"))
    pts = []
    for w in zones["wards"]:
        xs = [p[0] for r in w["rings"] for p in r]
        ys = [p[1] for r in w["rings"] for p in r]
        pts.append((sum(ys) / len(ys), sum(xs) / len(xs), w["name"]))
    random.Random(7).shuffle(pts)
    pts = pts[: args.n]

    stats = {c: {"agree": 0, "n": 0, "osm_missing": 0, "ratios": []} for c in _google.CATS}
    calls = 0
    for lat, lon, name in pts:
        res = _google.nearby_all(lat, lon)
        calls += len(_google.CATS)
        if res.get("error") and not res.get("cats"):
            print("Google error:", res["error"])
            return 1
        for cat, rows in res.get("cats", {}).items():
            if not rows:
                continue
            g = nearest(rows, lat, lon)
            o = nearest(geo["poi"].get(cat, []), lat, lon)
            s = stats[cat]
            s["n"] += 1
            if o is None or o > 3000:
                if g <= 3000:
                    s["osm_missing"] += 1
                continue
            if abs(o - g) <= 500 or abs(o - g) <= 0.35 * max(g, 1):
                s["agree"] += 1
            s["ratios"].append(o / max(g, 1))
    print(f"\nFacility audit — {len(pts)} points, ~{calls} Google calls\n")
    print(f"{'category':10} {'n':>3} {'agree':>7} {'OSM missing':>12} {'median OSM/Google dist':>24}")
    tot_a = tot_n = 0
    for c, s in stats.items():
        if not s["n"]:
            continue
        tot_a += s["agree"]
        tot_n += s["n"]
        med = statistics.median(s["ratios"]) if s["ratios"] else float("nan")
        print(f"{c:10} {s['n']:>3} {s['agree'] / s['n']:>6.0%} {s['osm_missing']:>12} {med:>24.2f}")
    print(f"\nOVERALL agreement: {tot_a}/{tot_n} = {tot_a / max(tot_n, 1):.0%}  (target for OSM backup is informational; Google is the primary source)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
