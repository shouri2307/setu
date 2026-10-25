p = "tests/engine.test.js"
s = open(p, encoding="utf-8").read()
BLOCK = r'''
  // ---- compare two addresses: evidence only, symmetric, honest about gaps ----
  const cA = await E.report(17.4235, 78.4745), cB = await E.report(17.4401, 78.3489), cC = await E.report(17.63, 78.48), cD = await E.report(17.3616, 78.4747);
  const same = E.compare(cA, cA);
  ok(same.sections.every(sec => sec.rows.every(rw => rw.cmp === 'same' || rw.cmp === 'both-unknown' || rw.cmp === 'differs-unrated' && false)) && same.biggest.length === 0 && same.notComparable.length === 0, 'comparing an address with itself finds no differences and no gaps');
  const ab = E.compare(cA, cB), ba = E.compare(cB, cA);
  const flipK = k => ({ 'a-more-severe': 'b-more-severe', 'b-more-severe': 'a-more-severe', 'only-a': 'only-b', 'only-b': 'only-a' }[k] || k);
  ok(ab.sections.every((sec, i) => sec.rows.length === ba.sections[i].rows.length && sec.rows.every(rw => ba.sections[i].rows.some(r2 => r2.id === rw.id && r2.cmp === flipK(rw.cmp)))), 'comparison is symmetric: swapping A and B flips every verdict and nothing else');
  ok(ab.notComparable.length === ba.notComparable.length && ab.biggest.length === ba.biggest.length, 'swap keeps the counts of gaps and differences');
  const nc = ab.notComparable.find(rw => (rw.a.level === 'unknown') !== (rw.b.level === 'unknown'));
  ok(nc && ['concern', 'watch', 'good', 'info'].includes((nc.a.level === 'unknown' ? nc.b : nc.a).level), 'one-sided gaps (unknown vs known) are labelled not comparable, not better or worse', nc && nc.id);
  ok(ab.sections.flatMap(sec => sec.rows).filter(rw => rw.cmp === 'not-comparable').every(rw => rw.a.level === 'unknown' || rw.b.level === 'unknown' || (rw.a.level === 'info') !== (rw.b.level === 'info')), 'only unknown or unrated-vs-rated rows are marked not comparable');
  ok(ab.sections.flatMap(sec => sec.rows).filter(rw => rw.cmp === 'a-more-severe').every(rw => ({ concern: 3, watch: 2, good: 1 })[rw.a.level] > ({ concern: 3, watch: 2, good: 1 })[rw.b.level]), 'a-more-severe is only used when both are rated and A is the more severe');
  ok(ab.sections.flatMap(sec => sec.rows).filter(rw => rw.cmp === 'both-unknown').every(rw => rw.a.level === 'unknown' && rw.b.level === 'unknown'), 'both-unknown is only used when both sides are unknown');
  const jsonKeys = o => o && typeof o === 'object' ? Object.entries(o).flatMap(([k, v]) => [k, ...jsonKeys(v)]) : [];
  ok(!jsonKeys(ab).some(k => /winner|best|safer|better|score|rank|total_?points/i.test(k)), 'the comparison result has no winner, rank or score field');
  ok(/does not say which address is safer or better/.test(ab.note) && /never a clean bill of health/.test(ab.note), 'the comparison note states it is evidence only and that a gap is not safety');
  const cov = E.coverage(cA); ok(cov.known + cov.unknown === cov.total && cov.pct >= 0 && cov.pct <= 1 && cov.sections.length === 5 && cov.total === cA.ev.total, 'coverage is consistent with the evidence report');
  ok(Math.abs(ab.coverage.a.pct - cov.pct) < 1e-9, 'comparison reports each address\'s own evidence coverage');
  ok(E.compare(cA, cC).sections.flatMap(sec => sec.rows).some(rw => rw.cmp === 'only-a' || rw.cmp === 'only-b'), 'findings shown for only one address (a different ward vs outside the wards) are marked as such');
  let cmpBad = 0, cmpRendered = 0;
  const pairs = []; for (let i = 0; i < 24; i++) pairs.push([D.wards[(i * 7) % 145], D.wards[(i * 11 + 3) % 145]]);
  for (const [wa, wb] of pairs) {
    const ra = await E.report(wa.c[1], wa.c[0]), rb = await E.report(wb.c[1], wb.c[0]); if (!ra.ok || !rb.ok) continue;
    const html = Rep.compare({ cmp: { a: ra, b: rb, la: wa.name, lb: wb.name }, open: {} }); cmpRendered++;
    if (/undefined|NaN|\[object|Infinity/.test(html) || /winner|safer address|better address|recommended/i.test(html.replace(/does not say which address is safer or better/g, '')) || !/Evidence gaps: not comparable/.test(html) || !/Where they differ most/.test(html)) { cmpBad++; fails.push(`compare render problem for wards ${wa.id} vs ${wb.id}: ` + (html.match(/.{30}(undefined|NaN|\[object|Infinity|winner|safer address|better address).{30}/) || [''])[0]); }
  }
  ok(cmpBad === 0 && cmpRendered >= 20, `${cmpRendered} comparison pages render cleanly with no winner wording`, cmpBad + ' bad');
  const sw = E.compare(cD, cD); ok(sw.coverage.a.total === sw.coverage.b.total && sw.checklist.a === sw.checklist.b, 'self-comparison has identical coverage and checklist sizes');
'''
anchor = "  // ---- claim check logic ----"
assert anchor in s and "compare two addresses: evidence only" not in s
s = s.replace(anchor, BLOCK + "\n" + anchor, 1)
open(p, "w", encoding="utf-8").write(s)
print("compare tests added")
