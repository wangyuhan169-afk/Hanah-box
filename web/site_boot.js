// Public official data; private profile enters via a URL fragment, never a server request.
const HANAH_PROFILE=(()=>{
 const encoded=new URLSearchParams(location.hash.slice(1)).get('profile');
 if(!encoded)return undefined;
 try{
  history.replaceState(null,'',location.pathname+location.search);
  if(encoded.length>12000)throw Error('profile too large');
  const bytes=Uint8Array.from(atob(encoded.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0));
  const input=JSON.parse(new TextDecoder().decode(bytes));
  if(!input||typeof input!=='object'||Array.isArray(input))throw Error('invalid profile');
  const allowed=['name','sex','birth_date','degree','major','party','degree_origin','certification','degree_title','degree_school','degree_start','degree_graduation','graduation_year','graduation_month','undergrad_school','undergrad_major','undergrad_start','undergrad_graduation','undergrad_title','undergrad_date_note','student_leadership','leadership_start','leadership_end','leadership_proof','leadership_note','work_years','higher_ed_counselor_years','work_experience','fresh','establishment','preferred_cities','preferred_categories','profile_updated_at','marital_status','preferred_region'];
  return Object.fromEntries(Object.entries(input).filter(([k,v])=>allowed.includes(k)&&(typeof v==='string'||Array.isArray(v)&&v.every(x=>typeof x==='string'))));
 }catch{return undefined}
})();
window.HANAH_SITE=(()=>{
 const nativeFetch=window.fetch.bind(window);let api,lastAttempt=0;
 const banner=()=>document.querySelector('#snapshotInfo');
 const show=text=>{if(banner())banner().textContent=text};
 const uniqueChanges=rows=>[...new Map(rows.map(x=>[x.at+'|'+x.text,x])).values()];
 return {
  storageKey:'hanah-library-site-v1',
  attach(value){api=value},
  compact(value){
   const next=structuredClone(value),documents={};
   for(const j of next.jobs){
    const key=j.source_url+'|'+(j.document_hash||j.id),text=j.official_text||next.documents?.[j.document_ref];
    if(text){documents[key]=text;j.document_ref=key;delete j.official_text}
   }
   next.documents=documents;return next;
  },
  expand(row,store){if(!row.official_text&&row.document_ref)row.official_text=store.documents?.[row.document_ref]||'';return row},
  async refresh(){
   lastAttempt=Date.now();const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),15000);
   try{
    const response=await nativeFetch('./snapshot.json',{cache:'no-store',signal:abort.signal,referrerPolicy:'no-referrer'});
    if(!response.ok)throw Error('HTTP '+response.status);
    const snapshot=await response.json();
    if(snapshot.version!==1||!Array.isArray(snapshot.jobs)||!Array.isArray(snapshot.sources))throw Error('快照格式需要核查');
    snapshot.jobs.forEach(api.validate);
    const next=structuredClone(api.get()),old=new Map(next.jobs.map(j=>[j.id,j]));
    for(const incoming of snapshot.jobs){
     const merged=(incoming.merged_ids||[]).map(id=>old.get(id)).filter(Boolean);
     if(!merged.length)continue;
     const keeper=old.get(incoming.id)||{...incoming,personal:{}};
     const personal=[keeper.personal||{},...merged.map(j=>j.personal||{})];
     keeper.personal={...personal.find(p=>p.stage)||{},...keeper.personal,favorite:personal.some(p=>p.favorite),note:[...new Set(personal.map(p=>p.note).filter(Boolean))].join('\n')};
     old.set(incoming.id,keeper);
     for(const row of merged){if(row._local_edit)continue;old.delete(row.id)}
    }
    for(const incoming of snapshot.jobs){
     const previous=old.get(incoming.id),notice=(snapshot.notices||[]).find(n=>n.url===incoming.source_url);
     const changed=previous?.document_hash&&previous.document_hash!==incoming.document_hash;
     let row;
     if(previous?._local_edit){
      row={...previous};
      if(changed){row.verification='变更待复核';row.changes=uniqueChanges([...(row.changes||[]),{at:incoming.last_checked||snapshot.snapshot_at,text:'官方内容已更新，本地编辑保留，请对照原公告复核'}])}
     }else row={...incoming,personal:previous?.personal||{},changes:uniqueChanges([...(previous?.changes||[]),...(incoming.changes||[]),...(notice?.changes||[])])};
     if(notice?.changes?.some(c=>!row.last_verified||c.at>row.last_verified))row.verification='变更待复核';
     old.set(row.id,row);
    }
    next.jobs=[...old.values()];next.sources=snapshot.sources;next.notices=snapshot.notices||[];next.snapshot_at=snapshot.snapshot_at;
    api.persist(next);
    const time=new Date(snapshot.snapshot_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false});
    show('官方快照：'+time+' · 北京时间 · 新采集岗位需核验');
    return {ok:true};
   }catch(e){show('快照同步未成功，保留已存岗位与个人记录；请稍后重试。');throw e}
   finally{clearTimeout(timer)}
  },
  async due(){if(Date.now()-lastAttempt>300000)return this.refresh();return {ok:true}}
 };
})();
