"""Step 1 validation: the state fire-station list against OpenStreetMap, at 10 representative places. OSM is NOT treated as ground truth: both lists can be wrong, and every disagreement is recorded.
Also checks what the source's remarks ("Moved", "Correct"...) mean by seeing whether such points sit on OSM stations.
OSM is fetched live from Overpass (one request; fetch time recorded).   .venv/Scripts/python research/v8/validate_fire.py"""
import json, math, time, collections, datetime, sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
import requests
ROOT = Path(__file__).resolve().parent.parent.parent
H = {"User-Agent": "SETU-sideproject/0.1 (validation)"}
BBOX = (17.15, 78.10, 17.75, 78.80)   # south, west, north, east
def overpass():
    q = f'[out:json][timeout:90];(nwr["amenity"="fire_station"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}););out center tags;'
    for u in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter"):
        try:
            r = requests.post(u, data={"data": q}, headers=H, timeout=120)
            if r.status_code == 200 and r.text.startswith("{"): return r.json(), u
        except Exception as e: print("overpass", u, "failed:", str(e)[:60])
    raise SystemExit("no Overpass server answered")
osm_j, host = overpass()
osm = []
for e in osm_j["elements"]:
    la, lo = (e.get("lat"), e.get("lon")) if e["type"] == "node" else (e.get("center", {}).get("lat"), e.get("center", {}).get("lon"))
    if la is None: continue
    t = e.get("tags", {}); osm.append((la, lo, t.get("name") or t.get("name:en") or "(unnamed)", e["type"] + "/" + str(e["id"])))
print(f"OSM fire stations in the box: {len(osm)} (host {host}; OSM data timestamp {osm_j.get('osm3s', {}).get('timestamp_osm_base')}; fetched {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')})")
G = json.load(open(ROOT / "web/data/fire.json"))["stations"]
geo = json.load(open(ROOT / "web/data/geo.json"))["poi"].get("fire", [])   # the app's merged list (OSM + Overture + ...), for comparison only
def hav(a, b, c, d):
    p = math.pi / 180; x = (d - b) * p * math.cos((a + c) / 2 * p); y = (c - a) * p; return 6371000 * math.hypot(x, y)
def nearest(pts, la, lo, f=lambda p: True):
    c = [(hav(la, lo, p[0], p[1]), p) for p in pts if f(p)]; return min(c, key=lambda t: t[0]) if c else (None, None)
existing = lambda p: p[4] == "Existing"
PLACES = {"Secunderabad (Hussain Sagar side)": (17.4399, 78.4983), "Gachibowli": (17.4401, 78.3489), "Charminar": (17.3616, 78.4747), "Kukatpally": (17.4948, 78.3996), "LB Nagar": (17.3457, 78.5522),
          "Uppal": (17.4058, 78.5591), "Shamshabad": (17.2403, 78.4294), "Medchal": (17.63, 78.48), "Miyapur": (17.4969, 78.3548), "Banjara Hills": (17.4126, 78.4482)}
rows = []; agree = 0
print("\n| place | nearest state-list station that is 'Existing' | nearest OSM station | same station? (within 500 m of each other) | nearest 'Proposed' |\n|---|---|---|---|---|")
for n, (la, lo) in PLACES.items():
    dg, g = nearest(G, la, lo, existing); do, o = nearest(osm, la, lo); dp, p = nearest(G, la, lo, lambda r: r[4] == "Proposed")
    same = g and o and hav(g[0], g[1], o[0], o[1]) <= 500
    agree += bool(same)
    gtxt = f"{g[2]} ({g[5]}) {dg/1000:.1f} km" if g else "none"; otxt = f"{o[2]} {do/1000:.1f} km" if o else "none"
    gap = f"{hav(g[0], g[1], o[0], o[1]):.0f} m apart" if g and o else ""
    print(f"| {n} | {gtxt} | {otxt} | {'yes' if same else 'NO ' + gap} | {p[2] + ' ' + format(dp/1000, '.1f') + ' km' if p else 'none'} |"); rows.append((n, dg, do, bool(same)))
print(f"\nnearest-station agreement: {agree} of {len(PLACES)} places")
print("\n== Coverage both ways (are the two lists describing the same stations?)")
ex = [p for p in G if existing(p)]
for lab, sel in (("all 32 Existing", lambda p: True), ("remark Moved (24)", lambda p: p[5] == "Moved"), ("remark Correct (1)", lambda p: p[5] == "Correct"), ("remark '... not found accurate' (7)", lambda p: "not found accurate" in p[5])):
    s = [p for p in ex if sel(p)]; d = [nearest(osm, p[0], p[1])[0] for p in s]
    print(f"  state-list {lab}: {len(s)} stations | OSM station within 300 m: {sum(1 for x in d if x is not None and x <= 300)} | within 1 km: {sum(1 for x in d if x is not None and x <= 1000)} | median distance to nearest OSM station: {sorted(d)[len(d)//2]:.0f} m" if d else f"  {lab}: none")
pr = [p for p in G if p[4] == "Proposed"]; d = [nearest(osm, p[0], p[1])[0] for p in pr]; print(f"  state-list Proposed (39): OSM station within 300 m: {sum(1 for x in d if x <= 300)} (a proposed site that already has an OSM station would be notable)")
inside = [o for o in osm if 17.26 <= o[0] <= 17.59 and 78.24 <= o[1] <= 78.65]
d = [nearest(ex, o[0], o[1])[0] for o in inside]
print(f"  OSM stations inside the study box: {len(inside)} | with a state-list 'Existing' station within 300 m: {sum(1 for x in d if x <= 300)} | within 1 km: {sum(1 for x in d if x <= 1000)}")
print("  OSM stations with NO state-list Existing station within 1 km:", [(o[2], round(o[0], 4), round(o[1], 4)) for o, x in zip(inside, d) if x > 1000][:12])
mg = [o for o in geo if 17.26 <= o[0] <= 17.59 and 78.24 <= o[1] <= 78.65]; print(f"  the app's merged list (OSM + Overture + others) has {len(mg)} fire stations in the box")
json.dump({"fetched": datetime.datetime.now().isoformat(timespec="minutes"), "osm_count": len(osm), "agreement": [agree, len(PLACES)], "places": rows}, open(ROOT / "research/v8/validate_fire.json", "w"), indent=1)
