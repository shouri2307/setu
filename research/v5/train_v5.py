"""Re-run the exact SETU validation (same models, same hyper-parameters, same 5 big-event leave-one-event-out
splits as research/train_final.py) with the GHMC-derived feature blocks added.  Writes only to research/v5/.

Variants were fixed before looking at any score:
  A baseline (reproduces research/model_card.json), B +drainage block, C +tank block, D +both.
Reports LOEO AUC, within-size-tercile AUC, a paired bootstrap CI on (variant - baseline), a shuffled-label control,
and the independent GHMC chronic-list AUC.      .venv/Scripts/python research/v5/train_v5.py
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
G = pd.read_csv(ROOT / 'research/v5/ghmc_features.csv', index_col='ward_id')
F = F.join(G)
L = pd.read_csv(ROOT / 'research/labels.csv')
ids = F.index.tolist(); events = sorted(L.event.unique())
big = ['2016-09', '2020-10-13', '2025-07-18', '2025-09-18', '2026-06-09']
pos = {e: set(L[L.event == e].ward_id) for e in events}
BASE = ['hand_low_frac', 'twi_mean', 'sink_frac', 'waterway_near_frac', 'builtup_frac', 'elev_rel_nbrs', 'upstream_km2', 'waterbody_near_frac']
DRAIN = ['ghmc_nala_len_km_per_km2', 'ghmc_nala_near_frac', 'drain_union_near_frac', 'stream11_len_km_per_km2', 'nala_width_mean']
TANK = ['tgrac_tank_area_frac', 'tgrac_tank_near_frac', 'hy_lost_area_frac', 'hy_enc_built_area_frac']
swap = lambda cols, a, b: [b if c == a else c for c in cols]
VARIANTS = {'A baseline': BASE, 'B +drainage': BASE + DRAIN, 'C +tanks': BASE + TANK, 'D +both': BASE + DRAIN + TANK,
            # E/F were added AFTER seeing the diagnostics (post-hoc, exploratory): same 8 slots, GHMC-based versions swapped in
            'E swap drainage (post-hoc)': swap(BASE, 'waterway_near_frac', 'drain_union_near_frac'),
            'F swap drainage+tank (post-hoc)': swap(swap(BASE, 'waterway_near_frac', 'drain_union_near_frac'), 'waterbody_near_frac', 'tgrac_tank_near_frac')}
F['log_area'] = np.log(F.area_km2)
rk = lambda s: pd.Series(np.asarray(s)).rank().values / len(s)
terc = pd.qcut(F.area_km2.values, 3, labels=False)


def strat_auc(y, s):
    y = np.asarray(y); num = den = 0
    for t in range(3):
        m = terc == t
        if y[m].sum() >= 2 and (~y[m].astype(bool)).sum() >= 2:
            n = y[m].sum(); num += n * roc_auc_score(y[m], np.asarray(s)[m]); den += n
    return num / den if den else np.nan


def make_fit(cols, shuffle_seed=None):
    use = cols + ['log_area']
    X0 = F[use].fillna(F[use].median()).values
    X0_adj = X0.copy(); X0_adj[:, -1] = np.median(X0[:, -1])

    def fit_scores(train_events):
        X = np.vstack([X0 for _ in train_events]); y = np.array([int(i in pos[e]) for e in train_events for i in ids])
        if shuffle_seed is not None:
            y = np.random.RandomState(shuffle_seed).permutation(y)
        sc = StandardScaler().fit(X)
        lg = LogisticRegression(C=0.05, class_weight='balanced', max_iter=2000).fit(sc.transform(X), y)
        rf = RandomForestClassifier(500, min_samples_leaf=8, max_depth=6, class_weight='balanced', random_state=0).fit(X, y)
        gb = GradientBoostingClassifier(n_estimators=80, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=0).fit(X, y)
        return (rk(lg.decision_function(sc.transform(X0_adj))) + rk(rf.predict_proba(X0_adj)[:, 1])
                + rk(gb.predict_proba(X0_adj)[:, 1]))
    return fit_scores


Cset = set(pd.read_csv(ROOT / 'research/labels_chronic.csv').ward_id)
yc = np.array([i in Cset for i in ids])
scores = {}; summary = {}
for name, cols in VARIANTS.items():
    fit = make_fit(cols)
    sc_ev = {h: fit([e for e in events if e != h]) for h in big}
    scores[name] = sc_ev
    raw = [roc_auc_score(np.array([i in pos[h] for i in ids]), sc_ev[h]) for h in big]
    wsz = [strat_auc(np.array([i in pos[h] for i in ids]), sc_ev[h]) for h in big]
    full = fit(events)
    summary[name] = dict(per_event={h: round(float(a), 3) for h, a in zip(big, raw)}, loeo=round(float(np.mean(raw)), 3),
                         within_size=round(float(np.nanmean(wsz)), 3), chronic_auc=round(float(roc_auc_score(yc, rk(full))), 3), n_features=len(cols))
    # shuffled-label control
    ctrl = []
    for sd in range(3):
        f2 = make_fit(cols, shuffle_seed=sd)
        ctrl.append(np.mean([roc_auc_score(np.array([i in pos[h] for i in ids]), f2([e for e in events if e != h])) for h in big]))
    summary[name]['shuffled_label_control'] = round(float(np.mean(ctrl)), 3)

# paired bootstrap over wards (same resample for every variant), mean across the 5 held-out events
rng = np.random.RandomState(1); B = 1000; n = len(ids)
Y = {h: np.array([i in pos[h] for i in ids]) for h in big}
boot = {k: np.zeros(B) for k in VARIANTS}
for b in range(B):
    idx = rng.randint(0, n, n)
    for k in VARIANTS:
        a = []
        for h in big:
            y = Y[h][idx]
            a.append(roc_auc_score(y, scores[k][h][idx]) if 0 < y.sum() < n else np.nan)
        boot[k][b] = np.nanmean(a)
for k in VARIANTS:
    lo, hi = np.percentile(boot[k], [2.5, 97.5]); summary[k]['loeo_ci95'] = [round(float(lo), 3), round(float(hi), 3)]
    if k != 'A baseline':
        d = boot[k] - boot['A baseline']; lo, hi = np.percentile(d, [2.5, 97.5])
        summary[k]['delta_vs_baseline'] = round(float(summary[k]['loeo'] - summary['A baseline']['loeo']), 3)
        summary[k]['delta_ci95'] = [round(float(lo), 3), round(float(hi), 3)]

for k, v in summary.items():
    print(k, json.dumps(v))
(ROOT / 'research/v5/results_v5.json').write_text(json.dumps(summary, indent=1))
