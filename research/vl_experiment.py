"""Does adding GHMC's official vulnerable-locality density as training labels help? (area-adjusted models) python research/vl_experiment.py"""
import warnings,sys,json; warnings.filterwarnings("ignore"); sys.path.insert(0,'research')
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import Point
import area_check as A
from area_check import *
d=json.load(open(ROOT/'research/external/vulnerable_localities.geojson',encoding='utf-8'))['features']
v=pd.DataFrame([dict(lat=f['geometry']['coordinates'][1],lon=f['geometry']['coordinates'][0]) for f in d])
w=gpd.read_file(ROOT/'data/zones_enriched.geojson').set_crs('EPSG:4326',allow_override=True)
j=gpd.sjoin(gpd.GeoDataFrame(v,geometry=[Point(x,y) for x,y in zip(v.lon,v.lat)],crs='EPSG:4326'),w[['zone_id','geometry']],how='inner',predicate='within')
cnt=np.array([(j.zone_id==i).sum() for i in ids]); dens=cnt/F.area_km2.values
VLpos=set(np.array(ids)[dens>=np.quantile(dens,0.75)]); print('VL top-quartile-density wards:',len(VLpos))
Cs=C; yC=np.array([i in Cs for i in ids]); yV=np.array([i in VLpos for i in ids])
def evaluate(use_vl):
    pos['VL']=VLpos; ev_all=events+(['VL'] if use_vl else [])
    raw=[];st=[]
    for h in big:
        s=fit_pred(COLS,[e for e in ev_all if e!=h],True); y=np.array([i in pos[h] for i in ids]); raw.append(roc_auc_score(y,s)); st.append(strat_auc(y,s))
    s_all=fit_pred(COLS,ev_all,True)
    return np.round(raw,2),round(float(np.mean(raw)),3),round(float(np.nanmean(st)),3),round(float(roc_auc_score(yC,s_all)),3)
print('events only     : per-event %s raw %s within-area %s | GHMC-chronic(indep) %s'%evaluate(False))
print('events + VL     : per-event %s raw %s within-area %s | GHMC-chronic(indep) %s'%evaluate(True))
# held-out VL test: train on events only, test VL
s=fit_pred(COLS,events,True); print('events-only model -> VL top-quartile density AUC (independent):',round(roc_auc_score(yV,s),3),'| Spearman w/ density',round(float(np.corrcoef(rk(s),rk(dens))[0,1]),3))
