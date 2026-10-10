/* p16_wardloc.js — precompute the ward-level Location Score so the map loads instantly.
 * Run:  node pipeline/p16_wardloc.js        -> web/data/wardloc.json  { wardId: score }
 * (Rerun after any change to geo.json / gov.json / engine scoring.) */
const fs = require('fs'), path = require('path'), vm = require('vm');
const WEB = path.join(__dirname, '..', 'web');
const sandbox = {
  console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout,
  fetch: u => Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(path.join(WEB, u), 'utf8')) })
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.E = SETUE;', sandbox);
(async () => {
  const E = sandbox.E; await E.load();
  const out = {}; let n = 0;
  for (const w of E.D.wards) { const r = await E.report(w.c[1], w.c[0]); if (r.ok) { out[w.id] = r.pillars.score; n++; } }
  fs.writeFileSync(path.join(WEB, 'data', 'wardloc.json'), JSON.stringify(out));
  console.log('wrote web/data/wardloc.json for', n, 'wards');
})();
