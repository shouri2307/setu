"""
p11_overture_places.py — pull Hyderabad places from the Overture Maps open dataset (free, no key, no card).

Overture's `places` theme merges POIs from Meta, Microsoft, Foursquare and others, which is far denser in India
than OpenStreetMap alone. We download the Hyderabad bounding box once, map Overture categories onto SETU's
categories, and write research/overture_places.json. p12_merge_places.py then merges it with the OSM layer.

Run:  .venv/Scripts/python pipeline/p11_overture_places.py [--release 2026-09-23.1]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research" / "overture_places.json"
W, S, E, N = 78.17, 17.17, 78.72, 17.70   # a little wider than the 145 wards so peripheral addresses are covered

# Overture primary-category -> SETU category (matched by exact name or prefix)
MAP = {
    "hospital": {"hospital", "emergency_room", "medical_center", "childrens_hospital", "maternity_clinic"},
    "clinic": {"clinic", "doctor", "health_clinic", "urgent_care_clinic", "dentist", "family_practice", "doctors_office", "dental_clinic", "medical_center_clinic", "diagnostic_center", "diagnostic_lab"},
    "school": {"school", "elementary_school", "middle_school", "high_school", "preschool", "private_school", "public_school", "primary_school", "secondary_school", "montessori_school", "kindergarten"},
    "college": {"college_university", "university", "college", "engineering_school", "technical_school", "vocational_and_technical_school", "business_school", "medical_school"},
    "fire": {"fire_station"},
    "police": {"police_station", "police_department"},
    "metro": {"subway_station", "train_station", "metro_station", "railway_station", "light_rail_and_subway_stations", "public_transportation", "transit_station"},
    "bus": {"bus_station", "bus_stop"},
    "market": {"supermarket", "grocery_store", "shopping_mall", "department_store", "market", "farmers_market", "convenience_store", "hypermarket", "wholesale_store"},
    "bank": {"bank", "bank_credit_union", "atm", "banks", "bank_or_credit_union", "credit_union"},
    "park": {"park", "playground", "garden", "city_park", "national_park", "botanical_garden", "dog_park"},
    "pharmacy": {"pharmacy", "drugstore"},
}
REV = {c: k for k, v in MAP.items() for c in v}


def latest_release():
    import urllib.request
    import re
    xml = urllib.request.urlopen("https://overturemaps-us-west-2.s3.amazonaws.com/?prefix=release/&delimiter=/", timeout=30).read().decode()
    rel = sorted(re.findall(r"<Prefix>release/([^/<]+)/</Prefix>", xml))
    return rel[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", default=None)
    args = ap.parse_args()
    rel = args.release or latest_release()
    print("Overture release:", rel, flush=True)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    con.execute("SET s3_region='us-west-2';")
    path = f"s3://overturemaps-us-west-2/release/{rel}/theme=places/type=place/*"
    t0 = time.time()
    q = f"""
      SELECT names.primary AS name, taxonomy.primary AS cat, basic_category AS cat2, operating_status AS st, confidence,
             ST_Y(geometry) AS lat, ST_X(geometry) AS lon
      FROM read_parquet('{path}', filename=false, hive_partitioning=1)
      WHERE bbox.xmin BETWEEN {W} AND {E} AND bbox.ymin BETWEEN {S} AND {N}
        AND (taxonomy.primary IS NOT NULL OR basic_category IS NOT NULL)
    """
    rows = con.execute(q).fetchall()
    print(f"downloaded {len(rows):,} places in {time.time() - t0:.0f}s", flush=True)
    out, cats_seen, unmapped = {k: [] for k in MAP}, {}, {}
    for name, cat, cat2, st, conf, lat, lon in rows:
        if st and st != 'open':
            continue
        cats_seen[cat] = cats_seen.get(cat, 0) + 1
        k = REV.get(cat) or REV.get(cat2)
        if not k:
            unmapped[cat] = unmapped.get(cat, 0) + 1
            continue
        if conf is not None and conf < 0.35:
            continue
        out[k].append([round(lat, 5), round(lon, 5), (name or "")[:60], round(conf or 0, 2)])
    OUT.write_text(json.dumps({"release": rel, "bbox": [W, S, E, N], "poi": out, "source": "Overture Maps Foundation (CDLA Permissive 2.0)"}, separators=(",", ":")), encoding="utf-8")
    print("\nmapped counts:", {k: len(v) for k, v in out.items()})
    top = sorted(unmapped.items(), key=lambda x: -x[1])[:40]
    print("top unmapped categories (check for anything we should map):", top)
    print("wrote", OUT, f"({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    sys.exit(main())
