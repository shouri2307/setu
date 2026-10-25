"""Quality checks on the downloaded parcel tiles and the prohibitory-category layer (web/data/parcels, web/data/prohib.json).
Reports: remark classes, duplicate (village, number) pairs, parcel size spread, tile-edge duplicates, and cross-source agreement between the prohibitory layer and the cadastral parcels.
.venv/Scripts/python research/v7/validate_parcels.py"""
import json, collections, re
from pathlib import Path
import numpy as np, pyproj
from shapely.geometry import Polygon, Point
from shapely.ops import transform
ROOT = Path(__file__).resolve().parent.parent.parent; D = ROOT / "web" / "data"
tr = pyproj.Transformer.from_crs(4326, 32644, always_xy=True).transform
idx = json.load(open(D / "parcels" / "index.json"))
rows = []   # (tile, number, village, mandal, code, remark, polygon(lon,lat))
for t in idx["tiles"]:
    tj = json.load(open(D / "parcels" / f"{t}.json"))
    for num, vi, mi, code, rem, rg in tj["p"]:
        rows.append((t, num, tj["v"][vi], tj["m"][mi], code, rem, rg))
print("stored parcel records (a parcel crossing a tile edge is stored once per tile):", len(rows))
uniq = {}
for t, num, v, m, code, rem, rg in rows: uniq.setdefault((v, num, round(rg[0][0][0], 5), round(rg[0][0][1], 5)), (t, num, v, m, code, rem, rg))
print("unique parcels (by village, number, first vertex):", len(uniq))
U = list(uniq.values())
print("remark classes:", collections.Counter(r[4] for r in U))
print("top remarks:", collections.Counter(r[5] for r in U if r[5]).most_common(12))
# duplicate (village, number) among normal parcels
vn = collections.Counter((r[2], r[1]) for r in U if r[4] == 0)
dups = {k: c for k, c in vn.items() if c > 1}
print(f"(village, number) pairs used by more than one normal polygon: {len(dups)} of {len(vn)} ({100 * len(dups) / len(vn):.1f}%) -> matching by number alone can be ambiguous; the engine requires the pin to fall inside")
# format of numbers
fmt = collections.Counter("digits" if re.fullmatch(r"\d+", r[1]) else "n/m" if re.fullmatch(r"\d+\s*/\s*\d+", r[1]) else "alnum" if re.fullmatch(r"[0-9A-Za-z/\-\. ]+", r[1]) else "other" for r in U)
print("number formats:", fmt)
# size spread (m2)
areas = []
for r in U:
    p = Polygon([(x[1], x[0]) for x in r[6][0]]).buffer(0)
    areas.append(transform(tr, p).area)
a = np.array(areas); print("area m2 percentiles 1/10/50/90/99/max:", [round(float(np.percentile(a, q))) for q in (1, 10, 50, 90, 99)], round(float(a.max())))
print("parcels > 1 km2:", int((a > 1e6).sum()), "| < 5 m2:", int((a < 5).sum()))
# villages
vc = collections.Counter(r[2] for r in U); print("villages:", len(vc), "| top:", vc.most_common(6))
# prohibitory layer agreement
pj = json.load(open(D / "prohib.json"))["p"]
print("prohibitory-category parcels:", len(pj), "| categories:", collections.Counter(p[0] for p in pj).most_common(14))
key = collections.defaultdict(list)
for r in U: key[(re.sub(r"[^a-z]", "", r[2].lower()), re.sub(r"\s", "", r[1]))].append(r)
hit = 0; pin = 0; ex = []
for p in pj:
    cat, sy, part, ext, v, m, rg = p
    poly = Polygon([(x[1], x[0]) for x in rg[0]]).buffer(0); c = poly.representative_point()
    k = (re.sub(r"[^a-z]", "", v.lower()), re.sub(r"\s", "", sy))
    if k in key: hit += 1
    if any(Polygon([(x[1], x[0]) for x in r[6][0]]).buffer(0).contains(c) for r in U[:0]): pin += 1
print(f"prohibitory parcels whose (village, survey no) also exists in the cadastral parcels: {hit} of {len(pj)} ({100 * hit / len(pj):.0f}%)")
