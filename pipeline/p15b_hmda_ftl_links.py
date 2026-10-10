"""
p15b_hmda_ftl_links.py — resolve HMDA's official FTL / cadastral PDF address for lakes, via the portal's own postbacks.

For each lake row the portal's "FTL" button redirects (HTTP 302) to http://lakes.hmda.gov.in/hmdalake/<id><name>_FTL.pdf.
We read that Location header (no PDF is downloaded) so every stored link is real, not guessed. Requests are paced.
Scope: lakes in Hyderabad district plus a verification sample elsewhere; set --all to resolve every row (slow).

Run:  .venv/Scripts/python pipeline/p15b_hmda_ftl_links.py [--all]
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "web" / "data" / "hmda_lakes.json"
UA = {"User-Agent": "Mozilla/5.0 (SETU hackathon project)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--districts", default="Hyderabad", help="comma list; default Hyderabad")
    args = ap.parse_args()
    doc = json.loads(FILE.read_text(encoding="utf-8"))
    lakes = doc["lakes"]
    s = requests.Session()
    s.headers.update(UA)
    page = s.get("https://lakes.hmda.gov.in/", timeout=60).text
    hid = {m.group(1): m.group(2) for m in re.finditer(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page)}
    want = set(d.strip() for d in args.districts.split(","))
    done = ok = 0
    for i, lk in enumerate(lakes):
        if not args.all and lk["district"] not in want:
            continue
        for kind, btn in (("ftl", "btn_pros"), ("cadastral", "btn_plan")):
            d = dict(hid)
            d["__EVENTTARGET"] = f"gv_showlakes$ctl{i + 2:02d}${btn}"
            d["__EVENTARGUMENT"] = ""
            try:
                r = s.post("https://lakes.hmda.gov.in/", data=d, timeout=60, allow_redirects=False)
                loc = r.headers.get("Location")
                if r.status_code == 302 and loc and loc.lower().endswith(".pdf"):
                    lk[kind + "_url"] = loc
                    ok += 1
            except Exception as e:
                print("  err", lk["name"], e)
            time.sleep(0.35)
        done += 1
        if done % 10 == 0:
            print(f"  {done} lakes processed, {ok} links", flush=True)
    FILE.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"resolved {ok} PDF links for {done} lakes")
    for lk in lakes:
        if lk.get("ftl_url") and lk["district"] == "Hyderabad":
            print(" ", lk["name"], "->", lk["ftl_url"])


if __name__ == "__main__":
    sys.exit(main())
