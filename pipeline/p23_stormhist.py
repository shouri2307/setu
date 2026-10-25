"""p23_stormhist.py — what each ward's mandal actually recorded in the 8 documented floods, and whether the ward was named flooded
(research/v5/ward_event_rain.csv + research/labels.csv) -> web/data/stormhist.json.
Rain = Open Data Telangana (TSDPS) mandal daily rainfall, day of the storm plus the next day (their day runs 08:30-08:30). Non-commercial licence."""
import json
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent
rain = pd.read_csv(ROOT / "research/v5/ward_event_rain.csv"); L = pd.read_csv(ROOT / "research/labels.csv")
EV = [("2016-09", "Sep 2016", "2016-09-23"), ("2020-10-13", "Oct 2020", "2020-10-13"), ("2021-07-14", "Jul 2021", "2021-07-14"), ("2023-07-27", "Jul 2023", "2023-07-27"),
      ("2025-06-12", "Jun 2025", "2025-06-12"), ("2025-07-18", "Jul 2025", "2025-07-18"), ("2025-09-18", "Sep 2025", "2025-09-18"), ("2026-06-09", "Jun 2026", "2026-06-09")]
named = {e: set(L[L.event == e].ward_id) for e, _, _ in EV}
wards = {}
for wid, g in rain.groupby("ward_id"):
    g = g.set_index("event")
    wards[str(int(wid))] = {"m": str(g.mandal.iloc[0]).title(), "r": [None if pd.isna(g.loc[e, "ev_rain_mm"]) else round(float(g.loc[e, "ev_rain_mm"])) for e, _, _ in EV],
                            "n": [int(int(wid) in named[e]) for e, _, _ in EV]}
city = {e: round(float(rain[rain.event == e].ev_rain_mm.mean())) for e, _, _ in EV}
out = {"meta": {"source": "Open Data Telangana (TSDPS) mandal-level daily rainfall; flood naming from news-sourced ward labels (research/labels.csv)", "licence": "TSDPS data is non-commercial only",
                "note": "mandal rainfall is the nearest official gauge reading, not a reading at the ward; 'named' means a news report named the ward, not that it is the only place that flooded"},
       "events": [{"id": e, "label": l, "date": d, "city_mean_mm": city[e], "named_wards": len(named[e])} for e, l, d in EV], "wards": wards}
(ROOT / "web/data/stormhist.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8"); print(len(wards), "wards;", out["events"][1])
