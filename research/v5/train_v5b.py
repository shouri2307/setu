"""v5b: the same models and the same leave-one-event-out protocol as research/train_final.py, but the training rows are
ward x event and each row carries THAT event's rainfall at the ward (Open Data Telangana mandal readings).
At test time the held-out event's own rainfall map is supplied, exactly as the app would supply a forecast/scenario.

Variants fixed before looking at scores:
  A  static only (reproduces research/model_card.json)
  R1 + rain_rel                     (how much more/less than the city average this ward got: the storm's spatial footprint)
  R2 + rain_rel + ev_rain_mm        (and the absolute amount)
  R3 + rain_rel + ev_rain_mm + ant_rain_mm   (and the rain in the 5 days before)
Reports LOEO AUC over the 5 big events (comparable with 0.689) and over all 8 events, within-size AUC, a paired bootstrap
CI on (variant - A), and a shuffled-label control.   .venv/Scripts/python research/v5/train_v5b.py
"""
import json, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent.parent
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score

F = pd.read_csv(ROOT / 'research/features.csv', index_col='ward_id')
L = pd.read_csv(ROOT / 'research/labels.csv')
RN = pd.read_csv(ROOT / 'research/v5/ward_event_rain.csv')
ids = F.index.tolist(); events = sorted(L.event.unique())
big = ['2016-09', '2020-10-13', '2025-07-18', '2025-09-18', '2026-06-09']
pos = {e: set(L[L.event == e].ward_id) for e in events}
BASE = ['hand_low_frac', 'twi_mean', 'sink_frac', 'waterway_near_frac', 'builtup_frac', 'elev_rel_nbrs', 'upstream_km2', 'waterbody_near_frac']
F['log_area'] = np.log(F.area_km2)
RN['ant_rain_mm'] = RN.ant_rain_mm.fillna(RN.ant_rain_mm.median())
RAIN = {e: RN[RN.event == e].set_index('ward_id').reindex(ids) for e in events}
VARIANTS = {'A static only': [], 'R1 +rain_rel': ['rain_rel'], 'R2 +rain_rel+ev_rain': ['rain_rel', 'ev_rain_mm'],
            'R3 +..+antecedent': ['rain_rel', 'ev_rain_mm', 'ant_rain_mm']}
rk = lambda s: pd.Series(np.asarray(s)).rank().values / len(s)
terc = pd.qcut(F.area_km2.values, 3, labels=False)
S0 = F[BASE + ['log_area']].fillna(F[BASE + ['log_area']].median()).values


def strat_auc(y, s):
    y = np.asarray(y); num = den = 0
    for t in range(3):
        m = terc == t
        if y[m].sum() >= 2 and (~y[m].astype(bool)).sum() >= 2:
            n = y[m].sum(); num += n * roc_auc_score(y[m], np.asarray(s)[m]); den += n
    return num / den if den else np.nan


def rows(e, rain_cols, adj=False):
    X = S0.copy()
    if adj: X[:, len(BASE)] = np.median(S0[:, len(BASE)])          # score at the median ward size
    if rain_cols: X = np.hstack([X, RAIN[e][rain_cols].values])
    return X


def fit_predict(train_events, test_event, rain_cols, shuffle_seed=None, params=None):
    p = dict(C=0.05, leaf=8, depth=6, trees=500, gb=80) if params is None else params
    X = np.vstack([rows(e, rain_cols) for e in train_events]); y = np.array([int(i in pos[e]) for e in train_events for i in ids])
    if shuffle_seed is not None: y = np.random.RandomState(shuffle_seed).permutation(y)
    Xt = rows(test_event, rain_cols, adj=True)
    sc = StandardScaler().fit(X)
    lg = LogisticRegression(C=p['C'], class_weight='balanced', max_iter=3000).fit(sc.transform(X), y)
    rf = RandomForestClassifier(p['trees'], min_samples_leaf=p['leaf'], max_depth=p['depth'], class_weight='balanced', random_state=0, n_jobs=-1).fit(X, y)
    gb = GradientBoostingClassifier(n_estimators=p['gb'], max_depth=2, learning_rate=0.05, subsample=0.8, random_state=0).fit(X, y)
    return rk(lg.decision_function(sc.transform(Xt))) + rk(rf.predict_proba(Xt)[:, 1]) + rk(gb.predict_proba(Xt)[:, 1]), lg


Y = {h: np.array([i in pos[h] for i in ids]) for h in events}
summary, scores = {}, {}
for name, rc in VARIANTS.items():
    sc_ev = {h: fit_predict([e for e in events if e != h], h, rc)[0] for h in events}
    scores[name] = sc_ev
    a = {h: roc_auc_score(Y[h], sc_ev[h]) for h in events}
    w = {h: strat_auc(Y[h], sc_ev[h]) for h in big}
    npos = np.array([Y[h].sum() for h in events])
    ctrl = np.mean([np.mean([roc_auc_score(Y[h], fit_predict([e for e in events if e != h], h, rc, shuffle_seed=sd)[0]) for h in big]) for sd in range(2)])
    summary[name] = dict(per_event={h: round(float(v), 3) for h, v in a.items()}, loeo_big5=round(float(np.mean([a[h] for h in big])), 3),
                         within_size_big5=round(float(np.nanmean(list(w.values()))), 3), loeo_all8_mean=round(float(np.mean(list(a.values()))), 3),
                         loeo_all8_pos_weighted=round(float(np.average([a[h] for h in events], weights=npos)), 3), shuffled_label_control=round(float(ctrl), 3))
    print(name, json.dumps(summary[name]), flush=True)

rng = np.random.RandomState(1); B = 1000; n = len(ids)
boot = {k: np.zeros(B) for k in VARIANTS}
for b in range(B):
    idx = rng.randint(0, n, n)
    for k in VARIANTS:
        boot[k][b] = np.nanmean([roc_auc_score(Y[h][idx], scores[k][h][idx]) if 0 < Y[h][idx].sum() < n else np.nan for h in big])
for k in VARIANTS:
    summary[k]['loeo_big5_ci95'] = [round(float(x), 3) for x in np.percentile(boot[k], [2.5, 97.5])]
    if k != 'A static only':
        d = boot[k] - boot['A static only']
        summary[k]['delta_vs_A'] = round(float(summary[k]['loeo_big5'] - summary['A static only']['loeo_big5']), 3)
        summary[k]['delta_ci95'] = [round(float(x), 3) for x in np.percentile(d, [2.5, 97.5])]
for k, v in summary.items(): print(k, v.get('loeo_big5'), v.get('loeo_big5_ci95'), v.get('delta_vs_A'), v.get('delta_ci95'))
(ROOT / 'research/v5/results_v5b.json').write_text(json.dumps(summary, indent=1))
