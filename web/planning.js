// Planning uses distinct official announcements, never counts table rows as annual recurrence.
(()=>{
const canonical=title=>String(title||'').replace(/[（(][^）)]*(?:岗位代码|\d+名)[^）)]*[）)]/g,'').replace(/(?:岗)?[一二三四五六七八九十\d]+(?:岗)?$/,'').trim();
window.HANAH_PLANS=(jobs,today)=>{
 const target=2027,groups=new Map();
 for(const j of jobs){
  const key=[j.school,j.category,canonical(j.title)].join('|');
  if(!groups.has(key))groups.set(key,{key,school:j.school,title:canonical(j.title),category:j.category,nature:j.nature,school_level:j.school_level,records:[],jobs:[]});
  const g=groups.get(key);g.jobs.push(j);
  const anchor=j.opens||j.published;
  if(!anchor||!/^(20\d{2})-\d{2}-\d{2}/.test(anchor)||Number(anchor.slice(0,4))<2022||Number(anchor.slice(0,4))>=target)continue;
  if(!g.records.some(r=>r.url===j.source_url))g.records.push({url:j.source_url,date:anchor.slice(0,10),published:j.published,opens:j.opens,deadline:j.deadline,basis:j.opens?'报名开始日期':'公告发布日期（未披露报名开始）',verification:j.verification});
 }
 return [...groups.values()].map(g=>{
  g.records.sort((a,b)=>a.date.localeCompare(b.date));
  const years=[...new Set(g.records.map(r=>Number(r.date.slice(0,4))))].sort(),months=[...new Set(g.records.map(r=>Number(r.date.slice(5,7))))].sort((a,b)=>a-b);
  const confirmed=g.records.filter(r=>['原文已核对','已核验'].includes(r.verification)),verifiedYears=[...new Set(confirmed.map(r=>Number(r.date.slice(0,4))))];
  const repeated=years.length>=2,substantiated=verifiedYears.length>=2;
  return {...g,years,months,target,confirmed_count:confirmed.length,repeated,substantiated,
   signal:substantiated?'已核对跨年重复':repeated?'跨年重复线索，待核验':years.length===1?'仅有单年样本':'尚无有效日期样本',
   window:repeated?`2027年 ${months.join('、')} 月附近重点关注`:'不足以预测招聘月份',
   basis:`${g.records.length} 份不同公告，覆盖 ${years.length} 个年份；同一公告的多个岗位行只计一次。`,
   monitoring:months.length?months.map(m=>m===1?'2026-12':`2027-${String(m-1).padStart(2,'0')}`).join('、'):'全年定期关注',
   relevant:g.jobs.some(j=>j.match?.relevant&&j.match?.summary!=='不符合'),
   warning:'同校同类岗位记录，不保证同一编制、条件或名额。2027年是否招聘尚无官方确认；月份仅供安排关注，公告发布日期与报名开始日期分开标注。'};
 }).sort((a,b)=>Number(b.relevant)-Number(a.relevant)||Number(b.repeated)-Number(a.repeated)||b.years.length-a.years.length||a.school.localeCompare(b.school,'zh-CN'));
};
})();
