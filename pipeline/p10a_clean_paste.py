"""
p10a_clean_paste.py — turn the raw text ChatGPT's rate batches were pasted as into a clean data/rates_input.csv.

The pasted batches arrive in three shapes: one long line of space-separated records, code-fenced CSV with real
newlines, and rows with backslash-escaped URLs (https\\://www\\.x). Some rows also miss the confidence column or carry
one extra empty column. This script reads every record by its own shape, never by line, and reports what it repaired.

Input : data/_raw_paste.txt         Output: data/rates_input.csv  (then run p10_rates_import.py)
Run   : .venv/Scripts/python pipeline/p10a_clean_paste.py
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "_raw_paste.txt"
OUT = ROOT / "data" / "rates_input.csv"
ZONES = ROOT / "web" / "data" / "zones.json"
HEAD = ["area", "ward", "lat", "lon", "apt_low_psf", "apt_high_psf", "apt_typ_low_psf", "apt_typ_high_psf",
        "plot_low_psy", "plot_high_psy", "guidance_psy", "as_of", "confidence", "sources", "notes"]
CONF = {"none", "low", "medium", "high"}
START = re.compile(r'(?:^|(?<=\s)|(?<="))([A-Z][A-Za-z0-9 .&/\-]{1,40}?),(Ward \d+)?,(\d{2}\.\d{3,5}),(\d{2}\.\d{3,5}),')


def main():
    t = RAW.read_text(encoding="utf-8")
    t = t.replace("```", "\n").replace("\\:", ":").replace("\\.", ".").replace("\\&", "&")
    # header lines, whether on their own line or glued to the first record of a one-line batch
    t = re.sub(r"area,ward,lat,lon,apt_low_psf,apt_high_psf,apt_typ_low_psf,apt_typ_high_psf,plot_low_psy,plot_high_psy,guidance_psy,as_of,confidence,sources,notes\s*", "\n", t)
    starts = [m for m in START.finditer(t)]
    zones = {int(re.match(r"Ward (\d+)", w["name"]).group(1)): w["name"] for w in json.loads(ZONES.read_text(encoding="utf-8"))["wards"]}
    rows, repairs = [], []
    for k, m in enumerate(starts):
        seg = t[m.end(): starts[k + 1].start() if k + 1 < len(starts) else len(t)]
        q = re.search(r'"([^"]*)"\s*$', seg.strip())
        notes = q.group(1).strip() if q else ""
        body = seg.strip()[: q.start()] if q else seg.strip()
        body = body.rstrip(", ")
        sm = re.search(r"(?:^|,)([A-Za-z][^,|]*\|https?://)", body)
        head = body[: sm.start()] if sm else body
        srcs = body[sm.start():].lstrip(",") if sm else ""
        fs = head.split(",")
        while fs and fs[-1] == "":
            fs.pop()
        conf = ""
        if fs and fs[-1] in CONF:
            conf = fs.pop()
        else:
            repairs.append(f"{m.group(1)}: confidence missing -> treated as 'none'")
            conf = "none"
        asof = ""
        if fs and re.fullmatch(r"\d{4}-\d{2}", fs[-1] or ""):
            asof = fs.pop()
        nums = fs
        if len(nums) > 7:
            if any(x for x in nums[7:]):
                repairs.append(f"{m.group(1)}: unexpected data in extra columns {nums[7:]} (row skipped)")
                continue
            repairs.append(f"{m.group(1)}: dropped {len(nums) - 7} stray empty column(s)")
            nums = nums[:7]
        nums += [""] * (7 - len(nums))
        ward = m.group(2) or ""
        if ward:
            n = int(ward.split()[1])
            if n not in zones:
                repairs.append(f"{m.group(1)}: {ward} not in zones file")
                ward = ""
            else:
                zn = zones[n].lower()
                first = re.sub(r"[^a-z]", "", m.group(1).lower())[:5]
                if first not in re.sub(r"[^a-z]", "", zn):
                    repairs.append(f"{m.group(1)}: name differs from zones file '{zones[n]}' (kept ward number)")
                ward = zones[n]
        rows.append([m.group(1).strip(), ward, m.group(3), m.group(4)] + nums + [asof, conf, srcs, notes])

    # de-duplicate: same name + same numbers -> keep the one that carries a ward
    seen = {}
    for r in rows:
        key = (r[0].lower(), r[4], r[5], r[6], r[7])
        if key in seen:
            if r[1] and not seen[key][1]:
                seen[key] = r
            continue
        seen[key] = r
    rows = list(seen.values())
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEAD)
        w.writerows(rows)
    priced = sum(1 for r in rows if r[4] or r[5] or r[8] or r[10])
    print(f"records read {len(starts)} -> written {len(rows)} ({priced} with any price)")
    for x in repairs:
        print("  repair:", x)


if __name__ == "__main__":
    sys.exit(main())
