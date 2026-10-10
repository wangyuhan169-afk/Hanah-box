// UI additions share the existing profile, filters, favorites and local backup store.
function inOpportunityScope(j){
 const current=['正在报名','即将报名'].includes(j.status)||(j.status==='滚动招聘'&&!!j.deadline&&j.deadline.slice(0,10)>=data.today);
 if(scope==='current')return current;
 if(scope==='leads')return ['滚动招聘','截止待核实'].includes(j.status)&&!current;
 if(scope==='history')return ['已截止','已取消'].includes(j.status);
 return true;
}
function renderOpportunityExtras(){
 document.querySelectorAll('[data-scope]').forEach(b=>b.classList.toggle('active',b.dataset.scope===scope));
 $('#scopeNote').textContent={current:'显示有明确报名期限的岗位。滚动招聘的剩余名额仍需确认；“即将报名”须等待开始日期。',leads:'期限未披露、长期招聘和旧公告不等于当前有空缺。先联系学校确认再准备投递。',history:'已截止公告用于了解门槛、考试与材料。报名开始日期来自原文；未披露时不以发布日期替代。',all:'全部真实采集记录；请同时查看报名状态、核验状态与最近检查时间。'}[scope];
 const genuine=data.jobs,open=genuine.filter(j=>['正在报名','即将报名'].includes(j.status)||(j.status==='滚动招聘'&&j.deadline&&j.deadline.slice(0,10)>=data.today)),pending=data.notices.filter(n=>!n.parsed_jobs||n.attachment_errors?.length||n.error),sources=data.sources;
 const timeBound=pending.filter(n=>n.schedule?.deadline&&n.schedule.deadline.slice(0,10)>=data.today);
 $('#currentNoticeCards').innerHTML=scope==='current'&&timeBound.length?`<details class="noticeFold"><summary>另有 ${timeBound.length} 份报名期限尚未过去的公告，岗位表待核验</summary>`+timeBound.map(n=>`<article class="sourceCard"><a href="${safeLink(n.url)}" target="_blank" rel="noopener">${esc(n.title)} ↗</a><small>报名开始 ${esc(showDate(n.schedule.opens))} · 截止 ${esc(showDate(n.schedule.deadline))}</small><p>岗位条件尚未完整录入，不能判断是否适合本人；请先核对官方岗位表。</p></article>`).join('')+'</details>':'';
 $('#open').textContent=open.length;
 $('#collectionSummary').innerHTML=`<strong>信息完整度</strong><span>${sources.length} 个来源入口 · ${sources.filter(s=>s.last_success).length} 个曾成功访问 · ${sources.filter(s=>s.error).length} 个本次访问有失败 · ${pending.length} 份公告仍待解析／复核</span><small>来源数量不是院校全覆盖率；学校官网、政府转载可能重复。自动整理岗位须核验。某校未出现岗位，不能据此判断没有招聘。</small>`;
 $('#planningPanel').hidden=tab!=='planning';
 if(tab==='planning')renderPlans();
 $('#learningPanel').hidden=tab!=='learning';if(tab==='learning')renderLearning();initCareerUi();
 $('#sourceCards').innerHTML=sources.map(s=>{
  const jobs=genuine.filter(j=>j.school===s.name),missing=data.notices.filter(n=>n.school===s.name&&(!n.parsed_jobs||n.attachment_errors?.length||n.error));
  return `<article class="sourceCard"><strong>${esc(s.name)} <span class="badge ${s.error||!s.parsed_jobs?'warn':''}">${esc(s.coverage_state||(s.error?'访问失败':s.last_success?'曾访问成功':'待检查'))}</span></strong><span>${esc(s.nature||'政府汇总入口')} · ${esc(s.school_level||'多院校')} · ${esc(s.city||'地点待核实')}</span><a href="${safeLink(s.url)}" target="_blank" rel="noopener">官方入口 ↗</a><small>最近尝试 ${esc(s.last_attempt||'尚未检查')} · 最近成功访问 ${esc(s.last_success||'尚未成功')}</small><small>发现 ${esc(s.discovered??'未统计')} 份公告 · 本次解析 ${esc(s.parsed_jobs??'未统计')} 个岗位 · 该校留存 ${jobs.length} 个岗位</small><p class="muted">${esc(s.coverage_note||'仅监测所列栏目')}${s.error?'；'+esc(s.error):''}</p>${missing.slice(0,3).map(n=>`<a href="${safeLink(n.url)}" target="_blank" rel="noopener">待核验：${esc(n.title)} ↗</a>`).join('')}</article>`;
 }).join('');
 $('#notices').innerHTML=pending.map(n=>`<article class="sourceCard"><a href="${safeLink(n.url)}" target="_blank" rel="noopener">${esc(n.title)} ↗</a><span>${esc(n.school)} · ${esc(n.verification||'待核验')}</span><small>${esc(n.schedule?.opens?'报名开始 '+n.schedule.opens:'报名开始待提取')} · ${esc(n.schedule?.deadline?'截止 '+n.schedule.deadline:'期限待核实')}</small>${n.error?`<p>${esc(n.error)}</p>`:''}${(n.attachment_errors||[]).map(e=>`<p>${esc(e)}</p>`).join('')}<button data-notice="${esc(n.url)}">核对官方岗位表后录入</button></article>`).join('')||'<p>本轮已发现公告没有待解析项。院校仍可能有未监测栏目。</p>';
 if(!filtered.length&&tab!=='planning'&&tab!=='sources'){
  $('#empty h3').textContent='当前范围和筛选下没有岗位';
  $('#empty p').textContent='这不代表广东高校没有招聘。可清空筛选、查看长期线索，或在院校覆盖页检查未解析公告。';
 }
}
function renderPlans(){renderCareerPlanning()}
