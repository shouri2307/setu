"""Leave-one-event-out evaluation of flood-susceptibility models. python research/eval.py"""
import sys, json, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
ROOT=Path(__file__).resolve().parent.parent
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score

F=pd.read_csv(ROOT/'research/features.csv',index_col='ward_id'); L=pd.read_csv(ROOT/'research/labels.csv')
ids=F.index.tolist(); events=sorted(L.event.unique()); big=['2016-09','2020-10-13','2025-07-18','2025-09-18','2026-06-09']
pos={e:set(L[L.event==e].ward_id) for e in events}
wm=json.load(open(ROOT/'web/data/model.json')); old192=pd.Series({int(k):v for k,v in wm['depths']['192'].items()}).reindex(ids).fillna(0)
cur=json.load(open(ROOT/'data/scenarios.json'))['scenarios']['192']; cur192=pd.Series({int(k):v for k,v in cur.items()}).reindex(ids).fillna(0)
def auc(score,e): 
    y=np.array([i in pos[e] for i in ids]); return roc_auc_score(y,np.asarray(score))
print('events',{e:len(pos[e]) for e in events})
print('\n== baselines (AUC per big event; 0.5 = coin flip) ==')
rows={'old demo model @192':old192,'current repo p3 @192':cur192}
for k,s in rows.items(): print(f'{k:28s}',{e:round(auc(s,e),2) for e in big},'mean',round(np.mean([auc(s,e) for e in big]),3))
print('\n== single features (sign chosen by pooled direction; AUC mean over big events) ==')
res=[]
for c in F.columns:
    a=np.mean([auc(F[c].fillna(F[c].median()),e) for e in big]); res.append((c,a))
for c,a in sorted(res,key=lambda t:-abs(t[1]-.5)): print(f'{c:26s} AUC(high=flood) {a:.3f}')

def loeo(cols,C=0.3,ev=big):
    out={}
    for h in ev:
        tr=[e for e in events if e!=h]
        X=[];y=[]
        for e in tr:
            X.append(F[cols].fillna(F[cols].median()).values); y+= [int(i in pos[e]) for i in ids]
        X=np.vstack(X); sc=StandardScaler().fit(X)
        m=LogisticRegression(C=C,class_weight='balanced',max_iter=1000).fit(sc.transform(X),y)
        s=m.decision_function(sc.transform(F[cols].fillna(F[cols].median()).values)); out[h]=auc(s,h)
    return out
sets={
 'A physical-lite (hand,twi,sink,waterway_near,builtup)':['hand_mean','hand_low_frac','twi_mean','sink_frac','waterway_near_frac','builtup_frac'],
 'B + water/terrain (elev_rel,upstream,waterbody)':['hand_low_frac','twi_mean','sink_frac','waterway_near_frac','builtup_frac','elev_rel_nbrs','upstream_km2','waterbody_near_frac'],
 'C all features':list(F.columns),
}
print('\n== learned model, leave-one-event-out AUC ==')
for n,c in sets.items():
    o=loeo(c); print(f'{n:58s}',{k:round(v,2) for k,v in o.items()},'mean',round(np.mean(list(o.values())),3))

# ---- variations (all leave-one-event-out) ----
print('\n== variations ==')
from sklearn.ensemble import RandomForestClassifier
core=['hand_low_frac','twi_mean','sink_frac','waterway_near_frac','builtup_frac','elev_rel_nbrs','upstream_km2','waterbody_near_frac']
for C in [0.03,0.1,0.3,1,3]:
    o=loeo(core,C=C); print(f'logistic B  C={C:<5}',{k:round(v,2) for k,v in o.items()},'mean',round(np.mean(list(o.values())),3))
mini=['hand_low_frac','sink_frac','waterbody_near_frac']
o=loeo(mini,C=0.3); print('logistic mini(3 feats)',{k:round(v,2) for k,v in o.items()},'mean',round(np.mean(list(o.values())),3))
def loeo_rf(cols):
    out={}
    for h in big:
        tr=[e for e in events if e!=h]; Xf=F[cols].fillna(F[cols].median()).values
        X=np.vstack([Xf for e in tr]); y=[int(i in pos[e]) for e in tr for i in ids]
        m=RandomForestClassifier(300,min_samples_leaf=15,max_depth=4,class_weight='balanced',random_state=0).fit(X,y)
        out[h]=auc(m.predict_proba(Xf)[:,1],h)
    return out
o=loeo_rf(core); print('random forest (shallow)',{k:round(v,2) for k,v in o.items()},'mean',round(np.mean(list(o.values())),3))
# rank-average of hand_low_frac + sink_frac + waterbody_near (no fitting at all)
r=lambda s: s.rank()/len(s)
naive=r(F.hand_low_frac)+r(F.sink_frac)+r(F.waterbody_near_frac)
o={e:auc(naive,e) for e in big}; print('NO-FIT rank average of 3 physical feats',{k:round(v,2) for k,v in o.items()},'mean',round(np.mean(list(o.values())),3))
# permutation sanity: shuffle labels -> AUC should be ~0.5
rng=np.random.default_rng(1); import copy
sav=copy.deepcopy(pos); perm=[]
for _ in range(20):
    for e in events: pos[e]=set(rng.choice(ids,len(sav[e]),replace=False))
    perm.append(np.mean(list(loeo(core).values())))
pos=sav; print('shuffled-label control mean AUC',round(np.mean(perm),3),'+/-',round(np.std(perm),3),'(should be ~0.5)')
