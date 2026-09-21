"""Is the model's skill just 'big wards get named more'? Compare raw AUC vs AUC WITHIN area terciles, and an area-adjusted model. python research/area_check.py"""
import warnings,sys; warnings.filterwarnings("ignore"); sys.path.insert(0,'research')
import numpy as np, pandas as pd
from pathlib import Path
from compare_features import *   # COLS, pos, events, big, C, rk, LogisticRegression, RandomForestClassifier, StandardScaler, roc_auc_score
F=pd.read_csv(ROOT/'research/features.csv',index_col='ward_id'); ids=F.index.tolist()
area=F.area_km2.values; terc=pd.qcut(area,3,labels=False)
def strat_auc(y,s):
    y=np.asarray(y); num=den=0
    for t in range(3):
        m=terc==t
        if y[m].sum()>=2 and (~y[m].astype(bool)).sum()>=2: n=y[m].sum(); num+=n*roc_auc_score(y[m],np.asarray(s)[m]); den+=n
    return num/den if den else np.nan
def fit_pred(cols,train,adjust_area=False):
    Fx=F.copy(); Fx['log_area']=np.log(Fx.area_km2); use=cols+(['log_area'] if adjust_area else [])
    X0=Fx[use].fillna(Fx[use].median()).values
    X=np.vstack([X0 for _ in train]); y=[int(i in pos[e]) for e in train for i in ids]
    sc=StandardScaler().fit(X); lg=LogisticRegression(C=0.3,class_weight='balanced',max_iter=2000).fit(sc.transform(X),y)
    rf=RandomForestClassifier(300,min_samples_leaf=15,max_depth=4,class_weight='balanced',random_state=0).fit(X,y)
    if adjust_area: X0=X0.copy(); X0[:,-1]=np.median(X0[:,-1])      # remove area from the ranking
    return rk(lg.decision_function(sc.transform(X0)))+rk(rf.predict_proba(X0)[:,1])
res={}
for name,fn in {'area only':lambda tr:np.log(area),'model (current)':lambda tr:fit_pred(COLS,tr),'model, area-adjusted':lambda tr:fit_pred(COLS,tr,True)}.items():
    raw=[];st=[]
    for h in big:
        s=fn([e for e in events if e!=h]); y=np.array([i in pos[h] for i in ids]); raw.append(roc_auc_score(y,s)); st.append(strat_auc(y,s))
    res[name]=(np.round(raw,2),round(float(np.mean(raw)),3),round(float(np.nanmean(st)),3))
    print(f'{name:22s} raw per-event {res[name][0]}  raw mean {res[name][1]}  WITHIN-area-tercile mean {res[name][2]}')
print('Spearman(area, model S) =',round(float(np.corrcoef(rk(area),rk(pd.read_csv(ROOT/"research/susceptibility.csv",index_col=0).S.reindex(ids)))[0,1]),3))
