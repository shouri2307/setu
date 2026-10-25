"""Source discovery, step 2: look inside the specific candidate layers. Metadata, counts, extents, and point queries at real places (no bulk download, no owner/personal fields shown).
.venv/Scripts/python research/v8/discover_probe.py"""
import requests, json, re, time
H = {"User-Agent": "SETU-sideproject/0.1"}; B = "https://tgrac.telangana.gov.in/arcgis/rest/services"
OWN = re.compile(r"owner|pattadar|khata|holder|father|aadhaar|phone|mobile|dharani|pass", re.I)
def get(u, **p):
    p["f"] = "json"
    for k in range(3):
        try: return requests.get(u, params=p, headers=H, timeout=90).json()
        except Exception: time.sleep(2)
    return {"error": "request failed"}
PTS = {"Charminar": (17.3616, 78.4747), "Gachibowli": (17.4401, 78.3489), "Hussain Sagar": (17.4235, 78.4745), "Saroornagar lake": (17.3558, 78.5260), "Kukatpally": (17.4948, 78.3996)}
def svc_summary(name):
    for typ in ("MapServer", "FeatureServer"):
        j = get(f"{B}/{name}/{typ}")
        if j.get("layers") or j.get("tables") or j.get("serviceDescription") is not None:
            ls = j.get("layers", [])
            di = j.get("documentInfo") or {}; m = get(f"{B}/{name}/{typ}/info/metadata") if False else None
            return typ, ls, j
    return None, [], {}
def layer_probe(svc, typ, lid, label, points=True):
    u = f"{B}/{svc}/{typ}/{lid}"; m = get(u)
    if "error" in m: print(f"\n[{label}] {svc}/{lid}: ERROR {m['error']}"); return
    c = get(u + "/query", where="1=1", returnCountOnly="true").get("count")
    fl = [f["name"] for f in (m.get("fields") or []) if not f["name"].lower().startswith(("shape", "objectid", "fid")) and not OWN.search(f["name"])]
    print(f"\n[{label}] {svc}/{lid} '{m.get('name')}' type={m.get('geometryType')} count={c}\n   fields: {', '.join(fl)[:380]}")
    for sl in (m.get("subLayers") or [])[:6]:
        layer_probe(svc, typ, sl["id"], label + " > " + str(sl.get("name")), points)
    if not points or m.get("geometryType") is None: return
    for pn, (la, lo) in PTS.items():
        env = f"{lo - 0.004},{la - 0.004},{lo + 0.004},{la + 0.004}"
        r = get(u + "/query", geometry=env, geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects", outFields="*", returnGeometry="false", resultRecordCount=3)
        fs = r.get("features", [])
        keep = [{k: v for k, v in f["attributes"].items() if v not in (None, "", " ", 0) and not k.lower().startswith(("shape", "objectid", "fid")) and not OWN.search(k)} for f in fs]
        print(f"   {pn:17s} {len(fs)} within ~900 m" + (f" e.g. {json.dumps(keep[0], ensure_ascii=False, default=str)[:230]}" if keep else ""))
print("##### 1. FTL / lake boundary services (Hydra folder)")
for s in ("Hydra_Folder/FTL_Tanks", "Hydra_Folder/FTL_Query", "Hydra_Folder/Topo_Tanks", "Hydra_Folder/WaterBody_Monitoring_Rasters", "Hydra_Folder/First_Window", "Hydra_Folder/Third_Window", "Hydra_Folder/Fourth_Window"):
    typ, ls, j = svc_summary(s); print(f"\n== {s}: {typ} layers: {[(l['id'], l['name']) for l in ls][:12]}")
    if typ and ls:
        for l in ls[:3]:
            layer_probe(s, typ, l["id"], "FTL")
print("\n##### 2. Cadastral with the old city?")
layer_probe("Bhunaksha_Folder/Bhunaksha_query", "MapServer", 0, "Full Cadastral"); layer_probe("Bhunaksha_Folder/Bhunaksha_query", "MapServer", 7, "Cadastral")
print("\n##### 3. TCUR fire stations, flooding area, seismic zones")
T = "TCUR_Folder/TCUR_Telangana_Core_Urban_Region_V2"
for lid, lab in ((61, "Fire stations"), (89, "Flooding Area"), (90, "Seismic Zones")): layer_probe(T, "MapServer", lid, lab)
print("\n##### 4. other fire-station layers"); layer_probe("PoliceProperties_Folder/Police_Admin_Layers", "MapServer", 15, "Fire stations (police admin)", points=False); layer_probe("TGIIC_Folder/BaseLayers", "MapServer", 11, "Fire stations (TGIIC)", points=False)
print("\n##### 5. Musi basin (GHMC watersheds, tanks, buffer)")
M = "MusiRiver/Musi_Basin_Web_Publication_vector"
for lid, lab in ((19, "Musi tanks"), (38, "GHMC watersheds"), (104, "Bufferzone 500 m"), (110, "Water body information")): layer_probe(M, "MapServer", lid, lab, points=lid in (19, 104, 110))
