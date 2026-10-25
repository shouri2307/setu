"""Point-query selected TGRAC layers at sample Hyderabad places; print what comes back (no owner/personal layers are queried)."""
import requests, json, time, sys
H = {"User-Agent": "SETU-sideproject/0.1"}; BASE = "https://tgrac.telangana.gov.in/arcgis/rest/services"
PTS = {"Gachibowli (GHMC)": (17.4401, 78.3489), "Hussain Sagar": (17.4235, 78.4745), "Old city Charminar": (17.3616, 78.4747), "Shamshabad (rural edge)": (17.2403, 78.4294), "Medchal (peri-urban)": (17.6300, 78.4800)}
LAY = [("Bhunaksha_Folder/Bhunaksha_Cadastral", 1, "Cadastral 30cm"), ("Bhunaksha_Folder/Bhunaksha", 0, "ULB_Cadastral_Prohibited"), ("Bhunaksha_Folder/Bhunaksha", 2, "ULB cadastral"),
       ("DLSFolder/Digital_Land_Survey", 8, "Base Cadastral (Survey No)"), ("HMDA_Folder/HMDA", 5, "HMDA Cadastral"),
       ("TIS_Folder/HMDA_ORR_GHMC_Water_Bodies", 16, "Water Bodies - Disappeared"), ("TIS_Folder/HMDA_ORR_GHMC_Water_Bodies", 12, "Totally Encroached WB"), ("TIS_Folder/HMDA_ORR_GHMC_Water_Bodies", 18, "SOI Water Bodies"),
       ("GWDPotential_Folder/Groundwater_Potential", 12, "Ground Water Potential"), ("Mines_Folder/Mines_Geology_Layer", 1, "Lithology"), ("Mines_Folder/Mines_Geology_Layer", 0, "Geo-Morphology"),
       ("StampsAndRegistrations_Folder/SRO", 1, "SRO Buildings"), ("StampsAndRegistrations_Folder/SRO", 2, "SRO Road Type"), ("TGIIC_Folder/Pollution_Category_Boundaries", 1, "Pollution category"),
       ("TCUR_Folder/TCUR_Telangana_Core_Urban_Region_V2", 4, "Forest Boundary")]
def q(svc, lid, lat, lon, dist=None):
    p = {"f": "json", "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "false"}
    if dist: p.update({"distance": dist, "units": "esriSRUnit_Meter"})
    t = time.time()
    try:
        r = requests.get(f"{BASE}/{svc}/MapServer/{lid}/query", params=p, headers=H, timeout=45)
        j = r.json(); return j.get("features", []), j.get("error"), time.time() - t, r.headers.get("access-control-allow-origin")
    except Exception as e: return [], str(e)[:60], time.time() - t, None
cors = set()
for nm, (la, lo) in PTS.items():
    print(f"\n######## {nm} ({la},{lo})")
    for svc, lid, lab in LAY:
        f, err, dt, c = q(svc, lid, la, lo); cors.add(c)
        if err: print(f"  {lab:28s} ERROR {str(err)[:70]}  ({dt:.1f}s)"); continue
        a = f[0]["attributes"] if f else {}
        keep = {k: v for k, v in a.items() if v not in (None, "", " ", 0) and not str(k).lower().startswith(("shape", "objectid", "fid"))}
        print(f"  {lab:28s} {len(f)} hit  {json.dumps(keep, ensure_ascii=False, default=str)[:230]}  ({dt:.1f}s)")
print("\nCORS header values seen:", cors)
