/* Print the engine's batch-2 values for the validation sample as JSON (research/v6/engine_sample.json). */
const fs = require('fs'), path = require('path'), vm = require('vm');
const WEB = path.join(__dirname, '..', '..', 'web');
const sb = { console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout, clearTimeout, AbortController,
  fetch: u => Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(path.join(WEB, u), 'utf8')) }) };
vm.createContext(sb); vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + ';globalThis.E=SETUE', sb);
const PTS = { 'Hussain Sagar': [17.4235, 78.4745], 'Gachibowli': [17.4401, 78.3489], 'Charminar': [17.3616, 78.4747], 'Saroornagar lake': [17.3558, 78.5260], 'Shamshabad edge': [17.2403, 78.4294], 'Medchal': [17.63, 78.48] };
(async () => {
  const E = sb.E; await E.load(); const out = {};
  for (const [n, [la, lo]] of Object.entries(PTS)) {
    const r = await E.report(la, lo), t = E.tankFacts(la, lo), s = E.streamFacts(la, lo), rf = r.outside ? null : E.rainFacts(r.wid), an = r.outside ? null : E.analogFacts(r.wid), c = E.checklist(r);
    out[n] = { lat: la, lon: lo, wid: r.outside ? null : r.wid, outside: !!r.outside, tanks: { n2: t.n2, nCap: t.nCap, capM3: t.capM3, nearest_d: t.nearest ? t.nearest.d : null, nearest_name: t.nearest ? t.nearest.t.a[0] : null, enc2023: t.enc2023 },
      stream: s.nearest ? { d: s.nearest.d, o: s.nearest.o, name: s.nearest.name } : null, rain: rf ? { mandal: rf.mandal, years: rf.years, per_year: rf.per_year, mean_over: rf.mean_over, wettest: rf.wettest } : null, analog: an ? { n: an.n, k: an.k } : null,
      checklist: c.items.map(i => i.key + ':' + i.trigger.level) };
  }
  fs.writeFileSync(path.join(__dirname, 'engine_sample.json'), JSON.stringify(out, null, 1)); console.log('written', Object.keys(out).length, 'places');
})();
