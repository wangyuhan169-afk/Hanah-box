// Count institutions by the official roster, keeping source registration and job verification separate.
(()=>{
window.HANAH_COVERAGE=(directory,sources,jobs)=>{
 const rows=directory.schools.map(s=>{
  const names=[s.name,...(s.aliases||[])],own=sources.filter(x=>names.includes(x.name)),aggregate=sources.filter(x=>names.some(n=>x.schools?.[n])),positions=jobs.filter(j=>names.includes(j.school)),reviewed=positions.filter(j=>['原文已核对','已核验'].includes(j.verification));
  return {...s,sources:own,aggregate,jobs:positions,reviewed,state:reviewed.length?'有已核对岗位':positions.length?'有岗位记录':own.length?'已配置院校来源':'未配置院校来源'};
 });
 return {rows,total:rows.length,configured:rows.filter(r=>r.sources.length).length,recorded:rows.filter(r=>r.jobs.length).length,verified:rows.filter(r=>r.reviewed.length).length,missing:rows.filter(r=>!r.sources.length).length};
};
})();
let directoryPage=0,directoryBound=false,directoryView;
function renderDirectory(){
 const directory=window.HANAH_DIRECTORY_DATA;if(!directory)return;
 directoryView=window.HANAH_COVERAGE(directory,data.sources,data.jobs);
 const c=directoryView,levels=directory.schools.reduce((a,s)=>(a[s.school_level]=(a[s.school_level]||0)+1,a),{});
 $('#schools').textContent=c.configured+'/'+c.total;
 $('#coverageNote').textContent=`全省普通高校名录 ${c.total} 所（本科 ${levels['本科']}、专科 ${levels['专科']}）；配置院校来源 ${c.configured} 所，有岗位记录 ${c.recorded} 所，有已核对岗位 ${c.verified} 所。来源接入与岗位记录都不代表全校岗位完整采集。`;
 $('#directorySummary').innerHTML=`<div class="coverageCounts"><div><strong>${c.total}</strong><span>全省名录</span></div><div><strong>${c.configured}</strong><span>配置院校来源</span></div><div><strong>${c.recorded}</strong><span>有岗位记录</span></div><div><strong>${c.verified}</strong><span>有已核对岗位</span></div></div><p>仍有 ${c.missing} 所未配置独立院校招聘来源。政府汇总入口另计；已经接入的栏目也可能有访问失败、附件未解析或遗漏。</p><small>教育部名单截至 ${esc(directory.as_of)}；${esc(directory.scope)}。<a href="${safeLink(directory.source_url)}" target="_blank" rel="noopener">核对名单依据 ↗</a></small>`;
 if(!directoryBound){
  directoryBound=true;$('#directoryCity').innerHTML='<option value="">全部城市</option>'+[...new Set(c.rows.map(r=>r.city))].sort().map(v=>`<option>${esc(v)}</option>`).join('');
  for(const id of ['directoryCity','directoryLevel','directoryNature','directoryState'])$('#'+id).onchange=()=>{directoryPage=0;renderDirectory()};
  $('#directoryQuery').oninput=()=>{directoryPage=0;renderDirectory()};
  $('#directoryPrev').onclick=()=>{directoryPage=Math.max(0,directoryPage-1);renderDirectory()};$('#directoryNext').onclick=()=>{directoryPage++;renderDirectory()};
  document.body.addEventListener('click',e=>{const b=e.target.closest('[data-directory-jobs]');if(!b)return;const row=directoryView.rows.find(r=>r.code===b.dataset.directoryJobs);if(!row?.jobs.length)return;filters.forEach(f=>Array.from($('#'+f).options).forEach(o=>o.selected=false));$('#major').value='';$('#mine').checked=false;$('#query').value=row.jobs[0].school;scope='all';$('#history').checked=true;tab='jobs';render();$('#jobsPanel').scrollIntoView({behavior:'smooth',block:'start'})});
 }
 if(tab!=='sources')return;
 const q=$('#directoryQuery').value.trim(),city=$('#directoryCity').value,level=$('#directoryLevel').value,nature=$('#directoryNature').value,state=$('#directoryState').value;
 const rows=c.rows.filter(r=>(!q||[r.name,...(r.aliases||[])].some(n=>n.includes(q)))&&(!city||r.city===city)&&(!level||r.school_level===level)&&(!nature||r.nature===nature)&&(!state||(state==='已配置院校来源'?r.sources.length:state==='未配置院校来源'?!r.sources.length:state==='有岗位记录'?r.jobs.length:r.reviewed.length)));
 const pages=Math.max(1,Math.ceil(rows.length/24));directoryPage=Math.min(directoryPage,pages-1);
 $('#directoryCount').textContent=`${rows.length} 所 · 第 ${directoryPage+1} / ${pages} 页`;
 $('#directoryPrev').disabled=directoryPage===0;$('#directoryNext').disabled=directoryPage>=pages-1;
 $('#directoryCards').innerHTML=rows.slice(directoryPage*24,directoryPage*24+24).map(r=>`<article class="directoryCard"><strong>${esc(r.name)}</strong><small>${esc(r.city)} · ${esc(r.nature)} · ${esc(r.school_level)}</small><span class="badge ${!r.reviewed.length?'warn':''}">${esc(r.state)}</span><small>岗位记录 ${r.jobs.length} · 已核对 ${r.reviewed.length}</small>${r.aliases?.length?`<small>旧名／别名：${esc(r.aliases.join('、'))}</small>`:''}${r.sources.length?`<a href="${safeLink(r.sources[0].url)}" target="_blank" rel="noopener">已登记的官方招聘入口 ↗</a><small>${esc(r.sources[0].coverage_state||'检查结果待更新')}${r.sources[0].error?' · 访问存在失败':''}</small>`:r.aggregate.length?`<a href="${safeLink(r.aggregate[0].url)}" target="_blank" rel="noopener">政府汇总入口 ↗</a><small>尚未配置独立院校栏目</small>`:'<small>招聘栏目尚未接入，不能判断是否有招聘。</small>'}${r.jobs.length?`<button data-directory-jobs="${esc(r.code)}">查看该校岗位记录</button>`:''}</article>`).join('')||'<p class="muted">没有符合条件的院校，可清空名录筛选。</p>';
}
