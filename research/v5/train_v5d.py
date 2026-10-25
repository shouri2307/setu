"""v5d: add worst-case (tail) terrain features, alone and together with rainfall. Same protocol as v5b.
Variants fixed in advance: A static; T1 static+tail; R2 static+rain; RT static+tail+rain."""
import json, sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
exec(compile(open(HERE / 'train_v5b.py', encoding='utf-8').read().split("Y = {h:")[0], 'v5b_head', 'exec'))
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
T = pd.read_csv(HERE / 'tail_features.csv', index_col='ward_id'); TAIL = list(T.columns)
G = F.join(T); G['log_area'] = np.log(G.area_km2)

def mat(e, scols, rcols, adj):
    X = G[scols + ['log_area']].fillna(G[scols + ['log_area']].median()).values.copy()
    if adj: X[:, len(scols)] = np.median(X[:, len(scols)])
    return np.hstack([X, RAIN[e][rcols].values]) if rcols else X

def fp(train_events, test_event, scols, rcols, seed=None):
    X = np.vstack([mat(e, scols, rcols, False) for e in train_events]); y = np.array([int(i in pos[e]) for e in train_events for i in ids])
    if seed is not None: y = np.random.RandomState(seed).permutation(y)
    Xt = mat(test_event, scols, rcols, True); sc = StandardScaler().fit(X)
    lg = LogisticRegression(C=0.05, class_weight='balanced', max_iter=3000).fit(sc.transform(X), y)
    rf = RandomForestClassifier(500, min_samples_leaf=8, max_depth=6, class_weight='balanced', random_state=0, n_jobs=-1).fit(X, y)
    gb = GradientBoostingClassifier(n_estimators=80, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=0).fit(X, y)
    return rk(lg.decision_function(sc.transform(Xt))) + rk(rf.predict_proba(Xt)[:, 1]) + rk(gb.predict_proba(Xt)[:, 1])

V = {'A static': (BASE, []), 'T1 +tail': (BASE + TAIL, []), 'R2 +rain': (BASE, ['rain_rel', 'ev_rain_mm']), 'RT +tail+rain': (BASE + TAIL, ['rain_rel', 'ev_rain_mm'])}
Yd = {h: np.array([i in pos[h] for i in ids]) for h in events}
res, sc_all = {}, {}
for k, (sc_, rc) in V.items():
    s = {h: fp([e for e in events if e != h], h, sc_, rc) for h in events}; sc_all[k] = s
    a = {h: roc_auc_score(Yd[h], s[h]) for h in events}
    ctrl = np.mean([np.mean([roc_auc_score(Yd[h], fp([e for e in events if e != h], h, sc_, rc, seed=sd)) for h in big]) for sd in range(2)])
    res[k] = dict(loeo_big5=round(float(np.mean([a[h] for h in big])), 3), loeo_all8_mean=round(float(np.mean(list(a.values()))), 3),
                  per_event={h: round(float(v), 3) for h, v in a.items()}, control=round(float(ctrl), 3)); print(k, res[k], flush=True)
rng = np.random.RandomState(1); B = 1000; n = len(ids); boot = {k: np.zeros(B) for k in V}
for b in range(B):
    idx = rng.randint(0, n, n)
    for k in V: boot[k][b] = np.nanmean([roc_auc_score(Yd[h][idx], sc_all[k][h][idx]) if 0 < Yd[h][idx].sum() < n else np.nan for h in big])
for k in V:
    res[k]['ci95'] = [round(float(x), 3) for x in np.percentile(boot[k], [2.5, 97.5])]
    if k != 'A static': res[k]['delta_vs_A'] = [round(res[k]['loeo_big5'] - res['A static']['loeo_big5'], 3), [round(float(x), 3) for x in np.percentile(boot[k] - boot['A static'], [2.5, 97.5])]]
    print(k, res[k]['loeo_big5'], res[k]['ci95'], res[k].get('delta_vs_A'))
(HERE / 'results_v5d.json').write_text(json.dumps(res, indent=1))
