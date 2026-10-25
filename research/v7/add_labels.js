/* Write a human label for every registry factor, taken from what the engine actually emits (across all 145 ward centres and outside places), and report any id the engine emits that the registry lacks.
   node research/v7/add_labels.js */
const fs = require('fs'), path = require('path'), vm = require('vm');
const WEB = path.join(__dirname, '..', '..', 'web');
const sb = { console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout, clearTimeout, AbortController,
  fetch: u => { if (/^https?:/.test(u)) return Promise.reject(new Error('offline')); const p = path.join(WEB, u); return fs.existsSync(p) ? Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) }) : Promise.resolve({ ok: false, status: 404, json: async () => ({}) }); } };
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.SETUE = SETUE;', sb);
const E = sb.SETUE;
(async () => {
  await E.load(); const labels = new Map(), ids = new Set();
  const pts = E.D.wards.map(w => [w.c[1], w.c[0]]).concat([[17.63, 78.48], [17.26, 78.43], [17.2403, 78.4294], [17.597, 78.57], [17.514, 78.45]]);
  for (const [la, lo] of pts) { const r = await E.report(la, lo); if (!r.ok) continue; await E.attachParcel(r, {}); for (const s of r.ev.sections) for (const f of s.findings) { ids.add(f.id); if (!labels.has(f.id)) labels.set(f.id, f.label); } }
  const p = path.join(WEB, 'data', 'quality.json'), q = JSON.parse(fs.readFileSync(p, 'utf8'));
  const missing = [...ids].filter(i => !q.factors[i]), unused = Object.keys(q.factors).filter(i => !ids.has(i));
  for (const [id, f] of Object.entries(q.factors)) if (labels.has(id)) f.label = labels.get(id);
  fs.writeFileSync(p, JSON.stringify(q, null, 1));
  console.log('emitted ids:', ids.size, '| registry factors:', Object.keys(q.factors).length, '| emitted but NOT in registry:', missing, '| in registry but never emitted at these places:', unused);
})();
