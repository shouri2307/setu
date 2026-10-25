"""Google proxy spend guards. No network: _post/_get are replaced by counters.   python tests/test_google_proxy.py"""
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
