const fs=require('fs'),path=require('path'),vm=require('vm');const WEB=path.join(__dirname,'..','..','web');
const sb={console,Math,JSON,Promise,Date,Set,Map,Array,Object,Number,String,isFinite,isNaN,parseFloat,setTimeout,clearTimeout,AbortController,fetch:u=>{if(/^https?:/.test(u))return Promise.reject(new Error('offline'));const p=path.join(WEB,u);return fs.existsSync(p)?Promise.resolve({ok:true,json:async()=>JSON.parse(fs.readFileSync(p,'utf8'))}):Promise.resolve({ok:false,status:404,json:async()=>({})});}};
vm.createContext(sb);vm.runInContext(fs.readFileSync(path.join(WEB,'platform','engine.js'),'utf8')+'\n;globalThis.SETUE=SETUE;',sb);const E=sb.SETUE;
(async()=>{await E.load();
const hy=JSON.parse(fs.readFileSync(path.join(WEB,'data','hydraa_tanks.json'),'utf8')).tanks, tp=JSON.parse(fs.readFileSync(path.join(WEB,'data','tank_syn.json'),'utf8')).par;
const pts=[];
// a point inside a tank-survey parcel, a point 150 m outside the outline, a tank without a number, a far point
const withPar=hy.filter(t=>t.syn&&(tp[t.id]||[]).some(p=>p.touch));const t1=withPar[5];const p1=tp[t1.id].find(p=>p.touch);const c=p1.rings[0].reduce((a,q)=>[a[0]+q[0]/p1.rings[0].length,a[1]+q[1]/p1.rings[0].length],[0,0]);
pts.push(['inside tank-survey parcel (centroid)',c[0],c[1],t1.name,t1.syn]);
const t2=hy.find(t=>!t.syn&&t.name);pts.push(['tank without number (ring point)',t2.rings[0][0][0]+0.0008,t2.rings[0][0][1],t2.name,'']);
const t3=withPar[20];pts.push(['near a numbered tank (ring point +200m)',t3.rings[0][0][0]+0.002,t3.rings[0][0][1],t3.name,t3.syn]);
pts.push(['far from any tank',17.4435,78.3811,'','']);
for(const [n,la,lo,nm,sy] of pts){const r=await E.report(la,lo);const f=r.ev.sections.flatMap(x=>x.findings).filter(x=>x.id==='tank_survey');
 console.log('\n##',n,'|',nm,sy);if(!f.length)console.log('  (no tank_survey finding)');for(const x of f)console.log(`  [${x.level}|${x.conf}] ${x.value}\n     ${x.note}`);}
})();
