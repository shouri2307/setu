const fs=require('fs'),path=require('path'),vm=require('vm');const WEB=path.join(__dirname,'..','..','web');
const sb={console,Math,JSON,Promise,Date,Set,Map,Array,Object,Number,String,isFinite,isNaN,parseFloat,setTimeout,clearTimeout,AbortController,fetch:u=>{if(/^https?:/.test(u))return Promise.reject(new Error('offline'));const p=path.join(WEB,u);return fs.existsSync(p)?Promise.resolve({ok:true,json:async()=>JSON.parse(fs.readFileSync(p,'utf8'))}):Promise.resolve({ok:false,status:404,json:async()=>({})});}};
vm.createContext(sb);vm.runInContext(fs.readFileSync(path.join(WEB,'platform','engine.js'),'utf8')+'\n;globalThis.SETUE=SETUE;',sb);const E=sb.SETUE;
(async()=>{await E.load();
for(const [n,la,lo] of [['Ghatkesar',17.4496,78.6847],['near east edge',17.45,78.652],['Charminar',17.3616,78.4747],['Shamshabad',17.2403,78.4294]]){
 const s=E.seismicFacts(la,lo);const r=await E.report(la,lo);const f=r.ev.sections.flatMap(x=>x.findings).filter(x=>['seismic','seismic_gis','fire_gis'].includes(x.id));
 console.log('\n##',n,JSON.stringify(s));for(const x of f)console.log(`  [${x.level}|${x.conf}] ${x.id}: ${x.value}`);}
})();
