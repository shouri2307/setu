"""Compare feature sets (SRTM vs COP30) with the SAME protocol: leave-one-event-out AUC + independent GHMC-list AUC. python research/compare_features.py"""
import warnings, sys; from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
ROOT=Path(__file__).resolve().parent.parent
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
L=pd.read_csv(ROOT/'research/labels.csv'); events=sorted(L.event.unique()); big=['2016-09','2020-10-13','2025-07-18','2025-09-18','2026-06-09']
pos={e:set(L[L.event==e].ward_id) for e in events}; C=set(pd.read_csv(ROOT/'research/labels_chronic.csv').ward_id)
COLS=['hand_low_frac','twi_mean','sink_frac','waterway_near_frac','builtup_frac','elev_rel_nbrs','upstream_km2','waterbody_near_frac']
rk=lambda s: pd.Series(s).rank().values/len(s)
def score(F,cols,train):
    ids=F.index.tolist(); X0=F[cols].fillna(F[cols].median()).values
    X=np.vstack([X0 for _ in train]); y=[int(i in pos[e]) for e in train for i in ids]
    sc=StandardScaler().fit(X); lg=LogisticRegression(C=0.3,class_weight='balanced',max_iter=2000).fit(sc.transform(X),y)
    rf=RandomForestClassifier(300,min_samples_leaf=15,max_depth=4,class_weight='balanced',random_state=0).fit(X,y)
    return rk(lg.decision_function(sc.transform(X0)))+rk(rf.predict_proba(X0)[:,1])
def run(F,cols=COLS):
    ids=F.index.tolist(); out=[]
    for h in big:
        s=score(F,cols,[e for e in events if e!=h]); out.append(roc_auc_score([i in pos[h] for i in ids],s))
    s=score(F,cols,events); ind=roc_auc_score([i in C for i in ids],s)
    return np.round(out,3),round(float(np.mean(out)),3),round(float(ind),3)
if __name__=='__main__':
    for name in ['features.csv','features_cop30.csv']:
        F=pd.read_csv(ROOT/'research'/name,index_col='ward_id'); r=run(F); print(f'{name:20s} per-event {r[0]}  mean {r[1]}  independent {r[2]}')
    # single-feature look at the top signals under each DEM
    for name in ['features.csv','features_cop30.csv']:
        F=pd.read_csv(ROOT/'research'/name,index_col='ward_id'); ids=F.index.tolist()
        m={c:round(np.mean([roc_auc_score([i in pos[e] for i in ids],F[c].fillna(F[c].median())) for e in big]),3) for c in ['hand_low_frac','sink_frac','twi_mean','elev_rel_nbrs']}
        print(name,m)
