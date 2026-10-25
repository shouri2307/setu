const fs=require('fs'),path=require('path'),vm=require('vm');const WEB=path.join(__dirname,'..','..','web');
const sb={console,Math,JSON,Promise,Date,Set,Map,Array,Object,Number,String,isFinite,isNaN,parseFloat,setTimeout,clearTimeout,AbortController,fetch:u=>{if(/^https?:/.test(u))return Promise.reject(new Error('offline'));const p=path.join(WEB,u);return fs.existsSync(p)?Promise.resolve({ok:true,json:async()=>JSON.parse(fs.readFileSync(p,'utf8'))}):Promise.resolve({ok:false,status:404,json:async()=>({})});}};
vm.createContext(sb);vm.runInContext(fs.readFileSync(path.join(WEB,'platform','engine.js'),'utf8')+'\n;globalThis.SETUE=SETUE;',sb);const E=sb.SETUE;
(async()=>{await E.load();const c={};let minOther=1e9;
for(let la=17.20;la<=17.66;la+=.01)for(let lo=78.18;lo<=78.70;lo+=.01){const s=E.seismicFacts(la,lo);const k=s?String(s.zone):'null';c[k]=(c[k]||0)+1;if(s&&s.other)minOther=Math.min(minOther,s.other.d);}
console.log('zone counts over the whole map region (17.20-17.66 N, 78.18-78.70 E, 0.01 deg grid):',c,'| nearest other-zone boundary anywhere on the grid:',Math.round(minOther/1000),'km');})();
