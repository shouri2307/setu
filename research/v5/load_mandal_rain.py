"""Load Open Data Telangana (TGDPS) mandal-level daily rainfall for the 8 SETU event months -> long table.
Source files live in research/external/tgdps/ (Open Government Licence India, NON-COMMERCIAL use only)."""
import pandas as pd, numpy as np
from pathlib import Path
D = Path(__file__).resolve().parent.parent / "external" / "tgdps"

def _std(df, dcol, mcol, tcol, rcol, fmt=None):
    o = pd.DataFrame({"district": df[dcol].astype(str).str.strip().str.upper(), "mandal": df[mcol].astype(str).str.strip().str.upper(),
                      "date": pd.to_datetime(df[tcol], format=fmt, errors="coerce"), "rain": pd.to_numeric(df[rcol], errors="coerce")})
    return o.dropna(subset=["date"])

def load():
    parts = []
    # 2016 wide format: columns DDMM + yy ("0106"..."3012") for the whole year
    w = pd.read_csv(D / "rain_2016_daywise.csv")
    days = [c for c in w.columns if c.isdigit() and len(c) == 4]
    m = w.melt(id_vars=["New_DIST", "NEW_MANDAL"], value_vars=days, var_name="dm", value_name="rain")
    m["date"] = pd.to_datetime("2016-" + m.dm.str[2:] + "-" + m.dm.str[:2], format="%Y-%m-%d", errors="coerce")
    parts.append(pd.DataFrame({"district": m.New_DIST.astype(str).str.strip().str.upper(), "mandal": m.NEW_MANDAL.astype(str).str.strip().str.upper(),
                               "date": m.date, "rain": pd.to_numeric(m.rain, errors="coerce")}).dropna(subset=["date"]))
    d20 = pd.read_csv(D / "weather_2020_10.csv", encoding="latin-1")
    parts.append(_std(d20, "district", "mandal", "date", "rain (mm)", "%Y-%m-%d"))
    for f in ("rain_2021_07", "rain_2023_07", "rain_2025_06", "rain_2025_07", "rain_2025_09", "rain_2026_06"):
        x = pd.read_csv(D / f"{f}.csv", encoding="latin-1")
        cols = {c.lower(): c for c in x.columns}
        rc = [c for c in x.columns if c.lower().startswith("rain")][0]
        dc = [c for c in x.columns if c.lower().startswith("date")][0]
        try: parts.append(_std(x, cols["district"], cols["mandal"], dc, rc, "%d-%b-%y"))
        except Exception: parts.append(_std(x, cols["district"], cols["mandal"], dc, rc))
    return pd.concat(parts, ignore_index=True)

if __name__ == "__main__":
    r = load(); print(len(r), r.date.min(), r.date.max())
    print(r.groupby(r.date.dt.to_period("M")).size())
    print(sorted(r[r.district.str.contains("HYD")].mandal.unique()))
    print(r.district.value_counts().head(40).to_dict())
