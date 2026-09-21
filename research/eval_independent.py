"""Independent test: model trained ONLY on flood events, scored on GHMC's official chronic-waterlogging lists."""
import json,warnings; from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from sklearn.metrics import roc_auc_score
ROOT=Path(__file__).resolve().parent.parent
F=pd.read_csv(ROOT/'research/features.csv',index_col='ward_id'); ids=F.index.tolist()
S=pd.read_csv(ROOT/'research/susceptibility.csv',index_col='ward_id')['S']
C=set(pd.read_csv(ROOT/'research/labels_chronic.csv').ward_id); y=np.array([i in C for i in ids])
wm=json.load(open(ROOT/'web/data/model.json'))
old=json.load(open('C:/Users/KSREEH~1/AppData/Local/Temp/old192.json')) if False else None
import subprocess
print('chronic list wards:',len(C))
print('NEW model S            AUC',round(roc_auc_score(y,S.reindex(ids)),3))
for c in ['hand_low_frac','sink_frac','waterbody_near_frac','area_km2','builtup_frac','elev_mean']:
    print(f'  feature {c:22s} AUC {roc_auc_score(y,F[c].fillna(F[c].median())):.3f}')
