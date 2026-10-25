"""p29_fetch_monsoon.py — download the monthly Open Data Telangana (TSDPS) weather files needed for complete monsoon seasons and for the heat check:
  * June-October of 2018-2025 (eight complete seasons) -> annual heavy-rain statistics
  * March-May of 2024-2026 -> mandal air temperature to compare with the Landsat surface-temperature grid
Each file has daily rain and temperature per mandal. Files go to research/external/tgdps/monsoon/ (git-ignored). Cached; safe to re-run.
Run: .venv/Scripts/python pipeline/p29_fetch_monsoon.py"""
import re, time, requests
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research" / "external" / "tgdps" / "monsoon"; OUT.mkdir(parents=True, exist_ok=True)
H = {"User-Agent": "SETU-sideproject/0.1"}
MON = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}
def get(u, **kw):
    for a in range(4):
        try:
            r = requests.get(u, headers=H, timeout=120, **kw)
            if r.status_code == 200: return r
        except Exception: pass
        time.sleep(3 + 4 * a)
    return None
r = get("https://data.telangana.gov.in/api/1/search", params={"fulltext": "Telangana Weather Data", "page-size": 20})
res = r.json().get("results", {}); items = list(res.values()) if isinstance(res, dict) else res
want = set((y, m) for y in range(2018, 2026) for m in range(6, 11)) | set((y, m) for y in (2024, 2025, 2026) for m in (3, 4, 5))
got = {}
for it in items:
    if not it.get("title", "").startswith("Telangana Weather Data"): continue
    for d in it.get("distribution", []):
        t = (d.get("title") or "").lower(); m = re.search(r"(\w+)\s+(20\d\d)", t)
        if not m or m.group(1) not in MON: continue
        key = (int(m.group(2)), MON[m.group(1)])
        if key in want and d.get("downloadURL"): got[key] = d["downloadURL"]
print("files wanted", len(want), "| found in the portal listing", len(got), "| missing", sorted(want - set(got)))
for (y, m), url in sorted(got.items()):
    f = OUT / f"w_{y}_{m:02d}.csv"
    if f.exists() and f.stat().st_size > 1000: continue
    rr = get(url)
    if rr is None: print("   FAILED", y, m); continue
    f.write_bytes(rr.content); print(f"   {y}-{m:02d} {len(rr.content)//1000} KB", flush=True)
print("done;", len(list(OUT.glob('w_*.csv'))), "files on disk")
