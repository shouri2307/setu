"""Summarise research/v7/parcel_coverage.json by planning-authority area (cell centre, same precedence the engine uses) and inside the 145 GHMC wards.
A null (failed request) is reported as unknown, never as zero."""
import json, collections
from pathlib import Path
from shapely.geometry import Polygon, Point
R = Path(__file__).resolve().parent; WEB = R.parent.parent / "web" / "data"
cov = json.load(open(R / "parcel_coverage.json")); st = cov["step"]; plan = json.load(open(WEB / "plan.json"))
ORDER = ["MCH", "CDA", "HADA", "HUDA", "HMR_ORR_GROWTH", "HMR"]
ZP = {z["z"]: [(Polygon([(x[1], x[0]) for x in p["o"]]).buffer(0), [Polygon([(x[1], x[0]) for x in h]).buffer(0) for h in p["h"]]) for p in z["polys"]] for z in plan["zones"]}
def zone(lon, lat):
    pt = Point(lon, lat)
    for zn in ORDER:
        for o, hs in ZP[zn]:
            if o.contains(pt) and not any(h.contains(pt) for h in hs): return zn
    return "none"
wards = [Polygon([(x[0], x[1]) for x in w["rings"][0]]).buffer(0) for w in json.load(open(WEB / "zones.json"))["wards"]]
inward = lambda pt: any(w.contains(pt) for w in wards)
cells = collections.defaultdict(dict)
for k, x, y, n in cov["cells"]: cells[(x, y)][k] = n
layers = list(cov["layers"]); grp = collections.defaultdict(list)
for (x, y) in cells:
    pt = Point(x + st / 2, y + st / 2); grp["zone " + zone(pt.x, pt.y)].append((x, y)); grp["inside 145 wards" if inward(pt) else "outside 145 wards"].append((x, y))
print("cells", len(cells), "| failed requests:", sum(1 for c in cells.values() for v in c.values() if v is None))
for g in sorted(grp):
    cs = grp[g]
    print(f"{g:24s} cells={len(cs):3d} | cells with >=1 feature: " + "  ".join(f"{k}={sum(1 for c in cs if (cells[c].get(k) or 0) > 0)}" for k in layers) + " | features (overlap-inflated): " + "  ".join(f"{k}={sum((cells[c].get(k) or 0) for c in cs)}" for k in layers))
