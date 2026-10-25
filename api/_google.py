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


def nearby_enabled():
    """Nearby Search costs one request per category per pin (8 per report), so it is OFF unless GOOGLE_PLACES_NEARBY=1. Address search stays on."""
    return os.environ.get("GOOGLE_PLACES_NEARBY", "").strip() == "1"


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
    if not nearby_enabled():
        return {"error": "nearby_disabled", "cats": {}}   # no Google request is made; the app uses its OpenStreetMap / Overture places
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


_sug_cache = {}


def suggest(q, token):
    if not server_key():
        return {"error": "no_key", "items": []}
    q = (q or "").strip()
    if len(q) < 3:
        return {"items": []}                       # never bill a request for one or two letters
    ck = q.lower()
    with _lock:
        hit = _sug_cache.get(ck)
        if hit and time.time() - hit[0] < TTL:
            return hit[1]                          # the same text again costs nothing
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
    res = {"items": items}
    with _lock:
        if len(_sug_cache) > 500:
            _sug_cache.clear()
        _sug_cache[ck] = (time.time(), res)
    return res


_geo_cache = {}
HYD_BOX = (17.0, 18.0, 77.9, 79.0)   # south, north, west, east: results outside the Hyderabad region are dropped


def geocode(q):
    """Address text -> one point, with ONE Places Text Search request (cached). Used when a pasted Google Maps link carries an address and no coordinates."""
    if not server_key():
        return {"error": "no_key"}
    q = (q or "").strip()[:200]
    if len(q) < 3:
        return {"error": "too_short"}
    ck = q.lower()
    with _lock:
        hit = _geo_cache.get(ck)
        if hit and time.time() - hit[0] < TTL:
            return hit[1]
    body = {"textQuery": q, "regionCode": "IN", "pageSize": 1,
            "locationBias": {"circle": {"center": HYD, "radius": 45000.0}}}
    try:
        data = _post(f"{PLACES}/places:searchText", body, "places.displayName,places.formattedAddress,places.location")
    except Exception as e:
        return {"error": _err(e)}
    ps = data.get("places") or []
    if not ps:
        res = {"error": "not_found"}
    else:
        loc = ps[0].get("location", {}); la, lo = loc.get("latitude"), loc.get("longitude")
        if la is None or not (HYD_BOX[0] <= la <= HYD_BOX[1] and HYD_BOX[2] <= lo <= HYD_BOX[3]):
            res = {"error": "outside_region"}
        else:
            res = {"lat": la, "lon": lo, "address": ps[0].get("formattedAddress", ""), "name": (ps[0].get("displayName") or {}).get("text", "")}
    with _lock:
        if len(_geo_cache) > 300:
            _geo_cache.clear()
        _geo_cache[ck] = (time.time(), res)
    return res


# Short Google links (maps.app.goo.gl/..., goo.gl/maps/...) cannot be opened from the browser (no CORS). The server follows the redirect itself.
# This uses no Google API and no key. It will only ever contact Google's own link hosts, and refuses to follow a redirect anywhere else.
LINK_HOSTS = ("maps.app.goo.gl", "goo.gl", "g.co", "google.com", "maps.google.com")


def _link_ok(url):
    try:
        u = urlparse(url)
    except Exception:
        return False
    h = (u.hostname or "").lower()
    return u.scheme in ("http", "https") and any(h == x or h.endswith("." + x) for x in LINK_HOSTS)


def resolve(url):
    from urllib.request import HTTPRedirectHandler, build_opener
    if not _link_ok(url):
        return {"error": "not_a_google_link"}

    class Guard(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not _link_ok(newurl):
                raise HTTPError(newurl, 403, "redirect to a non-Google host refused", headers, fp)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    try:
        op = build_opener(Guard)
        with op.open(Request(url, headers={"User-Agent": "Mozilla/5.0 SETU-link-resolver"}), timeout=7) as r:
            final = r.geturl()
    except Exception as e:
        return {"error": _err(e)}
    return {"url": final}


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
        if nearby_enabled():
            try:
                n = nearby_one("hospital", 17.385, 78.486, 2000)
                res["places_nearby"] = {"ok": True, "results": len(n)}
            except Exception as e:
                res["places_nearby"] = {"ok": False, "error": _err(e)}
        else:
            res["places_nearby"] = {"ok": True, "results": 0, "note": "off (GOOGLE_PLACES_NEARBY not set): saves requests"}
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
            return 200, {"mapsKey": browser_key(), "places": bool(server_key()) and nearby_enabled(), "suggest": bool(server_key() or tomtom_key()), "geocode": bool(server_key())}
        if route == "/api/health":
            return 200, health()
        if route == "/api/places":
            return 200, nearby_all(float(q["lat"]), float(q["lon"]))
        if route == "/api/suggest":
            return 200, (suggest(q.get("q", ""), q.get("token", "t")) if server_key() else tomtom_suggest(q.get("q", "")))
        if route == "/api/geocode":
            return 200, geocode(q.get("q", ""))
        if route == "/api/resolve":
            return 200, resolve(q.get("url", ""))
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
