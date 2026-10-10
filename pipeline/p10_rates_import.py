"""
p10_rates_import.py — merge a ChatGPT-compiled rates CSV into web/data/rates.json.

Input : data/rates_input.csv  (columns exactly as in docs/CHATGPT_RATES_PROMPTS.md)
Output: web/data/rates.json   (hand-curated entries are kept; imported ones are marked origin="llm-compiled")

Run:    .venv/Scripts/python pipeline/p10_rates_import.py

Safety checks (rows failing a hard check are dropped and reported; soft ones are kept but flagged):
  hard : no numbers at all · low > high · price outside a plausible Hyderabad range · lat/lon outside the study area
  soft : no source URL (confidence forced to 'low') · typical band outside low-high (clamped) ·
         price more than 2.2x/0.45x the median of its ward neighbours (flagged as outlier)
Nothing here "verifies" a price. The app labels these rows as AI-compiled estimates.
"""
import csv
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "rates_input.csv"
OUT = ROOT / "web" / "data" / "rates.json"
ZONES = ROOT / "web" / "data" / "zones.json"
HAND = ROOT / "research" / "rates_handcurated.json"
BBOX = (78.20, 17.18, 78.72, 17.66)  # lon_min, lat_min, lon_max, lat_max
APT_RANGE = (1500, 60000)            # Rs per sq ft
PLOT_RANGE = (3000, 600000)          # Rs per sq yd


def num(x):
    x = re.sub(r"[^\d.]", "", str(x or ""))
    return float(x) if x else None


