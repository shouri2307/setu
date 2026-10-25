"""Keep Google usage to the bare minimum: address search only. Nearby search (8 requests per pin) becomes opt-in; short queries are never sent; repeated queries are cached."""
from pathlib import Path
p = Path("api/_google.py"); s = p.read_text(encoding="utf-8")
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]; s = s.replace(old, new)

rep("def server_key():", '''def nearby_enabled():
    """Nearby Search costs one request per category per pin (8 per report), so it is OFF unless GOOGLE_PLACES_NEARBY=1. Address search stays on."""
    return os.environ.get("GOOGLE_PLACES_NEARBY", "").strip() == "1"


def server_key():''')
rep('''    if not server_key():
        return {"error": "no_key", "cats": {}}
    key = (round(lat, 3), round(lon, 3))''', '''    if not server_key():
        return {"error": "no_key", "cats": {}}
    if not nearby_enabled():
        return {"error": "nearby_disabled", "cats": {}}   # no Google request is made; the app uses its OpenStreetMap / Overture places
    key = (round(lat, 3), round(lon, 3))''')
rep('''def suggest(q, token):
    if not server_key():
        return {"error": "no_key", "items": []}
    body =''', '''_sug_cache = {}


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
    body =''')
rep('''                      "sub": (sf.get("secondaryText") or {}).get("text", "")})
    return {"items": items}''', '''                      "sub": (sf.get("secondaryText") or {}).get("text", "")})
    res = {"items": items}
    with _lock:
        if len(_sug_cache) > 500:
            _sug_cache.clear()
        _sug_cache[ck] = (time.time(), res)
    return res''')
rep('''    if server_key():
        try:
            n = nearby_one("hospital", 17.385, 78.486, 2000)
            res["places_nearby"] = {"ok": True, "results": len(n)}
        except Exception as e:
            res["places_nearby"] = {"ok": False, "error": _err(e)}
        s = suggest("Gachibowli", "health-check")''', '''    if server_key():
        if nearby_enabled():
            try:
                n = nearby_one("hospital", 17.385, 78.486, 2000)
                res["places_nearby"] = {"ok": True, "results": len(n)}
            except Exception as e:
                res["places_nearby"] = {"ok": False, "error": _err(e)}
        else:
            res["places_nearby"] = {"ok": True, "results": 0, "note": "off (GOOGLE_PLACES_NEARBY not set): saves requests"}
        s = suggest("Gachibowli", "health-check")''')
rep('"places": bool(server_key()), "suggest"', '"places": bool(server_key()) and nearby_enabled(), "suggest"')
p.write_text(s, encoding="utf-8")

Path("tests/test_google_proxy.py").write_text('''"""Google proxy spend guards. No network: _post/_get are replaced by counters.   python tests/test_google_proxy.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
os.environ["GOOGLE_PLACES_SERVER_KEY"] = "test-key-not-real"; os.environ.pop("GOOGLE_PLACES_NEARBY", None)
import _google as g
calls = []
def fake_post(url, body, mask=None, timeout=8):
    calls.append(url)
    return {"suggestions": [{"placePrediction": {"placeId": "P1", "structuredFormat": {"mainText": {"text": "Gachibowli"}, "secondaryText": {"text": "Hyderabad"}}}}]} if "autocomplete" in url else {"places": []}
g._post = fake_post; bad = 0
def check(c, m):
    global bad
    print(("ok   " if c else "FAIL ") + m); bad += (not c)
r = g.nearby_all(17.44, 78.35); check(r.get("error") == "nearby_disabled" and not calls, "nearby search makes no Google request unless GOOGLE_PLACES_NEARBY=1")
check(g.handle("/api/config")[1]["places"] is False and g.handle("/api/config")[1]["suggest"] is True, "config: nearby off, address search on")
g.suggest("ga", "t"); g.suggest("  g ", "t"); g.suggest("", "t"); check(not calls, "queries shorter than 3 letters are never sent")
g.suggest("Gachibowli", "t1"); n1 = len(calls); g.suggest("gachibowli", "t2"); g.suggest(" Gachibowli ", "t3"); check(n1 == 1 and len(calls) == 1, "the same query is billed once, then served from the cache")
os.environ["GOOGLE_PLACES_NEARBY"] = "1"; g._cache.clear(); g.nearby_all(17.44, 78.35); check(len(calls) == 1 + len(g.CATS), "with GOOGLE_PLACES_NEARBY=1 nearby search is one request per category (opt-in)")
os.environ.pop("GOOGLE_PLACES_SERVER_KEY"); calls.clear(); check(g.suggest("Gachibowli", "t")["error"] == "no_key" and not calls, "no key: no request and a clean error")
sys.exit(1 if bad else 0)
''', encoding="utf-8")
print("google proxy patched")
