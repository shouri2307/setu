"""v5c: (1) are the learned weights sensible? (2) does re-tuning help when it is done WITHOUT seeing the test event
(nested leave-one-event-out)? (3) what do the two NRSC-confirmed Oct-2020 label corrections change?
Reuses fit/predict machinery from train_v5b (same models and protocol)."""
import json, sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import importlib.util
src = open(str(__import__('pathlib').Path(__file__).resolve().parent / 'train_v5b.py'), encoding='utf-8').read().split("Y = {h:")[0]
exec(compile(src, 'train_v5b_head', 'exec'))   # defines F, L, RAIN, pos, ids, events, big, VARIANTS, rows, fit_predict, strat_auc, rk ...
from sklearn.metrics import roc_auc_score
Y = lambda h: np.array([i in pos[h] for i in ids])

# ---- (1) learned weights: standardized logistic coefficients, baseline vs R2 ----
for name in ('A static only', 'R2 +rain_rel+ev_rain'):
    rc = VARIANTS[name]
    X = np.vstack([rows(e, rc) for e in events]); y = np.array([int(i in pos[e]) for e in events for i in ids])
    from sklearn.preprocessing import StandardScaler; from sklearn.linear_model import LogisticRegression
    sc = StandardScaler().fit(X); lg = LogisticRegression(C=0.05, class_weight='balanced', max_iter=3000).fit(sc.transform(X), y)
    cols = BASE + ['log_area'] + rc
    print(f"\nlogistic weights ({name}), standardised, +ve = more flood-prone:")
    for c, w in sorted(zip(cols, lg.coef_[0]), key=lambda t: -abs(t[1])): print(f"   {c:22s} {w:+.3f}")

# ---- (2) nested hyper-parameter selection ----
GRID = [dict(C=0.05, leaf=8, depth=6, trees=300, gb=80), dict(C=0.01, leaf=15, depth=4, trees=300, gb=50), dict(C=0.2, leaf=4, depth=8, trees=300, gb=150)]
def loeo_mean(train_events, rc, p):
    return np.mean([roc_auc_score(Y(h), fit_predict([e for e in train_events if e != h], h, rc, params=p)[0]) for h in train_events])
print("\nnested tuning (hyper-parameters chosen on the 7 training events only):")
out = {}
for name in ('A static only', 'R2 +rain_rel+ev_rain'):
    rc = VARIANTS[name]; fixed, nested, picks = [], [], []
    for h in big:
        tr = [e for e in events if e != h]
        sc = [loeo_mean(tr, rc, p) for p in GRID]; k = int(np.argmax(sc)); picks.append(k)
        nested.append(roc_auc_score(Y(h), fit_predict(tr, h, rc, params=GRID[k])[0]))
        fixed.append(roc_auc_score(Y(h), fit_predict(tr, h, rc, params=GRID[0])[0]))
    out[name] = dict(fixed=round(float(np.mean(fixed)), 3), nested=round(float(np.mean(nested)), 3), picks=picks, per_event_nested={h: round(float(v), 3) for h, v in zip(big, nested)})
    print(f"   {name:24s} fixed-params {np.mean(fixed):.3f} | nested-tuned {np.mean(nested):.3f} | grid picks per fold {picks}", flush=True)

# ---- (3) NRSC-confirmed corrections to the Oct-2020 labels (ward 21 Ramanthapur, ward 27 Jeedimetla) ----
pos_orig = {k: set(v) for k, v in pos.items()}
pos['2020-10-13'] |= {21, 27}
print("\nwith the 2 NRSC-confirmed Oct-2020 wards added as positives (labels change for training AND testing):")
for name in ('A static only', 'R2 +rain_rel+ev_rain'):
    rc = VARIANTS[name]
    a = {h: roc_auc_score(Y(h), fit_predict([e for e in events if e != h], h, rc)[0]) for h in big}
    out[name]['with_nrsc_labels'] = dict(loeo_big5=round(float(np.mean(list(a.values()))), 3), per_event={h: round(float(v), 3) for h, v in a.items()})
    print(f"   {name:24s} LOEO big5 {np.mean(list(a.values())):.3f}  per-event {{{', '.join(f'{h}:{v:.2f}' for h, v in a.items())}}}")
pos.update(pos_orig)
open(str(__import__('pathlib').Path(__file__).resolve().parent / 'results_v5c.json'), 'w').write(json.dumps(out, indent=1))
