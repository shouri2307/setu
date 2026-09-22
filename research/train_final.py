"""Train final flood-susceptibility model on ALL events: logistic + shallow random forest + gradient
boosting, rank-averaged (3-way ensemble — GB added after research/push_auc.py found it genuinely improves
held-out and independent scores; hyperparameters were tuned ONLY against the same held-out-event protocol,
never against the independent set). SIZE-ADJUSTED (log ward area is a training covariate, then fixed at
the median when scoring, so big wards are not ranked as flood-prone just for being big). Also reports
leave-one-event-out AUC (raw and within area terciles), the independent GHMC chronic-list AUC, and the
independent official vulnerable-locality check. Writes research/susceptibility.csv and
research/model_card.json.   python research/train_final.py"""
import json, warnings
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import Point
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score

F = pd.read_csv(ROOT / 'research/features.csv', index_col='ward_id'); L = pd.read_csv(ROOT / 'research/labels.csv')
ids = F.index.tolist(); events = sorted(L.event.unique())
big = ['2016-09', '2020-10-13', '2025-07-18', '2025-09-18', '2026-06-09']
pos = {e: set(L[L.event == e].ward_id) for e in events}
COLS = ['hand_low_frac', 'twi_mean', 'sink_frac', 'waterway_near_frac', 'builtup_frac', 'elev_rel_nbrs', 'upstream_km2', 'waterbody_near_frac']
F['log_area'] = np.log(F.area_km2)
USE = COLS + ['log_area']
X0 = F[USE].fillna(F[USE].median()).values
X0_adj = X0.copy(); X0_adj[:, -1] = np.median(X0[:, -1])            # score every ward at the same (median) size
rk = lambda s: pd.Series(np.asarray(s)).rank().values / len(s)
terc = pd.qcut(F.area_km2.values, 3, labels=False)


def strat_auc(y, s):
    y = np.asarray(y); num = den = 0
    for t in range(3):
        m = terc == t
        if y[m].sum() >= 2 and (~y[m].astype(bool)).sum() >= 2:
            n = y[m].sum(); num += n * roc_auc_score(y[m], np.asarray(s)[m]); den += n
    return num / den if den else np.nan


def fit_scores(train_events):
    X = np.vstack([X0 for _ in train_events]); y = [int(i in pos[e]) for e in train_events for i in ids]
    sc = StandardScaler().fit(X)
    lg = LogisticRegression(C=0.05, class_weight='balanced', max_iter=2000).fit(sc.transform(X), y)
    rf = RandomForestClassifier(500, min_samples_leaf=8, max_depth=6, class_weight='balanced', random_state=0).fit(X, y)
    gb = GradientBoostingClassifier(n_estimators=80, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=0).fit(X, y)
    ens = (rk(lg.decision_function(sc.transform(X0_adj))) + rk(rf.predict_proba(X0_adj)[:, 1])
           + rk(gb.predict_proba(X0_adj)[:, 1]))
    return ens, lg, rf


res = {}
for h in big:
    s, _, _ = fit_scores([e for e in events if e != h]); y = np.array([i in pos[h] for i in ids])
    res[h] = (roc_auc_score(y, s), strat_auc(y, s))
print('LOEO AUC (size-adjusted ensemble)   raw / within-area-tercile')
for h, v in res.items(): print(f'  {h:11s} {v[0]:.2f} / {v[1]:.2f}')
raw_mean = float(np.mean([v[0] for v in res.values()])); st_mean = float(np.nanmean([v[1] for v in res.values()]))
print(f'  mean        {raw_mean:.3f} / {st_mean:.3f}')

ens, lg, rf = fit_scores(events)
S = rk(ens)
out = pd.DataFrame({'S': S}, index=ids); out.index.name = 'ward_id'; out.round(4).to_csv(ROOT / 'research/susceptibility.csv')

Cset = set(pd.read_csv(ROOT / 'research/labels_chronic.csv').ward_id)
ind_auc = float(roc_auc_score(np.array([i in Cset for i in ids]), S))
# independent: official GHMC 'Vulnerable Localities' (248 points with exact lat/lon), never used for training
vl = json.load(open(ROOT / 'research/external/vulnerable_localities.geojson', encoding='utf-8'))['features']
vdf = pd.DataFrame([dict(lat=f['geometry']['coordinates'][1], lon=f['geometry']['coordinates'][0]) for f in vl])
wd = gpd.read_file(ROOT / 'data/zones_enriched.geojson').set_crs('EPSG:4326', allow_override=True)
j = gpd.sjoin(gpd.GeoDataFrame(vdf, geometry=[Point(x, y) for x, y in zip(vdf.lon, vdf.lat)], crs='EPSG:4326'), wd[['zone_id', 'geometry']], how='inner', predicate='within')
dens = np.array([(j.zone_id == i).sum() for i in ids]) / F.area_km2.values
vl_spear = float(np.corrcoef(rk(S), rk(dens))[0, 1]); vl_auc = float(roc_auc_score(dens >= np.quantile(dens, .75), S))
print(f'independent GHMC chronic list AUC {ind_auc:.3f} | vulnerable-locality density Spearman {vl_spear:.2f}, top-quartile AUC {vl_auc:.3f}')
print('Spearman(area, S) =', round(float(np.corrcoef(rk(F.area_km2.values), S)[0, 1]), 3), '(was 0.58 before size adjustment)')
nm = {w['id']: w['name'].replace('Ward ', '') for w in json.load(open(ROOT / 'web/data/zones.json'))['wards']}
print('Most flood-prone 15:', [nm[i] for i in out.sort_values('S', ascending=False).head(15).index])
print('Least flood-prone 10:', [nm[i] for i in out.sort_values('S').head(10).index])

card = {'independent_ghmc_chronic_auc': round(ind_auc, 3), 'vulnerable_localities_spearman': round(vl_spear, 3),
        'vulnerable_localities_top_quartile_auc': round(vl_auc, 3),
        'events': {e: int(len(pos[e])) for e in events},
        'loeo_auc_ensemble': {h: round(float(v[0]), 3) for h, v in res.items()},
        'loeo_auc_mean': round(raw_mean, 3), 'loeo_auc_within_size_mean': round(st_mean, 3),
        'features': COLS, 'size_adjusted': True, 'baseline_old_demo_model_auc_mean': 0.49}
(ROOT / 'research/model_card.json').write_text(json.dumps(card, indent=1))
