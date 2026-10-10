"""
api/_google.py — server-side Google Places proxy shared by serve.py (local) and the Vercel functions.

Why a proxy: the Places key must never reach the browser. Every function degrades gracefully —
if the key is missing, wrong or Google is down, we return {"error": ...} and the app falls back to
OpenStreetMap data, so a report always renders.

Field masks are deliberately limited to id / name / location so Nearby Search stays in the
cheaper "Pro" SKU (the rating fields would move it to Enterprise).
"""
import os
import json
import time
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse, quote
from concurrent.futures import ThreadPoolExecutor

PLACES = "https://places.googleapis.com/v1"
CATS = {
    "hospital": ["hospital"],
    "school": ["school", "primary_school", "secondary_school"],
    "metro": ["subway_station", "train_station", "light_rail_station"],
    "market": ["supermarket", "shopping_mall", "grocery_store"],
    "bank": ["bank"],
    "park": ["park"],
    "fire": ["fire_station"],
    "police": ["police"],
}
HYD = {"latitude": 17.40, "longitude": 78.45}

_cache = {}
_lock = threading.Lock()
TTL = 900  # seconds; short session memo so re-opening a report doesn't re-bill the API


def tomtom_key():
    return os.environ.get("TOMTOM_API_KEY", "").strip()


_tt_cache = {}


def tomtom_suggest(q):
    """Type-ahead address / landmark search via TomTom's free tier. id encodes the coordinates, so no second call is needed."""
    key = tomtom_key()
    if not key:
        return {"error": "no_key", "items": []}
    ck = q.strip().lower()
    if ck in _tt_cache and time.time() - _tt_cache[ck][0] < 600:
        return _tt_cache[ck][1]
    from urllib.parse import quote as _q
    url = (f"https://api.tomtom.com/search/2/search/{_q(q)}.json?key={key}&typeahead=true&limit=7&countrySet=IN"
           f"&lat=17.40&lon=78.45&radius=60000&language=en-GB")
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=6) as r:
            data = json.loads(r.read())
    except Exception as e:
        return {"error": _err(e), "items": []}
    items = []
    for x in data.get("results", []):
        pos, addr, poi = x.get("position") or {}, x.get("address") or {}, x.get("poi") or {}
        if "lat" not in pos:
            continue
        full = addr.get("freeformAddress", "")
        items.append({"id": f"ll:{pos['lat']:.6f},{pos['lon']:.6f}", "main": poi.get("name") or full.split(",")[0], "sub": full})
    res = {"items": items, "provider": "tomtom"}
    _tt_cache[ck] = (time.time(), res)
    return res


def server_key():
    return os.environ.get("GOOGLE_PLACES_SERVER_KEY", "").strip()


def browser_key():
    return os.environ.get("GOOGLE_MAPS_BROWSER_KEY", "").strip()


def _post(url, body, mask=None, timeout=8):
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": server_key()}
    if mask:
        headers["X-Goog-FieldMask"] = mask
    req = Request(url, data=json.dumps(body).encode(), headers=headers)
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _get(url, mask, timeout=8):
    req = Request(url, headers={"X-Goog-Api-Key": server_key(), "X-Goog-FieldMask": mask})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _err(e):
    if isinstance(e, HTTPError):
        try:
            detail = json.loads(e.read().decode()).get("error", {}).get("message", "")
        except Exception:
            detail = ""
        return f"HTTP {e.code}: {detail}"[:300]
    return str(e)[:300]


def nearby_one(cat, lat, lon, radius=5000):
    body = {
        "includedTypes": CATS[cat], "maxResultCount": 15, "rankPreference": "DISTANCE",
        "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lon}, "radius": float(radius)}},
    }
    data = _post(f"{PLACES}/places:searchNearby", body, "places.id,places.displayName,places.location")
    out = []
    for p in data.get("places", []):
        loc = p.get("location", {})
        out.append([round(loc.get("latitude", 0), 5), round(loc.get("longitude", 0), 5),
                    (p.get("displayName") or {}).get("text", "")[:60]])
    return out


