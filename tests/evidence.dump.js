/* Print the evidence report for given places:  node tests/evidence.dump.js "Name:lat,lon" ...   (no args = a default set of contrasting places) */
const fs = require('fs'), path = require('path'), vm = require('vm');
const WEB = path.join(__dirname, '..', 'web'), realFetch = fetch;
const sb = { console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout,
  fetch: u => { if (/^https?:/.test(u)) return realFetch(u); const p = path.join(WEB, u); return fs.existsSync(p) ? Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) }) : Promise.resolve({ ok: false, status: 404, json: async () => { throw new Error('404'); } }); } };
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.SETUE = SETUE;', sb);
const E = sb.SETUE;
const DEF = ['Hussain Sagar:17.4235,78.4745', 'Gachibowli:17.4401,78.3489', 'Charminar:17.3616,78.4747', 'Saroornagar:17.3558,78.5260', 'Jeedimetla:17.5140,78.4500', 'Shamshabad outskirts:17.2600,78.4300'];
(async () => {
  await E.load();
  for (const a of (process.argv.slice(2).length ? process.argv.slice(2) : DEF)) {
    const [name, ll] = a.split(':'), [lat, lon] = ll.split(',').map(Number);
    const r = await E.report(lat, lon); if (!r.ok) { console.log('\n##', name, 'outside'); continue; }
    console.log(`\n######## ${name} (${r.ward.name}${r.outside ? ', OUTSIDE 145 wards' : ''}) — ${r.ev.total} findings`);
    for (const s of r.ev.sections) {
      console.log(`== ${s.title}: ${s.rating}  (concern ${s.counts.concern}, watch ${s.counts.watch}, good ${s.counts.good}, info ${s.counts.info}, unknown ${s.counts.unknown})`);
      for (const f of s.findings) console.log(`   [${f.level.padEnd(7)}|${f.conf.padEnd(11)}] ${f.label}: ${f.value}`);
    }
  }
})();
