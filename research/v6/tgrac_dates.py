"""Ask the TGRAC ArcGIS server what it says about each layer's date and provenance: service document info, copyright text, edit dates, and the metadata XML if it exists."""
import requests, re, json, datetime
H = {"User-Agent": "SETU-sideproject/0.1"}; B = "https://tgrac.telangana.gov.in/arcgis/rest/services"
SV = {"GHMC nalas (nalas, drains, inundation points)": ("GHMCNalas_Folder/GHMCNalas_vul", [1, 2, 5, 11, 13]), "Groundwater potential": ("GWDPotential_Folder/Groundwater_Potential", [12]),
      "Water bodies / stream order (HMDA ORR GHMC)": ("TIS_Folder/HMDA_ORR_GHMC_Water_Bodies", [13, 14, 16]), "TCUR (forest, transmission, substations)": ("TCUR_Folder/TCUR_Telangana_Core_Urban_Region_V2", [4, 12, 13]),
      "Endowment lands 2026": ("EndowmentLands_Folder/EndowmentLands_Admin_2026", [14]), "HYDRAA FTL tanks": ("Hydra_Folder/FTL_Tanks", [0])}
def g(u, **k):
    try: return requests.get(u, headers=H, timeout=60, **k)
    except Exception as e: return None
for name, (svc, layers) in SV.items():
    print(f"\n== {name}  [{svc}]")
    r = g(f"{B}/{svc}/MapServer", params={"f": "json"}); j = r.json() if r is not None and r.status_code == 200 else {}
    di = j.get("documentInfo") or {}
    print("   documentInfo:", {k: v for k, v in di.items() if v and k in ("Title", "Author", "Comments", "Subject", "Category", "Keywords")}, "| copyright:", (j.get("copyrightText") or "")[:100], "| description:", (j.get("description") or "")[:100])
    m = g(f"{B}/{svc}/MapServer/info/metadata")
    if m is not None and m.status_code == 200 and "<" in m.text:
        dates = re.findall(r"<(?:pubdate|caldate|date|revdate|CreaDate|ModDate|mdDateSt|idCitation)[^>]*>([^<]{4,20})<", m.text); print("   metadata xml found:", len(m.text), "bytes; dates in it:", dates[:6])
    else: print("   metadata xml: none")
    for lid in layers:
        lj = (g(f"{B}/{svc}/MapServer/{lid}", params={"f": "json"}).json() if g(f"{B}/{svc}/MapServer/{lid}", params={"f": "json"}) is not None else {})
        ei = lj.get("editingInfo") or {}; le = ei.get("lastEditDate")
        print(f"   layer {lid} {str(lj.get('name'))[:36]:36s} lastEditDate: {datetime.datetime.utcfromtimestamp(le/1000).strftime('%Y-%m-%d') if le else 'not published'} | description: {str(lj.get('description') or '')[:60]!r} | copyright: {str(lj.get('copyrightText') or '')[:50]!r}")
