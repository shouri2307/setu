"""Geocode flood locality names -> research/geocodes.csv (lat, lon, matched, query). Nominatim, 1 req/s. python research/geocode_labels.py"""
import re, time, json, csv, requests, pandas as pd
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
L=pd.read_csv(ROOT/'research/labels.csv'); H={'User-Agent':'SETU-research/1.0 (student project)'}
BB=(78.20,17.20,78.70,17.65)   # lon_min, lat_min, lon_max, lat_max
def variants(t):
    t=str(t); out=[]
    inner=re.findall(r'\(([^)]*)\)',t); base=re.sub(r'\([^)]*\)','',t)
    for part in re.split(r'[/,]',base+'/'+'/'.join(inner)):
        p=re.sub(r'\b(junction|road|ward)\b','',part,flags=re.I).strip()
        if p and p not in out: out.append(p)
    return out
cache={}; rows=[]
for _,r in L.iterrows():
    hit=None
    for v in variants(r.locality_named):
        key=v.lower()
        if key not in cache:
            time.sleep(1.1)
            try:
                res=requests.get('https://nominatim.openstreetmap.org/search',params={'q':f'{v}, Hyderabad, Telangana, India','format':'json','limit':1,'viewbox':f'{BB[0]},{BB[3]},{BB[2]},{BB[1]}','bounded':1},headers=H,timeout=30).json()
            except Exception as e: res=[]
            cache[key]=(float(res[0]['lat']),float(res[0]['lon']),res[0].get('display_name','')[:60]) if res else None
        if cache[key]: hit=(v,)+cache[key]; break
    rows.append(dict(event=r.event,ward_id=r.ward_id,locality=r.locality_named,query=hit[0] if hit else '',lat=hit[1] if hit else '',lon=hit[2] if hit else '',match=hit[3] if hit else ''))
pd.DataFrame(rows).to_csv(ROOT/'research/geocodes.csv',index=False)
g=pd.DataFrame(rows); print('geocoded',(g.lat!='').sum(),'of',len(g))