def main():
    if not SRC.exists():
        print(f"Missing {SRC}. Paste ChatGPT's CSV replies there (one header line) and re-run.")
        return 2
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    kept = [l for l in doc["localities"] if l.get("origin") != "llm-compiled"]  # keep hand-curated entries
    wards = {w["name"].lower(): w["id"] for w in json.loads(ZONES.read_text(encoding="utf-8"))["wards"]}

    rows, dropped, flagged = [], [], []
    with SRC.open(encoding="utf-8-sig", newline="") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            if not r.get("area") or r["area"].strip().lower() == "area":
                continue
            area = r["area"].strip()
            lat, lon = num(r.get("lat")), num(r.get("lon"))
            lo, hi, tl, th = (num(r.get(k)) for k in ("apt_low_psf", "apt_high_psf", "apt_typ_low_psf", "apt_typ_high_psf"))
            plo, phi, gv = (num(r.get(k)) for k in ("plot_low_psy", "plot_high_psy", "guidance_psy"))
            if lo is None and hi is None and plo is None and phi is None and gv is None:
                dropped.append((i, area, "no prices (left empty on purpose)"))
                continue
            if lat is None or lon is None or not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
                dropped.append((i, area, f"lat/lon missing or outside Hyderabad ({lat},{lon})"))
                continue
            if lo is not None and hi is None:
                hi = lo
            if hi is not None and lo is None:
                lo = hi
            if lo is not None:
                if lo > hi:
                    dropped.append((i, area, f"low {lo} > high {hi}"))
                    continue
                if not (APT_RANGE[0] <= lo and hi <= APT_RANGE[1]):
                    dropped.append((i, area, f"apartment price outside plausible range {lo}-{hi}"))
                    continue
            if plo is not None and phi is not None and not (PLOT_RANGE[0] <= plo <= phi <= PLOT_RANGE[1]):
                dropped.append((i, area, f"plot price implausible {plo}-{phi}"))
                continue
            srcs = []
            for part in (r.get("sources") or "").split(";"):
                if "|" in part:
                    n, u = part.split("|", 1)
                    if u.strip().startswith("http"):
                        srcs.append({"name": n.strip(), "url": u.strip()})
            conf = (r.get("confidence") or "low").strip().lower()
            if conf not in ("high", "medium", "low"):
                conf = "low"
            if not srcs:
                conf = "low"
                flagged.append((i, area, "no source URL — forced to low confidence"))
            if lo is not None:
                typ = [tl or lo, th or hi]
                if typ[0] < lo or typ[1] > hi or typ[0] > typ[1]:
                    typ = [max(lo, min(typ[0], hi)), min(hi, max(typ[1], lo))]
                    typ.sort()
            ward = None
            w = (r.get("ward") or "").strip().lower()
            if w in wards:
                ward = wards[w]
            e = {"name": area, "lat": lat, "lon": lon, "conf": conf, "origin": "llm-compiled", "asOf": (r.get("as_of") or "").strip(),
                 "sources": srcs or [{"name": "ChatGPT-compiled, no source given", "url": ""}]}
            if lo is not None:
                e.update({"low": int(lo), "high": int(hi), "typical": [int(typ[0]), int(typ[1])]})
            if plo is not None and phi is not None:
                e["plot"] = {"low": int(plo), "high": int(phi)}
            if gv is not None:
                e["guidance"] = int(gv)
            if ward is not None:
                e["ward"] = ward
            if (r.get("notes") or "").strip():
                e["note"] = r["notes"].strip()[:240]
            rows.append(e)

    # outlier screen: compare each apartment midpoint with the median of rows within ~4 km
    def hav(a, b, c, d):
        import math
        p = math.pi / 180
        x = (1 - math.cos((c - a) * p)) / 2 + math.cos(a * p) * math.cos(c * p) * (1 - math.cos((d - b) * p)) / 2
        return 12742000 * math.asin(math.sqrt(x))
    for e in rows:
        if "low" not in e:
            continue
        mid = (e["low"] + e["high"]) / 2
        near = [(x["low"] + x["high"]) / 2 for x in rows if x is not e and "low" in x and hav(e["lat"], e["lon"], x["lat"], x["lon"]) < 4000]
        if len(near) >= 3:
            med = statistics.median(near)
            if mid > 2.2 * med or mid < 0.45 * med:
                e["flag"] = "outlier vs neighbours"
                flagged.append((0, e["name"], f"midpoint {mid:.0f} vs neighbour median {med:.0f}"))

    # same place from more than one source set -> one entry whose band is the outer limits of all of them
    # (hand-curated rows live in research/rates_handcurated.json so a re-run never loses them)
    kept = json.loads(HAND.read_text(encoding="utf-8"))["localities"] if HAND.exists() else kept
    rank = {"low": 0, "medium": 1, "high": 2}

    def key(n):
        return re.sub(r"[^a-z0-9]", "", n.lower())
    groups = {}
    for e in kept + rows:
        groups.setdefault(key(e["name"]), []).append(e)
    merged_rows, merged_n = [], 0
    for g in groups.values():
        priced = [x for x in g if "low" in x]
        if len(priced) < 2:
            merged_rows += g
            continue
        base = dict(next((x for x in priced if "ward" in x), priced[0]))
        base["low"], base["high"] = min(x["low"] for x in priced), max(x["high"] for x in priced)
        tl, th = max(x["typical"][0] for x in priced), min(x["typical"][1] for x in priced)
        base["typical"] = [tl, th] if tl <= th else [round(sum(x["typical"][0] for x in priced) / len(priced)), round(sum(x["typical"][1] for x in priced) / len(priced))]
        base["conf"] = min((x["conf"] for x in priced), key=lambda c: rank[c])
        base["sources"] = [s for x in priced for s in x["sources"]]
        for x in priced:
            if "ward" in x:
                base["ward"] = x["ward"]
        base["origin"] = "merged"
        base["asOf"] = max(x.get("asOf") or "" for x in priced)
        lows = sorted(x["low"] for x in priced)
        base["note"] = f"{len(priced)} source sets disagree ({'; '.join(f'{x['low']}-{x['high']}' for x in priced)}); the band shows the outer limits of all of them."[:240]
        if max(x["high"] for x in priced) / max(1, min(x["low"] for x in priced)) > 2.2:
            base["conf"] = "low"
        base.pop("flag", None)
        merged_rows.append(base)
        merged_n += 1
    flagged_names = {n for _, n, _ in flagged}
    kept = [x for x in merged_rows if x.get("origin") != "llm-compiled"]
    rows = [x for x in merged_rows if x.get("origin") == "llm-compiled"]
    print(f"merged {merged_n} places that two or more source sets priced")
    doc["localities"] = kept + rows
    doc["asOf"] = max([e.get("asOf") or "" for e in rows] + [doc.get("asOf", "")])
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"imported {len(rows)} rows · kept {len(kept)} hand-curated · dropped {len(dropped)} · flagged {len(flagged)}")
    for i, a, why in dropped[:40]:
        print(f"  DROPPED line {i}: {a} — {why}")
    for i, a, why in flagged[:40]:
        print(f"  FLAG    line {i}: {a} — {why}")
    cover = {e["ward"] for e in doc["localities"] if "ward" in e and "low" in e}
    print(f"wards with an apartment band: {len(cover)} of {len(wards)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
