"""One-off patch: address comparison in the engine (web/platform/engine.js). Evidence only: no winner, no combined score."""
p = "web/platform/engine.js"
s = open(p, encoding="utf-8").read()

def rep(old, new):
    global s
    assert old in s, "missing: " + old[:90]
    s = s.replace(old, new, 1)

rep("  function analyse(r) {",
r'''  // =====================================================================================================
  // COMPARE TWO ADDRESSES. Same evidence engine for both. It states where findings differ and how much evidence each address has.
  // It never names a winner and never sums a score: "unknown on one side" is NOT COMPARABLE, not better or worse, and unknown never means safe.
  // =====================================================================================================
  const CMP_SEV = { concern: 3, watch: 2, good: 1 };
  function coverage(r) {
    const secs = r.ev.sections.map(sec => { const c = sec.counts, total = sec.findings.length, unknown = c.unknown; return { id: sec.id, title: sec.title, total, unknown, known: total - unknown, rated: c.concern + c.watch + c.good, pct: total ? (total - unknown) / total : 0 }; });
    const total = secs.reduce((a, x) => a + x.total, 0), unknown = secs.reduce((a, x) => a + x.unknown, 0), rated = secs.reduce((a, x) => a + x.rated, 0);
    return { sections: secs, total, unknown, known: total - unknown, rated, pct: total ? (total - unknown) / total : 0 };
  }
  function cmpKind(x, y) {
    if (!x) return 'only-b';
    if (!y) return 'only-a';
    const ux = x.level === 'unknown', uy = y.level === 'unknown';
    if (ux && uy) return 'both-unknown';
    if (ux || uy) return 'not-comparable';
    const sx = CMP_SEV[x.level], sy = CMP_SEV[y.level];
    if (sx && sy) return sx === sy ? 'same' : sx > sy ? 'a-more-severe' : 'b-more-severe';
    if (!sx && !sy) return x.value === y.value ? 'same' : 'differs-unrated';
    return 'not-comparable';   // one side is rated, the other is information only
  }
  function compare(a, b) {
    const ca = coverage(a), cb = coverage(b);
    const sections = SECTIONS.map(([id, title], si) => {
      const fa = a.ev.sections[si].findings, fb = b.ev.sections[si].findings, ia = new Map(fa.map(f => [f.id, f])), ib = new Map(fb.map(f => [f.id, f]));
      const ids = [...fa.map(f => f.id), ...fb.map(f => f.id).filter(id => !ia.has(id))];
      const rows = ids.map(rid => { const x = ia.get(rid) || null, y = ib.get(rid) || null; return { id: rid, label: (x || y).label, a: x, b: y, cmp: cmpKind(x, y), high: HIGH.has(rid) }; });
      const tally = k => rows.filter(rw => rw.cmp === k).length;
      return { id, title, ratingA: a.ev.sections[si].rating, ratingB: b.ev.sections[si].rating, covA: ca.sections[si], covB: cb.sections[si], rows,
        counts: { aMore: tally('a-more-severe'), bMore: tally('b-more-severe'), same: tally('same'), notComparable: tally('not-comparable'), bothUnknown: tally('both-unknown'), onlyA: tally('only-a'), onlyB: tally('only-b'), differsUnrated: tally('differs-unrated') } };
    });
    const all = sections.flatMap(sec => sec.rows.map(rw => ({ ...rw, section: sec.title })));
    const gap = rw => Math.abs(CMP_SEV[rw.a.level] - CMP_SEV[rw.b.level]);
    const bigger = all.filter(rw => rw.cmp === 'a-more-severe' || rw.cmp === 'b-more-severe').sort((p, q) => (q.high - p.high) || (gap(q) - gap(p)));
    return { sections, coverage: { a: ca, b: cb }, biggest: bigger, notComparable: all.filter(rw => rw.cmp === 'not-comparable'),
      checklist: { a: checklist(a).items.length, b: checklist(b).items.length },
      note: `This compares evidence; it does not say which address is safer or better. Evidence coverage differs (${Math.round(ca.pct * 100)}% of findings have data for A, ${Math.round(cb.pct * 100)}% for B), and a finding with no data is never a clean bill of health.` };
  }

  function analyse(r) {''')
rep("return { load, report, evidence, checklist,", "return { load, report, evidence, checklist, compare, coverage,")
open(p, "w", encoding="utf-8").write(s)
print("compare engine patched")
