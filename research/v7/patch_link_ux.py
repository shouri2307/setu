"""Fixes from the live screenshot: wrong 'survey number entered' wording when none was entered; the suggestion dropdown opening for a pasted Google link; a readable label for pins from Google links."""
from pathlib import Path
def patch(path, pairs):
    p = Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, f"{path}: {s.count(old)} x {old[:80]!r}"; s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")

patch("web/platform/engine.js", [
    # identity carries the reason, so the UI can say what actually happened
    ("      : { status: 'pending', label: 'Not matched yet'", "      : { status: 'pending', reason: '', label: 'Not matched yet'"),
    ("const identity = pc ? { status: pc.status, label: PARCEL_LABEL[pc.status], text: pc.text,", "const identity = pc ? { status: pc.status, reason: pc.reason, label: PARCEL_LABEL[pc.status], text: pc.text,"),
    # a place link with coordinates also keeps the place name for the label
    ("    if (ll) return ll;\n    const dec =", "    const dec0 = s => { try { return decodeURIComponent(s.replace(/\\+/g, ' ')).replace(/\\s+/g, ' ').trim(); } catch (e) { return s.replace(/\\+/g, ' ').trim(); } };\n    if (ll) { const pn = q.match(/\\/maps\\/place\\/([^/@?#]+)/i); if (pn && dec0(pn[1]).length >= 3 && !/^-?\\d/.test(dec0(pn[1]))) ll.name = dec0(pn[1]); return ll; }\n    const dec ="),
])
patch("web/platform/view.js", [
    ("id.status === 'none' ? 'The pin does not match the survey number you entered'", "id.status === 'none' ? (MISMATCH.has(id.reason) ? 'The pin does not match the survey number you entered' : id.reason === 'on-feature' ? 'The pin is on a road, canal or tank, not on a plot' : 'The pin is not on a mapped survey plot')"),
    ("id.status === 'none' ? 'Does not match the survey number entered'", "id.status === 'none' ? (MISMATCH.has(id.reason) ? 'Does not match the survey number entered' : id.reason === 'on-feature' ? 'On a road, canal or tank, not a plot' : 'Not on a mapped survey plot')"),
    ("  const label = r => r.label || '';", "  const MISMATCH = new Set(['number-mismatch', 'neighbour', 'village-mismatch']);   // only these mean \"your number does not fit the pin\"\n  const label = r => r.label || '';"),
])
patch("web/platform/app.js", [
    ("async function updateSuggestions(q) {\n  const el = $('sug');\n", "async function updateSuggestions(q) {\n  const el = $('sug');\n  if (SETUE.parseMapsLink(q)) { el.classList.remove('show'); sugItems = []; return; }   // a pasted Google link is not search text: no \"no exact match\" box\n"),
    ("  if (link.lat != null) return setPin(link.lat, link.lon, 'Pin from Google Maps link');", "  if (link.lat != null) { $('sug').classList.remove('show'); if (link.name) $('q').value = link.name; return setPin(link.lat, link.lon, link.name || 'Pin from Google Maps link'); }"),
])
# tests
p = Path("tests/engine.test.js"); s = p.read_text(encoding="utf-8"); anchor = "  // ---- live APIs (optional) ----"; assert s.count(anchor) == 1
s = s.replace(anchor, r"""  // ---- wording must say what actually happened ----
  {
    const SBx = r => ({ r, label: '', cust: {}, agent: {}, claim: { peril: 'rain_vehicle', date: '', amount: '', out: null, busy: false }, ai: {}, fc: null, air: { aqi: 80, band: 'x' }, access: {}, terrain: { relief: 0 }, line: 'motor', PERILS: PER, open: {}, pref: { survey: '', village: '', plot: '', layout: '', doc: '' } });
    const r = await E.report(17.4401, 78.3489), mk = (la, lo, w) => ({ ok: true, outsideBox: false, parcels: w });
    const sq = (la, lo, h) => { const a = h / 110540, b = h / (111320 * Math.cos(la * Math.PI / 180)); return [[la - a, lo - b], [la - a, lo + b], [la + a, lo + b], [la + a, lo - b], [la - a, lo - a]]; };
    const bbox = ring => [Math.min(...ring.map(p => p[0])), Math.min(...ring.map(p => p[1])), Math.max(...ring.map(p => p[0])), Math.max(...ring.map(p => p[1]))];
    const P = (la, lo, n) => { const ring = sq(la, lo, 40); return { n, v: 'X', m: 'Y', code: 0, rem: '', rings: [ring], _b: bbox(ring) }; };
    // a pin in a gap between plots, with NO survey number typed
    E.setParcel(r, mk(0, 0, [P(17.4401 + 0.0009, 78.3489, '1'), P(17.4401 - 0.0009, 78.3489, '2')]), {});
    let d = View.dock(SBx(r)), id = View.identity(r, SBx(r));
    ok(r.ev.identity.status === 'none' && r.ev.identity.reason === 'unmapped', 'a pin in a gap between plots is "no match / unmapped"');
    ok(!/survey number (you )?entered/i.test(d.replace(/<[^>]+>/g, ' ')) && /Not on a mapped survey plot/.test(d), 'the map card does NOT claim a survey number was entered when none was');
    ok(!/does not match the survey number you entered/i.test(id) && /not on a mapped survey plot/i.test(id), 'the identity box says the pin is not on a mapped plot, not that a number mismatched');
    // the same status with a typed number that does not fit really is a mismatch
    E.setParcel(r, mk(0, 0, [P(17.4401, 78.3489, '7')]), { survey: '99' }); d = View.dock(SBx(r));
    ok(r.ev.identity.reason === 'number-mismatch' && /Does not match the survey number entered/.test(d), 'with a typed number that does not fit, the card says so');
    const pp = E.parseMapsLink('https://www.google.com/maps/place/Shri+Ahobilam+Matt/@17.4022667,78.5197988,17z/data=!3m1!4b1!4m6!3m5!1s0x0:0x0!8m2!3d17.4022667!4d78.5197988');
    ok(pp && pp.lat === 17.4022667 && pp.name === 'Shri Ahobilam Matt', 'a place link keeps its readable name next to the coordinates (used as the label)');
    ok(E.parseMapsLink('https://www.google.com/maps/@17.44,78.35,15z').name === undefined, 'a plain map link has no place name');
  }
""" + anchor)
p.write_text(s, encoding="utf-8")
print("patched")
