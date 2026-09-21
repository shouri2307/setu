"""Geocode the parsed GHMC 2017 waterlogging points -> research/external/ghmc_points_geocoded.csv. python research/geocode_ghmc_points.py"""
import json, time, re, requests, pandas as pd
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; H={'User-Agent':'SETU-research/1.0 (student project)'}
pts=json.load(open(ROOT/'research/external/ghmc_points_parsed.json')); BB=(78.20,17.20,78.70,17.65)
def q(text):
    time.sleep(1.1)
    try: r=requests.get('https://nominatim.openstreetmap.org/search',params={'q':text+', Hyderabad, Telangana','format':'json','limit':1,'viewbox':f'{BB[0]},{BB[3]},{BB[2]},{BB[1]}','bounded':1},headers=H,timeout=30).json()
    except Exception: r=[]
    return (float(r[0]['lat']),float(r[0]['lon'])) if r else None
rows=[]
for p in pts:
    loc=re.sub(r'\b(both sides|near|opp|opposite)\b','',p['loc'],flags=re.I).strip(' .,')
    hit=q(loc); tier='full'
    if not hit:
        parts=[x.strip() for x in re.split(r',',p['loc']) if x.strip()]
        if len(parts)>1: hit=q(parts[-1]); tier='tail'
    if not hit:
        w=re.findall(r'([A-Z][a-zA-Z\.]+(?: [A-Z][a-zA-Z\.]+)?)',p['loc']); 
        if w: hit=q(w[-1]); tier='lastcap'
    rows.append(dict(**p,lat=hit[0] if hit else None,lon=hit[1] if hit else None,tier=tier if hit else 'none'))
    if len(rows)%20==0: pd.DataFrame(rows).to_csv(ROOT/'research/external/ghmc_points_geocoded.csv',index=False); print(len(rows),flush=True)
pd.DataFrame(rows).to_csv(ROOT/'research/external/ghmc_points_geocoded.csv',index=False); print('done',len(rows),sum(r['lat'] is not None for r in rows))
