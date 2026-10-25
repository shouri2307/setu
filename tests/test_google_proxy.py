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
calls.clear(); os.environ["GOOGLE_PLACES_SERVER_KEY"] = "test-key-not-real"; g._geo_cache.clear()
def fake_geo(url, body, mask=None, timeout=8):
    calls.append(url); return {"places": [{"displayName": {"text": "Shri Ahobilam Matt"}, "formattedAddress": "2-2-20/B, Bagh Amberpet, Hyderabad", "location": {"latitude": 17.395, "longitude": 78.515}}]}
g._post = fake_geo
r = g.geocode("Shri Ahobilam Matt, 2-2-20/B, Bagh Amberpet, Hyderabad, Telangana 500013"); check(r.get("lat") == 17.395 and len(calls) == 1, "an address is turned into a point with one request")
g.geocode("shri ahobilam matt, 2-2-20/b, bagh amberpet, hyderabad, telangana 500013"); check(len(calls) == 1, "the same address is cached")
g.geocode("ab"); check(len(calls) == 1 and g.geocode("ab")["error"] == "too_short", "very short text is never sent")
g._post = lambda *a, **k: {"places": [{"location": {"latitude": 28.6, "longitude": 77.2}}]}; g._geo_cache.clear(); check(g.geocode("somewhere far")["error"] == "outside_region", "a result outside the Hyderabad region is refused")
check(g.resolve("https://evil.example.com/x")["error"] == "not_a_google_link" and g.resolve("file:///etc/passwd")["error"] == "not_a_google_link" and g.resolve("https://google.com.evil.com/x")["error"] == "not_a_google_link", "the link resolver refuses anything that is not a Google link host")
check(g._link_ok("https://maps.app.goo.gl/abc") and g._link_ok("https://www.google.com/maps/place/x") and not g._link_ok("http://169.254.169.254/latest"), "only Google hosts pass the link check")
sys.exit(1 if bad else 0)
