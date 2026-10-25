"""Google Maps links: understand the newer 'search?api=1&query=<address text>' links, 'place/<name>' links without coordinates, and real short links (resolved server-side, no Google API request)."""
from pathlib import Path
def patch(path, pairs):
    p = Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, f"{path}: {s.count(old)} x {old[:80]!r}"; s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")

# ---------------- server: geocode (one request) and short-link resolver (zero Google requests) ----------------
patch("api/_google.py", [
("def place(pid, token):", '''_geo_cache = {}
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
    body = {"textQuery": q, "includedRegionCode": "in", "pageSize": 1,
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


def place(pid, token):'''),
('"places": bool(server_key()) and nearby_enabled(), "suggest": bool(server_key() or tomtom_key())}',
 '"places": bool(server_key()) and nearby_enabled(), "suggest": bool(server_key() or tomtom_key()), "geocode": bool(server_key())}'),
('        if route == "/api/place":', '''        if route == "/api/geocode":
            return 200, geocode(q.get("q", ""))
        if route == "/api/resolve":
            return 200, resolve(q.get("url", ""))
        if route == "/api/place":'''),
])
for name in ("geocode", "resolve"):
    src = Path("api/suggest.py").read_text(encoding="utf-8").replace("/api/suggest", f"/api/{name}")
    Path(f"api/{name}.py").write_text(src, encoding="utf-8")

# ---------------- engine: a testable link parser ----------------
patch("web/platform/engine.js", [
("  // ---------- evidence-quality registry helpers ----------", r'''  // ---------- pasted Google Maps links ----------
  // Returns {lat, lon} when the link carries coordinates; {text} when it carries an address or place name (to be looked up); {short, url} for a short link; null when it is not a Google Maps link.
  function parseMapsLink(q) {
    q = String(q || '').trim();
    if (!/(google\.[a-z.]+\/maps|maps\.google|goo\.gl|maps\.app|g\.co\/kgs)/i.test(q)) return null;
    const num = (re) => { const m = q.match(re); return m ? { lat: +m[1], lon: +m[2] } : null; };
    const ll = num(/!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)/) || num(/[?&](?:q|ll|query|destination|center)=(-?\d+\.\d+)(?:,|%2C)\s*(-?\d+\.\d+)/i) || num(/@(-?\d+\.\d+),(-?\d+\.\d+)/);
    if (ll) return ll;
    const dec = s => { try { return decodeURIComponent(s.replace(/\+/g, ' ')).replace(/\s+/g, ' ').trim(); } catch (e) { return s.replace(/\+/g, ' ').trim(); } };
    const tq = q.match(/[?&](?:query|q|destination)=([^&#]+)/i);
    if (tq && dec(tq[1]).length >= 3) return { text: dec(tq[1]) };
    const pl = q.match(/\/maps\/place\/([^/@?#]+)/i);
    if (pl && dec(pl[1]).length >= 3) return { text: dec(pl[1]) };
    if (/(goo\.gl|maps\.app|g\.co\/kgs)/i.test(q)) return { short: true, url: (q.match(/https?:\/\/\S+/) || [q])[0] };
    return { short: true, url: '' };
  }

  // ---------- evidence-quality registry helpers ----------'''),
("return { load, report, evidence, checklist, HIGH,", "return { load, report, evidence, checklist, HIGH, parseMapsLink,"),
])

