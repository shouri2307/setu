"""Diagnostic for step2_validate: for the lakes where no same-numbered parcel was found in the same village, is there one under a different village spelling, or touching the outline?"""
import json, re, sys
sys.path.insert(0, "research/v8")
sys.stdout.reconfigure(encoding="utf-8")
import importlib.util, io, contextlib
src = open("research/v8/step2_validate.py", encoding="utf-8").read().split("rows = []")[0]
ns = {"__file__": str(__import__("pathlib").Path("research/v8/step2_validate.py").resolve())}; exec(compile(src, "s2", "exec"), ns)
q, polys, same_no, pick, clean, M = ns["q"], ns["polys"], ns["same_no"], ns["pick"], ns["clean"], ns["M_PER_DEG"]
MAIN = ns["MAIN"]
for n, (area, nm, sy, vil, man, st, g) in enumerate(pick, 1):
    x0, y0, x1, y1 = g.bounds; pad = 150 / M
    r = q(MAIN, (x0 - pad, y0 - pad, x1 + pad, y1 + pad), "Parcel_num,V_Name")
    hits = [(clean(f["attributes"]["V_Name"]), clean(f["attributes"]["Parcel_num"]), polys(f)) for f in r["features"] if same_no(f["attributes"].get("Parcel_num"), sy)]
    vill = sorted({clean(f["attributes"]["V_Name"]) for f in r["features"]})
    th = [(v, p) for v, p, pg in hits if pg is not None and pg.intersects(g)]
    print(f"{n:2d} {nm} [{vil}] syn {sy}: same number anywhere nearby: {[(v, p) for v, p, _ in hits][:4]} | touching outline: {th[:3]} | villages around: {vill[:5]}")
