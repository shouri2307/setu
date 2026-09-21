"""Size-adjusted LOEO comparison of feature sets built from different DEMs. python research/compare_dems.py"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
ROOT=Path(__file__).resolve().parent.parent
L=pd.read_csv(ROOT/'research/labels.csv'); events=sorted(L.event.unique()); big=['2016-09','2020-10-13','2025-07-18','2025-09-18','2026-06-09']
pos={e:set(L[L.event==e].ward_id) for e in events}; C=set(pd.read_csv(ROOT/'research/labels_chronic.csv').ward_id)
COLS=['hand_low_frac','twi_mean','sink_frac','waterway_near_frac','builtup_frac','elev_rel_nbrs','upstream_km2','waterbody_near_frac']
rk=lambda s: pd.Series(np.asarray(s)).rank().values/len(s)
def run(F):
    ids=F.index.tolist(); F=F.copy(); F['log_area']=np.log(F.area_km2); U=COLS+['log_area']; X0=F[U].fillna(F[U].median()).values; A=X0.copy(); A[:,-1]=np.median(A[:,-1])
    terc=pd.qcut(F.area_km2.values,3,labels=False)
    def sc_(train):
        X=np.vstack([X0 for _ in train]); y=[int(i in pos[e]) for e in train for i in ids]; s=StandardScaler().fit(X)
        lg=LogisticRegression(C=0.3,class_weight='balanced',max_iter=2000).fit(s.transform(X),y)
        rf=RandomForestClassifier(300,min_samples_leaf=15,max_depth=4,class_weight='balanced',random_state=0).fit(X,y)
        return rk(lg.decision_function(s.transform(A)))+rk(rf.predict_proba(A)[:,1])
    raw=[];st=[]
    for h in big:
        s=sc_([e for e in events if e!=h]); y=np.array([i in pos[h] for i in ids]); raw.append(roc_auc_score(y,s))
        num=den=0
        for t in range(3):
            m=terc==t
            if y[m].sum()>=2: n=y[m].sum(); num+=n*roc_auc_score(y[m],s[m]); den+=n
        st.append(num/den)
    ind=roc_auc_score([i in C for i in ids],sc_(events))
    return np.round(raw,2),round(float(np.mean(raw)),3),round(float(np.mean(st)),3),round(float(ind),3)
for n in ['features.csv','features_cop30.csv','features_fabdem.csv']:
    r=run(pd.read_csv(ROOT/'research'/n,index_col='ward_id')); print(f'{n:22s} per-event {r[0]} raw {r[1]} within-size {r[2]} GHMC-indep {r[3]}')
