/* Try the parcel matcher on real parcels from the downloaded tiles.  node research/v7/parcel_try.js */
const fs = require('fs'), path = require('path'), vm = require('vm');
const WEB = path.join(__dirname, '..', '..', 'web');
const sb = { console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout, clearTimeout, AbortController,
  fetch: u => { if (/^https?:/.test(u)) return Promise.reject(new Error('offline')); const p = path.join(WEB, u); return fs.existsSync(p) ? Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) }) : Promise.resolve({ ok: false, status: 404, json: async () => ({}) }); } };
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.SETUE = SETUE;', sb);
const E = sb.SETUE;
const centroid = r => { let la = 0, lo = 0; for (const p of r) { la += p[0]; lo += p[1]; } return [la / r.length, lo / r.length]; };
(async () => {
  await E.load();
  const idx = JSON.parse(fs.readFileSync(path.join(WEB, 'data/parcels/index.json'), 'utf8'));
  // pick Kondapur-area parcels (tile with many small parcels)
  const t = JSON.parse(fs.readFileSync(path.join(WEB, 'data/parcels/' + Object.keys(idx.tiles).find(k => idx.tiles[k] > 900) + '.json'), 'utf8'));
  const norm = t.p.filter(p => p[3] === 0 && p[0] && p[5][0].length >= 6 && p[5][0].length <= 12).slice(0, 400);
  const P = norm[120], Q = norm[121];
  const [la, lo] = centroid(P[5][0].slice(0, -1)), vname = t.v[P[1]];
  const show = (name, m) => console.log(name.padEnd(34), m.status.padEnd(12), (m.reason || '').padEnd(20), m.parcel ? `sy ${m.parcel.number}/${m.parcel.village}` : '', m.neighbour ? 'nb ' + JSON.stringify(m.neighbour) : '', '|', m.text.slice(0, 110));
  console.log('pin at centroid of parcel', P[0], vname, [la.toFixed(5), lo.toFixed(5)]);
  const d = await E.parcelLoad(la, lo); console.log('loaded', d.ok, 'parcels', d.parcels.length, 'tiles', d.tiles);
  show('no reference', E.parcelMatch(la, lo, d, {}));
  show('correct number', E.parcelMatch(la, lo, d, { survey: P[0] }));
  show('correct number + village', E.parcelMatch(la, lo, d, { survey: P[0], village: vname }));
  show('correct number, wrong village', E.parcelMatch(la, lo, d, { survey: P[0], village: 'Zzzzville' }));
  show('village spelled slightly differently', E.parcelMatch(la, lo, d, { survey: P[0], village: vname.slice(0, -1) + 'e' }));
  show('number of the neighbouring parcel', E.parcelMatch(la, lo, d, { survey: Q[0] }));
  show('number that does not exist', E.parcelMatch(la, lo, d, { survey: '99999/9' }));
  show('number with spaces/zeros', E.parcelMatch(la, lo, d, { survey: ' 0' + P[0].replace('/', ' / 0') }));
  show('Gachibowli pin, no reference', E.parcelMatch(17.4401, 78.3489, await E.parcelLoad(17.4401, 78.3489), {}));
  show('Charminar (old city)', E.parcelMatch(17.3616, 78.4747, await E.parcelLoad(17.3616, 78.4747), {}));
  show('Outside the study box', E.parcelMatch(18.5, 79.5, await E.parcelLoad(18.5, 79.5), {}));
  const r = await E.report(la, lo); await E.attachParcel(r, { survey: P[0] });
  for (const s of r.ev.sections) for (const f of s.findings) if (['plot', 'planauth', 'zoning', 'prohib', 'overlap', 'supply', 'supplynet', 'sewernet'].includes(f.id)) console.log(`[${f.level}|${f.conf}] ${f.id}: ${f.value}  {scope ${f.scope}}`);
  console.log('identity:', JSON.stringify(r.ev.identity).slice(0, 220)); console.log('gaps:', r.ev.gaps.length);
})();
