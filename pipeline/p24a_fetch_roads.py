"""p24a_fetch_roads.py — main and collector roads (motorway..unclassified, no residential streets) for the Hyderabad study box from OpenStreetMap (Overpass), tile by tile,
cached in research/osm_cache/roads_full/. A tile that times out is split into four and retried (down to ~1 km), so dense city tiles still finish.
Run in the background: .venv/Scripts/python pipeline/p24a_fetch_roads.py"""
import json, time, requests
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research" / "osm_cache" / "roads_full"; OUT.mkdir(parents=True, exist_ok=True)
H = {"User-Agent": "SETU-sideproject/0.1 (flood and location research)"}
EP = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
W0, S0, E1, N1, T = 78.20, 17.22, 78.70, 17.62, 0.06
HW = "motorway|trunk|primary|secondary|tertiary|unclassified|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link"   # residential streets are left out: the public servers time out on them
tick = [0]
def fetch(s, w, n, e, depth=0):
    f = OUT / f"t_{s:.4f}_{w:.4f}_{n:.4f}_{e:.4f}.json"
    if f.exists() and f.stat().st_size > 50: return True
    q = f'[out:json][timeout:120];way["highway"~"^({HW})$"]({s},{w},{n},{e});out geom tags;'
    for a in range(3):
        ep = EP[(tick[0] + a) % len(EP)]; tick[0] += 1
        try:
            r = requests.post(ep, data={"data": q}, headers=H, timeout=140)
            if r.status_code == 200 and r.text.startswith("{"):
                els = r.json().get("elements", []); f.write_text(json.dumps(els, separators=(",", ":")), encoding="utf-8")
                print(f"ok {s:.3f},{w:.3f} size {n-s:.3f} deg: {len(els)} ways {len(r.content)//1000} KB via {ep.split('/')[2]}", flush=True); return True
            print("  retry", s, w, r.status_code, flush=True)
        except Exception as ex: print("  retry", s, w, str(ex)[:50], flush=True)
        time.sleep(5 + 5 * a)
    if (n - s) > 0.012:                                   # split into 4 and retry
        ms, mw = (s + n) / 2, (w + e) / 2; print(f"  splitting {s:.3f},{w:.3f} ({n-s:.3f} deg)", flush=True)
        ok = True
        for (a, b, c, d) in ((s, w, ms, mw), (s, mw, ms, e), (ms, w, n, mw), (ms, mw, n, e)): ok = fetch(a, b, c, d, depth + 1) and ok
        if ok: f.write_text("[]")                            # marker: covered by children
        return ok
    print("  GAVE UP", s, w, flush=True); return False
y_list = []; y = S0
while y < N1: y_list.append(y); y += T
x_list = []; x = W0
while x < E1: x_list.append(x); x += T
for i, x in enumerate(x_list):
    for y in y_list: fetch(round(y, 4), round(x, 4), round(min(y + T, N1), 4), round(min(x + T, E1), 4))
    print(f"column {i+1}/{len(x_list)} done", flush=True); time.sleep(1)
print("done", flush=True)
