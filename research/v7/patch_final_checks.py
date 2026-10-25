"""Pre-commit hardening: reword 'Looks fine' (it implied more certainty than a check supports), make a geometric overlap a 'look into' item not a 'needs attention' one, and add the guard tests."""
from pathlib import Path
def patch(path, pairs):
    p = Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, f"{path}: {s.count(old)} x {old[:70]!r}"; s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")

patch("web/platform/view.js", [
    ("good: { word: 'Looks fine', k: 'ok', glyph: '✓' }", "good: { word: 'No issue found', k: 'ok', glyph: '✓' }"),
    ("looks fine / could not be checked", "no issue found / could not be checked"),
    ("<b>${nG}</b> look fine</span>", "<b>${nG}</b> no issue found</span>"),
    ("Nothing rated fine yet.", "No check has run clean yet."),
])
patch("web/platform/reports.js", [
    ("<b>Needs attention / look into / looks fine / couldn't check.</b> Every finding carries one of these four words and an icon.", "<b>Needs attention / look into / no issue found / couldn't check.</b> Every finding carries one of these four words and an icon. \"No issue found\" means the check ran and found nothing in the data we have; it is never a clearance."),
    ("<span class=\"n-ok\"><b>${n.g}</b> fine</span>", "<span class=\"n-ok\"><b>${n.g}</b> no issue found</span>"),
])
patch("web/platform/engine.js", [
    ("level: parts.length ? 'concern' : 'info', kind: 'official', conf: 'low',\n        source: 'TGRAC cadastral outline tested against", "level: parts.length ? 'watch' : 'info', kind: 'official', conf: 'low',\n        source: 'TGRAC cadastral outline tested against"),
    ("Two map layers disagree about the same ground. That is a reason to check, not a legal finding; either outline can be off by metres", "Two map layers disagree about the same ground. That is a reason to investigate, not proof of encroachment or of any legal restriction; either outline can be off by metres"),
])
patch("tests/engine.test.js", [
    ("m('look fine') !==", "m('no issue found') !=="),
    ("ok(f.level === 'concern' && /disappeared/.test(f.value) && f.scope === 'parcel' && /not a legal finding/.test(f.note), 'overlap finding: a matched outline over a disappeared tank is a concern, labelled parcel-scope and \"not a legal finding\"');",
     "ok(f.level === 'watch' && /disappeared/.test(f.value) && f.scope === 'parcel' && /not proof of encroachment or of any legal restriction/.test(f.note), 'overlap finding: a matched outline over a disappeared tank is a look-into item (never proof), labelled parcel-scope');"),
])
# guard tests: a village serial can never pose as a survey number; restriction wording; 'No issue found' is never a clearance
Path("tests/_guard_block.js").write_text("""
  // ---- guards added before release ----
  {
    const p31 = fs.readFileSync(path.join(__dirname, '..', 'pipeline', 'p31_parcels.py'), 'utf8'), eng = fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8');
    ok(!/CAD_FIELDS\\s*=\\s*"[^"]*\\bSNo\\b/.test(p31), 'the parcel download never requests SNo (a village serial number, not a survey number)');
    ok(!/\\bSNo\\b/.test(eng.replace(/\\/\\/.*$/gm, '')), 'the engine never reads SNo');
    const t0 = JSON.parse(fs.readFileSync(path.join(WEB, 'data', 'parcels', Object.keys(D.parcelIdx.tiles)[0] + '.json'), 'utf8'));
    ok(t0.p.every(row => row.length === 6 && typeof row[0] === 'string' && row[0].length > 0), 'every stored parcel row is [parcel number, village, mandal, remark class, remark, rings] with a non-empty parcel number');
    const html = Rep.render('customer', { r: await E.attachParcel(await E.report(17.4401, 78.3489), {}), label: '', cust: { price: '', area: '', brokerage: '' }, agent: {}, claim: { peril: 'rain_vehicle', date: '', amount: '', out: null, busy: false }, ai: { q: '', a: '', think: false }, fc: null, air: { aqi: 80, band: 'x' }, access: {}, terrain: { relief: 0 }, line: 'motor', PERILS: PER, open: {}, pref: {} });
    ok(!/Looks fine/.test(html) && /No issue found/.test(html) && /never a clearance/.test(html), 'the report says "No issue found" (never "Looks fine") and states that it is not a clearance');
    const rr = await E.report(17.4401, 78.3489); await E.attachParcel(rr, {});
    const lvl = {}; for (const s of rr.ev.sections) for (const f of s.findings) lvl[f.id] = f.level;
    ok(!['overlap', 'prohib'].some(id => lvl[id] === 'concern'), 'a map overlap or a prohibitory-layer listing is never rated "needs attention" on its own');
  }
""", encoding="utf-8")
p = Path("tests/engine.test.js"); s = p.read_text(encoding="utf-8"); anchor = "  // ---- live APIs (optional) ----"; assert s.count(anchor) == 1
s = s.replace(anchor, Path("tests/_guard_block.js").read_text(encoding="utf-8") + anchor); p.write_text(s, encoding="utf-8")
Path("tests/_guard_block.js").unlink()
print("final checks patched")
