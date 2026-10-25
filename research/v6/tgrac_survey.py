"""Inspect selected TGRAC ArcGIS services: layers, geometry types, key fields, and a point-query probe at sample places."""
import requests, json, sys, time
H = {"User-Agent": "SETU-sideproject/0.1"}; BASE = "https://tgrac.telangana.gov.in/arcgis/rest/services"
def g(u, **k):
    for a in range(3):
        try:
            r = requests.get(u, headers=H, timeout=60, **k)
            if r.status_code == 200: return r.json()
        except Exception as e: err = e
        time.sleep(2)
    return None
SVC = ["Bhunaksha_Folder/Bhunaksha_Cadastral", "Bhunaksha_Folder/Bhunaksha", "DLSFolder/Digital_Land_Survey", "LIS_Folder/LandInformationSystem", "Bhubarathi_Folder/Bhubarathi",
       "Hydra_Folder/FTL_Tanks", "Hydra_Folder/FTL_Query", "GWD_Folder/GWD_Layers", "GWDPotential_Folder/Groundwater_Potential", "GWP_Folder/GWP", "EndowmentLands_Folder/EndowmentLands_Admin_2026",
       "ForestLands_Folder/ForestLands", "SoilAtlas_Folder/Soil_Atlas", "Mines_Folder/Mines_Geology_Layer", "HMDA_Folder/HMDA", "TCUR_Folder/TCUR_Telangana_Core_Urban_Region_V2", "TIS_Folder/HMDA_ORR_GHMC_Water_Bodies",
       "StampsAndRegistrations_Folder/SRO", "WaterShed_Folder/WaterShed", "RnB_Folder/RnB_Roads", "TGIIC_Folder/Pollution_Category_Boundaries", "CadastralAgricultureLULC/CadastralAgricultureLULC"]
out = {}
for s in SVC:
    j = g(f"{BASE}/{s}/MapServer", params={"f": "json"})
    if not j: print("##", s, "UNREACHABLE"); continue
    L = j.get("layers", []); print(f"\n## {s}  ({len(L)} layers) — {str(j.get('serviceDescription') or j.get('description') or '')[:90]}")
    out[s] = []
    for l in L[:40]:
        lj = g(f"{BASE}/{s}/MapServer/{l['id']}", params={"f": "json"}) or {}
        fields = [f["name"] for f in (lj.get("fields") or [])][:12]
        print(f"   [{l['id']}] {l['name'][:48]:48s} {str(lj.get('geometryType') or '?').replace('esriGeometry',''):9s} minScale={lj.get('minScale')} fields={fields}")
        out[s].append({"id": l["id"], "name": l["name"], "geom": lj.get("geometryType"), "fields": [f["name"] for f in (lj.get("fields") or [])]})
json.dump(out, open("research/v6/tgrac_services.json", "w"), indent=1)
