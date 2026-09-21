"""Extra candidate features -> appended to research/features.csv (road density, lake area fraction). python research/extra_features.py"""
import sys,json,warnings; from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import LineString
from shapely.strtree import STRtree
warnings.filterwarnings("ignore")
ROOT=Path(__file__).resolve().parent.parent; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'pipeline'))
import config
sys.path.insert(0,str(ROOT/"archive")); import p3_flood_demo_v2 as old
M="EPSG:32644"
g=gpd.read_file(config.DATA/'zones_enriched.geojson').set_crs("EPSG:4326",allow_override=True); g.index=g.zone_id.astype(int); gm=g.to_crs(M)
raw=json.loads(Path(config.OSM_ROADS).read_text()); lines=[]
for el in raw['elements']:
    geom=el.get('geometry')
    if geom and len(geom)>1: lines.append(LineString([(p['lon'],p['lat']) for p in geom]))
rl=gpd.GeoSeries(lines,crs="EPSG:4326").to_crs(M); tree=STRtree(list(rl.geometry)); geoms=list(rl.geometry)
water=old._load_water_union(M)
road=[];wf=[]
for i,r in gm.iterrows():
    idx=tree.query(r.geometry); L=sum(geoms[j].intersection(r.geometry).length for j in idx)
    road.append(L/1000/(r.geometry.area/1e6)); wf.append(r.geometry.intersection(water).area/r.geometry.area if water is not None else np.nan)
F=pd.read_csv(ROOT/'research/features.csv',index_col='ward_id')
F['road_km_per_km2']=pd.Series(road,index=gm.index); F['waterbody_area_frac']=pd.Series(wf,index=gm.index)
F.round(4).to_csv(ROOT/'research/features.csv'); print(F[['road_km_per_km2','waterbody_area_frac']].describe().round(3))
