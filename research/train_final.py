"""Train final flood-susceptibility (logistic + shallow random forest, rank-averaged) on ALL events.
Also reports leave-one-event-out AUC of the ensemble. Writes research/susceptibility.csv. python research/train_final.py"""
import json, warnings; from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
ROOT=Path(__file__).resolve().parent.parent
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
F=pd.read_csv(ROOT/'research/features.csv',index_col='ward_id'); L=pd.read_csv(ROOT/'research/labels.csv')
ids=F.index.tolist(); events=sorted(L.event.unique()); big=['2016-09','2020-10-13','2025-07-18','2025-09-18','2026-06-09']
pos={e:set(L[L.event==e].ward_id) for e in events}
COLS=['hand_low_frac','twi_mean','sink_frac','waterway_near_frac','builtup_frac','elev_rel_nbrs','upstream_km2','waterbody_near_frac']
X0=F[COLS].fillna(F[COLS].median()).values
rk=lambda s: pd.Series(s).rank().values/len(s)
def fit_scores(train_events):
    X=np.vstack([X0 for _ in train_events]); y=[int(i in pos[e]) for e in train_events for i in ids]
    sc=StandardScaler().fit(X); lg=LogisticRegression(C=0.3,class_weight='balanced',max_iter=2000).fit(sc.transform(X),y)
    rf=RandomForestClassifier(500,min_samples_leaf=15,max_depth=4,class_weight='balanced',random_state=0).fit(X,y)
    s_lg=lg.decision_function(sc.transform(X0)); s_rf=rf.predict_proba(X0)[:,1]
    return s_lg,s_rf,lg,rf
res={}
for h in big:
    s_lg,s_rf,_,_=fit_scores([e for e in events if e!=h]); y=np.array([i in pos[h] for i in ids])
    res[h]=(roc_auc_score(y,s_lg),roc_auc_score(y,s_rf),roc_auc_score(y,rk(s_lg)+rk(s_rf)))
print('LOEO AUC   logistic / forest / ENSEMBLE')
for h,v in res.items(): print(f'  {h:11s}',*[f'{x:.2f}' for x in v])
print('  mean       ',*[f'{np.mean([v[i] for v in res.values()]):.3f}' for i in range(3)])
s_lg,s_rf,lg,rf=fit_scores(events)
ens=rk(rk(s_lg)+rk(s_rf))          # in [0,1], 1 = most flood-prone
out=pd.DataFrame({'S_logit_rank':rk(s_lg),'S_forest_rank':rk(s_rf),'S':ens},index=ids); out.index.name='ward_id'
out.round(4).to_csv(ROOT/'research/susceptibility.csv')
print('\nlogistic coefficients (standardised):',dict(zip(COLS,lg.coef_[0].round(2))))
print('forest importances:',dict(zip(COLS,rf.feature_importances_.round(2))))
nm={w['id']:w['name'].replace('Ward ','') for w in json.load(open(ROOT/'web/data/zones.json'))['wards']}
top=out.sort_values('S',ascending=False).head(15); print('\nMost flood-prone 15:',[f"{nm[i]}" for i in top.index])
print('Least flood-prone 10:',[nm[i] for i in out.sort_values('S').head(10).index])

Cset=set(pd.read_csv(ROOT/'research/labels_chronic.csv').ward_id)
ind_auc=round(float(roc_auc_score(np.array([i in Cset for i in ids]),ens)),3)
card={'independent_ghmc_chronic_auc':ind_auc,'events':{e:int(len(pos[e])) for e in events},'loeo_auc_ensemble':{h:round(float(v[2]),3) for h,v in res.items()},
      'loeo_auc_mean':round(float(np.mean([v[2] for v in res.values()])),3),'features':COLS,
      'baseline_old_demo_model_auc_mean':0.49}
(ROOT/'research/model_card.json').write_text(json.dumps(card,indent=1))
