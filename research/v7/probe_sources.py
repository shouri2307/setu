"""Batch 4 source audit: what do the candidate TGRAC layers for water service, sewer, planning and parcels actually contain in Hyderabad?
Step 1 prints layer metadata (fields, total count, extent). Step 2 point/near queries at sample places. Owner / personal fields are never printed or stored.
Run: .venv/Scripts/python research/v7/probe_sources.py [meta|points]"""
import requests, json, time, sys, re
H = {"User-Agent": "SETU-sideproject/0.1"}; BASE = "https://tgrac.telangana.gov.in/arcgis/rest/services"
TC = "TCUR_Folder/TCUR_Telangana_Core_Urban_Region_V2"
LAY = [(TC, 30, "HMWSSB valve"), (TC, 31, "HMWSSB source line"), (TC, 32, "HMWSSB supply line"), (TC, 33, "HMWSSB pumphouse"), (TC, 34, "HMWSSB reservoir"), (TC, 35, "HMWSSB docket boundary"),
       (TC, 36, "HMWSSB section boundary"), (TC, 38, "Core-city manholes"), (TC, 39, "Core-city sewer line"), (TC, 22, "TCUR proposed core urban area"),
       ("HMDA_Folder/HMDA", 5, "HMDA Cadastral"), ("HMDA_Folder/HMDA", 6, "HMDA Pocket"), ("HMDA_Folder/HMDA", 4, "HMDA Manufacture(Industrial)"), ("HMDA_Folder/HMDA", 3, "HMDA Village"),
       ("Bhunaksha_Folder/Bhunaksha", 2, "ULB cadastral"), ("Bhunaksha_Folder/Bhunaksha", 4, "ULB Villages"), ("Bhunaksha_Folder/Bhunaksha", 5, "ULB"),
       ("StampsAndRegistrations_Folder/SRO", 0, "SRO circle"), ("StampsAndRegistrations_Folder/SRO", 1, "SRO buildings"), ("StampsAndRegistrations_Folder/SRO", 2, "SRO road type")]
PTS = {"Gachibowli": (17.4401, 78.3489), "Hussain Sagar": (17.4235, 78.4745), "Charminar": (17.3616, 78.4747), "Banjara Hills": (17.4126, 78.4482), "Kukatpally": (17.4948, 78.3996),
       "Secunderabad": (17.4399, 78.4983), "Shamshabad edge": (17.2403, 78.4294), "Medchal": (17.6300, 78.4800)}
OWNER = re.compile(r"owner|name_of|pattadar|khata|holder|father|aadhaar|phone|mobile|dharani|pass", re.I)

def get(url, **p):
    p["f"] = "json"
    t = time.time()
    try: j = requests.get(url, params=p, headers=H, timeout=60).json()
    except Exception as e: return {"error": str(e)[:80]}, time.time() - t
    return j, time.time() - t

def meta():
    for svc, lid, lab in LAY:
        u = f"{BASE}/{svc}/MapServer/{lid}"
        m, dt = get(u)
        c, _ = get(u + "/query", where="1=1", returnCountOnly="true")
        e, _ = get(u + "/query", where="1=1", returnExtentOnly="true", outSR=4326)
        flds = [f["name"] for f in m.get("fields", []) if not f["name"].lower().startswith(("shape", "objectid", "fid"))]
        safe = [f for f in flds if not OWNER.search(f)]; held = [f for f in flds if OWNER.search(f)]
        ex = e.get("extent") or {}
        print(f"\n[{lab}] {svc}/{lid}  count={c.get('count', c.get('error'))}  type={m.get('geometryType')}  extent=" + (f"{ex.get('xmin', 0):.3f},{ex.get('ymin', 0):.3f} .. {ex.get('xmax', 0):.3f},{ex.get('ymax', 0):.3f}" if ex else "n/a") + f"  ({dt:.1f}s)")
        print("   fields:", ", ".join(safe)[:420]);
        if held: print("   (owner/personal-looking fields NOT shown:", len(held), ")")
        print("   desc:", (m.get("description") or "")[:140].replace("\n", " "), "| copyright:", (m.get("copyrightText") or "")[:80])

def points():
    for nm, (la, lo) in PTS.items():
        print(f"\n#### {nm} ({la},{lo})")
        for svc, lid, lab in LAY:
            line = "Line" in lab or "line" in lab or "valve" in lab or "manhole" in lab
            p = dict(geometry=f"{lo},{la}", geometryType="esriGeometryPoint", inSR=4326, spatialRel="esriSpatialRelIntersects", outFields="*", returnGeometry="false")
            if line: p.update(distance=300, units="esriSRUnit_Meter")
            j, dt = get(f"{BASE}/{svc}/MapServer/{lid}/query", **p)
            if "error" in j: print(f"  {lab:30s} ERROR {str(j['error'])[:60]} ({dt:.1f}s)"); continue
            fs = j.get("features", []); a = fs[0]["attributes"] if fs else {}
            keep = {k: v for k, v in a.items() if v not in (None, "", " ", 0) and not k.lower().startswith(("shape", "objectid", "fid")) and not OWNER.search(k)}
            print(f"  {lab:30s} {len(fs):3d} hit {json.dumps(keep, ensure_ascii=False, default=str)[:200]} ({dt:.1f}s)")

if __name__ == "__main__":
    {"meta": meta, "points": points}[sys.argv[1] if len(sys.argv) > 1 else "meta"]()
