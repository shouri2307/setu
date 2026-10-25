import requests, json, collections
H={"User-Agent":"SETU-sideproject/0.1"}; B="https://tgrac.telangana.gov.in/arcgis/rest/services/TIS_Folder/HMDA_ORR_GHMC_Water_Bodies/MapServer"
ENV="78.20,17.20,78.75,17.70"
ids=sorted(requests.get(f"{B}/13/query",params={"f":"json","geometry":ENV,"geometryType":"esriGeometryEnvelope","inSR":4326,"spatialRel":"esriSpatialRelIntersects","returnIdsOnly":"true"},headers=H,timeout=90).json()["objectIds"])
A=[]
for i in range(0,len(ids),150):
    j=requests.get(f"{B}/13/query",params={"f":"json","objectIds":",".join(map(str,ids[i:i+150])),"outFields":"FID,Area,Bund_Heigh,Volume,MCFT,WBS_2023,WBS_2011,WB_Name,Village,Mandal,Area_Total,WB_Type,WB_Source","returnGeometry":"false"},headers=H,timeout=90).json()
    A+=[f["attributes"] for f in j["features"]]
def f(v):
    try: return float(str(v).strip())
    except Exception: return None
print(len(A),"records; unique FID",len({a["FID"] for a in A}))
ok=n=0
for a in A:
    ar,bh,vol=f(a["Area"]),f(a["Bund_Heigh"]),f(a["Volume"])
    if ar and bh and vol: n+=1; ok+= abs(vol-ar*bh/2)/vol<0.02
print("Volume = Area x Bund_Height / 2 holds for",ok,"of",n)
mc=[(f(a["MCFT"]),f(a["Volume"])) for a in A if f(a["MCFT"]) and f(a["Volume"])]; print("median Volume_m3 / MCFT =",round(sorted(v/m for m,v in mc)[len(mc)//2]),"(1 MCFT = 28,317 m3)")
for nm in ("Hussain","Saroor","Himayat","Osman","Durgam","Mir Alam","Pedda"):
    for a in A:
        if a["WB_Name"] and nm.lower() in a["WB_Name"].lower() and f(a["Area"]): print(f"{a['WB_Name']:30s} Area {f(a['Area'])/1e4:.1f} ha | Area_Total {a['Area_Total']} | bund {a['Bund_Heigh']} m | volume {(f(a['Volume']) or 0)/1e6:.2f} Mm3 | 2023: {a['WBS_2023']} | 2011: {a['WBS_2011']}")
print("types:",collections.Counter(a["WB_Type"] for a in A).most_common(5),"| source:",collections.Counter(a["WB_Source"] for a in A).most_common(5))
print("named:",sum(1 for a in A if (a["WB_Name"] or '').strip()),"| bund missing/zero:",sum(1 for a in A if not f(a["Bund_Heigh"])),"| Area missing:",sum(1 for a in A if not f(a["Area"])))
print("sum of Volume over all records: %.0f Mm3"%(sum(f(a["Volume"]) or 0 for a in A)/1e6))
at=[(f(a["Area"]) or 0)/1e4 for a in A if f(a["Area_Total"])]; atot=[f(a["Area_Total"]) for a in A if f(a["Area_Total"])]
print("Area(ha) vs Area_Total: Area_Total >= Area/1e4 in",sum(1 for x,y in zip(at,atot) if y>=x*0.99),"of",len(at))
print("Area_Total examples (Area ha, Area_Total):",[(round(x,1),round(y,1)) for x,y in list(zip(at,atot))[:8]])
