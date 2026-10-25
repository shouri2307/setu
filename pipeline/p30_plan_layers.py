"""p30_plan_layers.py — HMDA planning-authority areas and mandal boundaries from the Telangana State GIS (TGRAC ArcGIS, HMDA_Folder/HMDA) -> web/data/plan.json

What this is: the six planning-authority areas HMDA publishes (MCH = erstwhile Municipal Corporation of Hyderabad, HUDA, CDA, HADA, HMR = rest of the HMDA region, HMR_ORR_GROWTH)
and the mandal boundaries. They say WHICH official plan governs an area. They do NOT say what land use a plot is zoned for: the plans themselves are published by HMDA as static
PDF / JPEG sheets (no machine-readable zoning layer exists on the public servers we reached), and SETU does not read them.

Checked on 24 Oct 2026: Gachibowli and Kondapur fall in CDA, Kukatpally / Uppal / LB Nagar in HUDA, Shamshabad in HADA, Charminar / Banjara Hills / Ameerpet in MCH.
The server simplifies geometry (~22 m). The ArcGIS document was created 2025-04-17; layer survey dates are not published.
Run: .venv/Scripts/python pipeline/p30_plan_layers.py"""
import json, re, time
from pathlib import Path
import requests
from shapely.geometry import Polygon
from shapely.ops import unary_union
ROOT = Path(__file__).resolve().parent.parent
H = {"User-Agent": "SETU-sideproject/0.1"}; BASE = "https://tgrac.telangana.gov.in/arcgis/rest/services/HMDA_Folder/HMDA/MapServer"
# Master Plan 2031 sheet published by HMDA per OLD mandal name (the layer's `Mandal` field); one sheet covers two mandals in four cases
SHEETS = {"Bibinagar": "BIBINAGAR", "Bommalaramaram": "BOMMALARAMARAM", "Buvanagiri": "BUVANAGIRI", "Chevella": "CHEVELLA", "Choutuppal": "CHOUTUPPAL", "Faruqnagar": "FARUQNAGAR", "Ghatkesar": "GHATKESAR",
          "Hatnura": "HATNURA", "Hayathnagar": "HAYATHNAGAR", "Ibrahimpatnam": "IBRAHIMPATNAM MANCHAL", "Manchal": "IBRAHIMPATNAM MANCHAL", "Jinnawaram": "JINNAWARAM_FPLU", "Kandukur": "KANDUKUR", "Kisara": "KISARA",
          "Kothuru": "KOTHURU", "Maheshwaram": "MAHESHWARAM", "Medchal": "MEDCHAL_QUTUBULLAPUR", "Qutubullapur": "MEDCHAL_QUTUBULLAPUR", "Moinabad": "MOINABAD_RAJENDRANAGAR", "Rajendranagar": "MOINABAD_RAJENDRANAGAR",
          "Mulug": "MULUG", "Narsapur": "NARSAPUR", "Patancheruvu": "PATANCHERUVU", "Pochampalli": "POCHAMPALLI", "Sangareddy": "SANGAREDDY", "Shahabad": "SHAHBAD", "Shahmirpet": "SHAHMIRPET", "Shamshabad": "SHAMSHABAD",
          "Shankarpalli": "SHANKARPALLI_RAMCHANDRAPURAM", "Ramchandrapuram": "SHANKARPALLI_RAMCHANDRAPURAM", "Shivampet": "SHIVAMPET", "Tupran": "TUPRAN", "Wargal": "WARGAL", "Yacharam": "YACHARAM"}

def pull(lid):
    for k in range(3):
        try:
            r = requests.get(f"{BASE}/{lid}/query", params={"f": "json", "where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": 4326, "maxAllowableOffset": 0.0002, "geometryPrecision": 5}, headers=H, timeout=180).json()
            if "features" in r: return r["features"]
        except Exception: time.sleep(3)
    raise SystemExit(f"layer {lid} could not be fetched")

def polys(geom):
    """ESRI rings -> list of {o: outer ring, h: [holes]} in [lat, lon]. Outer rings are clockwise (negative signed area), holes counter-clockwise; each hole is attached to the outer ring that contains it."""
    outs, holes = [], []
    for r in geom["rings"]:
        if len(r) < 4: continue
        a = sum(r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1] for i in range(len(r)))
        (outs if a < 0 else holes).append(Polygon(r).buffer(0))
    res = []
    for o in outs:
        hs = [h for h in holes if o.contains(h.representative_point())]
        if o.area > 1e-8: res.append({"o": o, "h": hs})   # drop zero-area slivers the server returns
    return res

def ll(poly): return [[round(y, 5), round(x, 5)] for x, y in poly.exterior.coords]

zones, mand = [], []
for f in pull(0):
    ps = polys(f["geometry"])
    zones.append({"z": f["attributes"]["ZNAME"], "polys": [{"o": ll(p["o"]), "h": [ll(h) for h in p["h"]]} for p in ps]})
for f in pull(2):
    a = f["attributes"]; ps = polys(f["geometry"]); old = (a.get("Mandal") or "").strip()
    mand.append({"m": old, "nm": (a.get("New_Mandal") or "").strip(), "d": (a.get("New_Distri") or "").strip(), "sheet": SHEETS.get(old),
                 "polys": [{"o": ll(p["o"]), "h": [ll(h) for h in p["h"]]} for p in ps]})
out = {"meta": {"source": "Telangana State GIS (TGRAC ArcGIS) HMDA layers 0 (planning-authority areas) and 2 (mandals), fetched Oct 2026", "service_created": "2025-04-17",
                "geometry": "server-simplified (~22 m)", "note": "Says which official plan governs an area. It does NOT give land-use zoning: HMDA publishes the plans as PDF / JPEG sheets only.",
                "sheet_base": "https://masterplan.hmda.gov.in/Masterplan2031/Content/",
                "pages": {"master_plan": "https://www.hmda.gov.in/planning-2/", "master_plan_2031": "https://www.hmda.gov.in/master-planning-2031/", "revised_development_plan": "https://www.hmda.gov.in/revised-development-plan/",
                          "zoning_regulations": "https://www.hmda.gov.in/wp-content/uploads/2020/07/Zoning-Regulations-and-MasterPlan-GOs.pdf", "dpms": "https://www.hmda.gov.in/dpms/"}},
       "zones": zones, "mandals": mand}
(ROOT / "web" / "data" / "plan.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
print("zones", [(z["z"], len(z["polys"])) for z in zones], "| mandal polygons", len(mand), "| without a sheet:", sorted({m["m"] for m in mand if not m["sheet"]}))
print("bytes", (ROOT / "web" / "data" / "plan.json").stat().st_size)