# ---------------- app: use it ----------------
patch("web/platform/app.js", [
('''function parseMapsLink(q) {   // full Google Maps URLs carry the pin's coordinates; short links cannot be resolved in the browser
  if (!/(google\\.[a-z.]+\\/maps|maps\\.google|goo\\.gl|maps\\.app)/i.test(q)) return null;
  const pick = re => { const m = q.match(re); return m ? { lat: +m[1], lon: +m[2] } : null; };
  return pick(/!3d(-?\\d+\\.\\d+)!4d(-?\\d+\\.\\d+)/) || pick(/[?&](?:q|ll|query|destination|center)=(-?\\d+\\.\\d+)(?:,|%2C)(-?\\d+\\.\\d+)/i) || pick(/@(-?\\d+\\.\\d+),(-?\\d+\\.\\d+)/) || { short: true };
}''', '''// a pasted Google Maps link is understood three ways: coordinates in it, an address in it (looked up), or a short link (the server follows the redirect)
async function searchText(text) {
  toast('Finding that address…', 6000);
  let hit = null;
  if (S.cfg.geocode) { const j = await api(`/api/geocode?q=${encodeURIComponent(text)}`, 8000).catch(() => null); if (j && j.lat != null && inRegion(j.lat, j.lon)) hit = { lat: j.lat, lon: j.lon, label: j.name || text.split(',')[0], address: j.address }; }
  if (!hit) { const on = await onlineSearch(text); if (on.length) hit = { lat: on[0].lat, lon: on[0].lon, label: text.split(',')[0], address: on[0].sub }; }
  if (!hit) return toast('Could not place that address on the map. Try the locality name, or click the map.', 6000);
  $('toast').classList.remove('show'); $('q').value = text.split(',').slice(0, 2).join(','); S.address = hit.address || ''; return setPin(hit.lat, hit.lon, hit.label);
}
async function handleMapsLink(link) {
  if (link.lat != null) return setPin(link.lat, link.lon, 'Pin from Google Maps link');
  if (link.text) return searchText(link.text);
  if (link.short && link.url) {
    toast('Opening that short link…', 6000);
    const j = await api(`/api/resolve?url=${encodeURIComponent(link.url)}`, 9000).catch(() => null);
    const l2 = j && j.url ? SETUE.parseMapsLink(j.url) : null;
    if (l2 && !l2.short) return handleMapsLink(l2);
  }
  toast('Could not read that Google link. Paste the full address from your browser bar, or search the place name.', 6500);
}'''),
('''  const link = parseMapsLink(q);
  if (link && link.short) return toast('That is a short Google link. Open it in your browser first, then paste the full address-bar URL here.', 6000);
  if (link) return setPin(link.lat, link.lon, 'Pin from Google Maps link');''', '''  const link = SETUE.parseMapsLink(q);
  if (link) return handleMapsLink(link);'''),
])

# ---------------- tests ----------------
Path("tests/test_google_proxy.py").write_text(Path("tests/test_google_proxy.py").read_text(encoding="utf-8").replace("sys.exit(1 if bad else 0)", '''calls.clear(); os.environ["GOOGLE_PLACES_SERVER_KEY"] = "test-key-not-real"; g._geo_cache.clear()
def fake_geo(url, body, mask=None, timeout=8):
    calls.append(url); return {"places": [{"displayName": {"text": "Shri Ahobilam Matt"}, "formattedAddress": "2-2-20/B, Bagh Amberpet, Hyderabad", "location": {"latitude": 17.395, "longitude": 78.515}}]}
g._post = fake_geo
r = g.geocode("Shri Ahobilam Matt, 2-2-20/B, Bagh Amberpet, Hyderabad, Telangana 500013"); check(r.get("lat") == 17.395 and len(calls) == 1, "an address is turned into a point with one request")
g.geocode("shri ahobilam matt, 2-2-20/b, bagh amberpet, hyderabad, telangana 500013"); check(len(calls) == 1, "the same address is cached")
g.geocode("ab"); check(len(calls) == 1 and g.geocode("ab")["error"] == "too_short", "very short text is never sent")
g._post = lambda *a, **k: {"places": [{"location": {"latitude": 28.6, "longitude": 77.2}}]}; g._geo_cache.clear(); check(g.geocode("somewhere far")["error"] == "outside_region", "a result outside the Hyderabad region is refused")
check(g.resolve("https://evil.example.com/x")["error"] == "not_a_google_link" and g.resolve("file:///etc/passwd")["error"] == "not_a_google_link" and g.resolve("https://google.com.evil.com/x")["error"] == "not_a_google_link", "the link resolver refuses anything that is not a Google link host")
check(g._link_ok("https://maps.app.goo.gl/abc") and g._link_ok("https://www.google.com/maps/place/x") and not g._link_ok("http://169.254.169.254/latest"), "only Google hosts pass the link check")
sys.exit(1 if bad else 0)'''), encoding="utf-8")
print("maps link patched")
