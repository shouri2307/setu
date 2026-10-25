"""Source discovery, step 3: the HYDRAA FTL group layers (sub-layer ids), the lake-side cadastral (Fourth_Window), and where TCUR 'Flooding Area' is.   .venv/Scripts/python research/v8/discover_probe2.py"""
import requests, json, re, time, collections
H = {"User-Agent": "SETU-sideproject/0.1"}; B = "https://tgrac.telangana.gov.in/arcgis/rest/services"
OWN = re.compile(r"owner|pattadar|khata|holder|father|aadhaar|phone|mobile|dharani|pass", re.I)
def get(u, **p):
    p["f"] = "json"
    for k in range(3):
        try: return requests.get(u, params=p, headers=H, timeout=90).json()
        except Exception: time.sleep(2)
    return {"error": "x"}
PTS = {"Saroornagar lake": (17.3558, 78.5260), "Hussain Sagar": (17.4235, 78.4745), "Gachibowli (Kummari Kunta)": (17.4401, 78.3489), "Mir Alam Tank": (17.3296, 78.4425)}
for svc in ("Hydra_Folder/FTL_Tanks", "Hydra_Folder/Topo_Tanks"):
    print(f"\n######## {svc}")
    for lid in range(0, 9):
        u = f"{B}/{svc}/MapServer/{lid}"; m = get(u)
        if m.get("error") or not m.get("name"): continue
        g = m.get("geometryType"); c = get(u + "/query", where="1=1", returnCountOnly="true").get("count") if g else None
        fl = [f["name"] for f in (m.get("fields") or []) if not f["name"].lower().startswith(("shape", "objectid", "fid")) and not OWN.search(f["name"])]
        print(f"  layer {lid}: '{m['name']}' geom={g} count={c} sub={[s.get('id') for s in (m.get('subLayers') or [])]} fields={', '.join(fl)[:200]}")
        if g and c:
            for pn, (la, lo) in PTS.items():
                r = get(u + "/query", geometry=f"{lo - 0.004},{la - 0.004},{lo + 0.004},{la + 0.004}", geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects", outFields="*", returnGeometry="false", resultRecordCount=2)
                fs = r.get("features", []); keep = [{k: v for k, v in f["attributes"].items() if v not in (None, "", " ", 0) and not k.lower().startswith(("shape", "objectid", "fid")) and not OWN.search(k)} for f in fs]
                print(f"      {pn:27s} {len(fs)} hit" + (f"  {json.dumps(keep[0], ensure_ascii=False, default=str)[:260]}" if keep else ""))
print("\n######## Fourth_Window cadastral (HYDRAA): what kinds of polygon?")
u = f"{B}/Hydra_Folder/Fourth_Window/MapServer/0/query"
for fld in ("TYPE", "Remarks", "D_Name"):
    r = get(u, where="1=1", groupByFieldsForStatistics=fld, outStatistics=json.dumps([{"statisticType": "count", "onStatisticField": "geodb_oid", "outStatisticFieldName": "n"}]), orderByFields="n DESC", resultRecordCount=12)
    print(" ", fld, [(x["attributes"].get(fld), x["attributes"]["n"]) for x in r.get("features", [])] if r.get("features") else r.get("error"))
ext = get(u, where="1=1", returnExtentOnly="true", outSR=4326).get("extent")
print("  extent:", {k: round(v, 3) for k, v in (ext or {}).items() if k in ("xmin", "ymin", "xmax", "ymax")})
print("\n######## TCUR layer 89 'Flooding Area': where is it?")
e = get(f"{B}/TCUR_Folder/TCUR_Telangana_Core_Urban_Region_V2/MapServer/89/query", where="1=1", returnExtentOnly="true", outSR=4326).get("extent"); print("  extent:", {k: round(v, 3) for k, v in (e or {}).items() if k in ("xmin", "ymin", "xmax", "ymax")})
r = get(f"{B}/TCUR_Folder/TCUR_Telangana_Core_Urban_Region_V2/MapServer/89/query", where="1=1", outFields="Flood", returnGeometry="false", resultRecordCount=30); print("  values:", collections.Counter(f["attributes"]["Flood"] for f in r.get("features", [])))
