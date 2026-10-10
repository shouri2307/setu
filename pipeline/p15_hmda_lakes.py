"""
p15_hmda_lakes.py — pull HMDA's public list of notified lakes (lakes.hmda.gov.in) into web/data/hmda_lakes.json.

The portal lists ~2,980 lakes with district / mandal / village, lake ID and the dates of Preliminary and Final
Notification under HMDA's lake-protection process. The FTL (full tank level) and buffer maps themselves sit behind
per-lake postbacks and are not machine-readable here, so we ONLY take the notification status and point users to the
portal to verify the FTL/buffer for a specific plot.

Run:  .venv/Scripts/python pipeline/p15_hmda_lakes.py
"""
import html
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data" / "hmda_lakes.json"


def main():
    r = requests.get("https://lakes.hmda.gov.in/", headers={"User-Agent": "Mozilla/5.0 (SETU hackathon project)"}, timeout=90)
    r.raise_for_status()
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, flags=re.S | re.I):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S | re.I)]
        if len(cells) >= 9 and cells[0].isdigit():
            rows.append({"district": cells[1], "mandal": cells[2], "village": cells[3], "name": cells[4], "id": cells[5],
                         "prelim": cells[6] or None, "final": cells[7] or None})
    by = {}
    for x in rows:
        by[x["district"]] = by.get(x["district"], 0) + 1
    OUT.write_text(json.dumps({"source": "HMDA — Lakes information portal (lakes.hmda.gov.in)", "fetched": time.strftime("%Y-%m-%d"), "lakes": rows}, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(len(rows), "lakes", by, "final-notified:", sum(1 for x in rows if x["final"]))
    print("wrote", OUT, f"({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    sys.exit(main())
