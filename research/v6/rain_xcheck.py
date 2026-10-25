import sys, re, json
from pathlib import Path
import pandas as pd, numpy as np
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "pipeline")); sys.path.insert(0, str(ROOT / "research" / "v5"))
src = open(ROOT / "pipeline/p28_rainstats.py", encoding="utf-8").read().split("frames, qc = [], {}")[0]
src = src.replace('ROOT = Path(__file__).resolve().parent.parent', f'ROOT = Path(r"{ROOT}")'); exec(src)
from load_mandal_rain import load
fr = [read(y, m)[0].assign(y=y, m=m) for y in YEARS for m in MONTHS]; R = pd.concat(fr, ignore_index=True)
old = load(); old["key"] = old.mandal.map(norm).map(lambda k: ALIAS.get(k, k)); od = old[old.key.isin(keys)]
oagg = od.groupby(["key", "date"], as_index=False).rain.agg(["mean", "count", "min", "max"]).reset_index()
j = oagg.merge(R[["key", "date", "rain"]], on=["key", "date"]); j["diff"] = (j["mean"] - j["rain"]).abs()
print("shared mandal-days", len(j), "| differing by >0.1 mm:", int((j["diff"] > .1).sum()), "| by >5 mm:", int((j["diff"] > 5).sum()))
bad = j[j["diff"] > 5].sort_values("diff", ascending=False)
print("by month:", bad.date.dt.to_period("M").value_counts().to_dict()); print("by mandal:", bad.key.value_counts().head(8).to_dict())
print(bad.head(10)[["key", "date", "mean", "count", "min", "max", "rain"]].to_string())
# how many raw old rows exist per (key,date) for the bad ones (several records under the same normalised name?)