def nearby_all(lat, lon):
    if not server_key():
        return {"error": "no_key", "cats": {}}
    key = (round(lat, 3), round(lon, 3))
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < TTL:
            return hit[1]
    cats, errors = {}, {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {c: ex.submit(nearby_one, c, lat, lon) for c in CATS}
        for c, f in futs.items():
            try:
                cats[c] = f.result()
            except Exception as e:
                errors[c] = _err(e)
    res = {"cats": cats, "errors": errors, "source": "google"}
    if not cats:
        res["error"] = next(iter(errors.values()), "failed")
    else:
        with _lock:
            _cache[key] = (time.time(), res)
    return res


def suggest(q, token):
    if not server_key():
        return {"error": "no_key", "items": []}
    body = {"input": q, "sessionToken": token, "includedRegionCodes": ["in"],
            "locationBias": {"circle": {"center": HYD, "radius": 45000.0}}}
    try:
        data = _post(f"{PLACES}/places:autocomplete", body)
    except Exception as e:
        return {"error": _err(e), "items": []}
    items = []
    for s in data.get("suggestions", []):
        pp = s.get("placePrediction")
        if not pp:
            continue
        sf = pp.get("structuredFormat", {})
        items.append({"id": pp.get("placeId"),
                      "main": (sf.get("mainText") or {}).get("text") or (pp.get("text") or {}).get("text", ""),
                      "sub": (sf.get("secondaryText") or {}).get("text", "")})
    return {"items": items}


def place(pid, token):
    if not server_key():
        return {"error": "no_key"}
    try:
        d = _get(f"{PLACES}/places/{quote(pid)}?sessionToken={quote(token)}", "id,formattedAddress,location")
    except Exception as e:
        return {"error": _err(e)}
    loc = d.get("location", {})
    return {"lat": loc.get("latitude"), "lon": loc.get("longitude"), "address": d.get("formattedAddress", "")}


def health():
    res = {"tomtom_key_present": bool(tomtom_key()), "groq": bool(os.environ.get("GROQ_API_KEY", "").strip()),
           "browser_key_present": bool(browser_key()), "server_key_present": bool(server_key())}
    if tomtom_key() and not server_key():
        s = tomtom_suggest("Gachibowli")
        res["tomtom_search"] = {"ok": not s.get("error"), "error": s.get("error"), "results": len(s.get("items", []))}
    if server_key():
        try:
            n = nearby_one("hospital", 17.385, 78.486, 2000)
            res["places_nearby"] = {"ok": True, "results": len(n)}
        except Exception as e:
            res["places_nearby"] = {"ok": False, "error": _err(e)}
        s = suggest("Gachibowli", "health-check")
        res["places_autocomplete"] = {"ok": not s.get("error"), "error": s.get("error"), "results": len(s.get("items", []))}
    return res


def handle(path):
    """GET router shared by serve.py and Vercel. Returns (status, dict)."""
    u = urlparse(path)
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    route = u.path.rstrip("/")
    try:
        if route == "/api/config":
            return 200, {"mapsKey": browser_key(), "places": bool(server_key()), "suggest": bool(server_key() or tomtom_key())}
        if route == "/api/health":
            return 200, health()
        if route == "/api/places":
            return 200, nearby_all(float(q["lat"]), float(q["lon"]))
        if route == "/api/suggest":
            return 200, (suggest(q.get("q", ""), q.get("token", "t")) if server_key() else tomtom_suggest(q.get("q", "")))
        if route == "/api/place":
            if q["id"].startswith("ll:"):          # TomTom result: coordinates are in the id
                la, lo = q["id"][3:].split(",")
                return 200, {"lat": float(la), "lon": float(lo), "address": ""}
            return 200, place(q["id"], q.get("token", "t"))
    except KeyError as e:
        return 400, {"error": f"missing {e}"}
    except Exception as e:
        return 200, {"error": str(e)[:300]}
    return 404, {"error": "not found"}
