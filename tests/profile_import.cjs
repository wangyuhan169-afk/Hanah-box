const fs=require('fs'),vm=require('vm'),assert=require('assert');
function open(saved,profile,online=true){
 const memory=new Map(saved?[['hanah-library-site-v1',JSON.stringify(saved)],['hanah-library-wyh-v2',JSON.stringify(saved)]]:[]);
 const location={hash:profile?'#profile='+Buffer.from(JSON.stringify(profile)).toString('base64url'):'',pathname:'/Hanah-box/',search:''};
 const context={console,Response,Blob,URL,URLSearchParams,TextEncoder,TextDecoder,Uint8Array,Intl,Date,structuredClone,setTimeout,clearTimeout,crypto:require('crypto').webcrypto,atob,location,history:{replaceState(){location.hash=''}},localStorage:{getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v)},document:{querySelector(){return {textContent:'',onclick:null}}},fetch:async()=>new Response('{}')};context.window=context;vm.createContext(context);
 if(online)vm.runInContext(fs.readFileSync('web/site_boot.js','utf8'),context);
 else vm.runInContext('const HANAH_PROFILE='+JSON.stringify(profile)+';',context);
 vm.runInContext('const HANAH_SOURCES=[];const HANAH_JOBS=[];',context);
 vm.runInContext(fs.readFileSync('web/offline.js','utf8'),context);
 return {state:JSON.parse(memory.get(online?'hanah-library-site-v1':'hanah-library-wyh-v2')),location};
}
const saved={version:1,jobs:[],notices:[],sources:[],profile:{name:'已有档案',major:'旧专业',saved_extra:'保留'},career:{custom:[{id:'custom:1',title:'保留待办'}]}};
const profile={name:'更新档案',major:'测试专业',birth_date:'2000-01-01',marital_status:'已婚',preferred_region:'广东全省',profile_updated_at:'2026-10-10T00:00:00+08:00',unknown_field:'不得导入'};
const result=open(saved,profile);assert.equal(result.state.profile.major,'测试专业');assert.equal(result.state.profile.birth_date,'2000-01-01');assert.equal(result.state.profile.marital_status,'已婚');assert.equal(result.state.profile.preferred_region,'广东全省');assert.equal(result.state.profile.saved_extra,'保留');assert(!('unknown_field' in result.state.profile));assert.equal(result.location.hash,'');assert.deepEqual(result.state.career,saved.career);
assert.equal(open(result.state,null).state.profile.major,'测试专业');
const offline=open(saved,profile,false).state;assert.equal(offline.profile.major,'测试专业');offline.profile.major='后来手动修改';assert.equal(open(offline,profile,false).state.profile.major,'后来手动修改');assert.deepEqual(offline.career,saved.career);
console.log('PASS profile import: update existing profile, retain other records, consume fragment, keep later manual edits.');
