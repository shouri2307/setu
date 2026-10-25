"""Independent check of web/data/network.json. For six places, fetch the RAW pipes from the state server with their geometry (no simplification), clip them exactly against each ~100 m cell with shapely
(the pipeline instead samples every ~20 m), and compare per-cell length and largest diameter with what is stored. Also a completeness check: the raw pipes intersecting each place's 3x3 cell window,
counted by shapely, against the server's own envelope query.   .venv/Scripts/python research/v7/validate_network.py"""
import json, re, requests
from pathlib import Path
import pyproj
from shapely.geometry import LineString, box
from shapely.ops import transform
ROOT = Path(__file__).resolve().parent.parent.parent
H = {"User-Agent": "SETU-sideproject/0.1"}; B = "https://tgrac.telangana.gov.in/arcgis/rest/services/TCUR_Folder/TCUR_Telangana_Core_Urban_Region_V2/MapServer"
net = json.load(open(ROOT / "web/data/network.json")); m = net["meta"]; NX, NY, C, X0, Y0 = m["nx"], m["ny"], m["cell_deg"], m["bbox"][0], m["bbox"][1]
tr = pyproj.Transformer.from_crs(4326, 32644, always_xy=True).transform
INUSE = re.compile(r"^IN\s?USE", re.I)
PLACES = {"Charminar": (17.3616, 78.4747), "Banjara Hills": (17.4126, 78.4482), "Secunderabad": (17.4399, 78.4983), "Dilsukhnagar": (17.3688, 78.5247), "Kukatpally": (17.4948, 78.3996), "Gachibowli": (17.4401, 78.3489)}
stored = {"supply": {c[0]: (c[1], c[2]) for c in net["supply"]}, "sewer": {c[0]: (c[1], c[2]) for c in net["sewer"]}}
LAYERS = {"supply": (32, "SIZE_IN_MM"), "sewer": (39, "SP_PIPE_DI")}
worst = {"supply": 0, "sewer": 0}; tot_ok = tot = 0; dia_bad = 0
print("| place | layer | cells with pipe (raw / stored) | 3x3 window length m (raw / stored) | worst cell difference m | diameter mismatches |\n|---|---|---|---|---|---|")
for name, (la, lo) in PLACES.items():
    i0 = int((lo - X0) // C); j0 = int((la - Y0) // C)
    for layer, (lid, dia) in LAYERS.items():
        x0, y0 = X0 + (i0 - 1) * C, Y0 + (j0 - 1) * C; env = (x0, y0, x0 + 3 * C, y0 + 3 * C)
        r = requests.get(f"{B}/{lid}/query", params={"f": "json", "where": "1=1", "geometry": ",".join(f"{v:.7f}" for v in env), "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
                                                  "outFields": f"SP_STATUS,{dia}", "returnGeometry": "true", "outSR": 4326}, headers=H, timeout=180).json()
        fs = [f for f in r["features"] if INUSE.match(str(f["attributes"].get("SP_STATUS") or "").strip())]
        raw_len = {}; raw_dia = {}
        for dj in range(3):
            for di in range(3):
                cb = box(X0 + (i0 - 1 + di) * C, Y0 + (j0 - 1 + dj) * C, X0 + (i0 + di) * C, Y0 + (j0 + dj) * C); cell = (j0 - 1 + dj) * NX + (i0 - 1 + di)
                L = 0.0; D = 0
                for f in fs:
                    for p in f["geometry"]["paths"]:
                        if len(p) < 2: continue
                        g = LineString(p).intersection(cb)
                        if g.is_empty: continue
                        l = transform(tr, g).length
                        if l > 0: L += l; D = max(D, float(f["attributes"].get(dia) or 0))
                if L > 0: raw_len[cell] = L; raw_dia[cell] = D
        cells = set(raw_len) | {c for c in stored[layer] if abs(c // NX - j0) <= 1 and abs(c % NX - i0) <= 1}
        diffs = [abs(raw_len.get(c, 0) - stored[layer].get(c, (0, 0))[0]) for c in cells]; wd = max(diffs) if diffs else 0; worst[layer] = max(worst[layer], wd)
        dm = sum(1 for c in cells if raw_dia.get(c, 0) != stored[layer].get(c, (0, 0))[1]); dia_bad += dm
        sl = sum(stored[layer].get(c, (0, 0))[0] for c in cells); rl = sum(raw_len.values())
        tot += len(cells); tot_ok += sum(1 for d in diffs if d <= max(25, 0.15 * max(raw_len.get(c, 0) for c in cells)))
        print(f"| {name} | {layer} | {len(raw_len)} / {sum(1 for c in cells if c in stored[layer])} | {rl:.0f} / {sl:.0f} | {wd:.0f} | {dm} |")
print(f"\ncells compared: {tot}, within max(25 m, 15% of the window's longest cell): {tot_ok}; worst single-cell difference supply {worst['supply']:.0f} m, sewer {worst['sewer']:.0f} m; diameter mismatches {dia_bad}")
