// Pure planning model. Suggested goals never become official recruitment deadlines.
(()=>{
const day=s=>String(s||'').slice(0,10),add=(s,n)=>new Date(Date.parse(s+'T00:00:00Z')+n*86400000).toISOString().slice(0,10);
const track=j=>j.category==='辅导员'?'辅导员':j.category==='教师'?'教师':'宣传行政';
window.HANAH_CAREER=c=>({tasks:{},custom:[],study:{},settings:{},...c});
window.HANAH_STRATEGY=(jobs,profile,today,career={})=>{
 const state=window.HANAH_CAREER(career),ready=!!(profile.degree&&profile.major),groups=window.HANAH_PLANS(jobs,today),targets=[];
 for(const g of groups){
  const candidates=g.jobs.filter(j=>j.match?.relevant&&j.match.summary!=='不符合'&&!j.cancelled).sort((a,b)=>Number(['正在报名','即将报名'].includes(b.status))-Number(['正在报名','即将报名'].includes(a.status))||String(b.published||'').localeCompare(a.published||''));
  if(!ready||!candidates.length)continue;
  const j=candidates[0],uncertain=j.match.items.filter(i=>i.outcome==='需核实'),active=['正在报名','即将报名'].includes(j.status)||(j.status==='滚动招聘'&&day(j.deadline)>=today),rolling=!active&&['滚动招聘','截止待核实'].includes(j.status);
  const subject=[...(j.majors||[]),j.evidence?.major||''].join(' '),teachingUnclear=(j.category==='教师'||/教师|老师|讲师/.test(j.title))&&(!j.evidence?.degree||!subject.trim()||(!subject.includes('不限')&&!subject.includes(profile.major)));
  if(teachingUnclear)uncertain.push({field:'教师专业门槛',outcome:'需核实',evidence:'教师岗位必须先核对学历与对应专业；缺失专业字段不能作为与本人匹配的证据。'});
  const ageText=j.eligibility?.age_text||j.attachment_fields?.['年龄']||j.evidence?.age||'',limit=ageText.match(/(\d+)\s*(?:周岁|岁)(?:及)?以下|不超过(\d+)\s*(?:周岁|岁)/),year=active?Number(today.slice(0,4)):2027;
  const ageRisk=limit&&profile.birth_date&&year-Number(profile.birth_date.slice(0,4))-1>Number(limit[1]||limit[2]);
  if(ageRisk)uncertain.push({field:'年龄风险',outcome:'需核实',evidence:`按${year}年最低周岁已超过已录入年龄上限；若沿用此限制可能无法报考。核实计算日与放宽条件后再投入备考。`});
  const barrier=teachingUnclear||ageRisk||uncertain.some(i=>/职称|高校工作经历/.test(i.field));
  const observed=g.repeated&&g.months.length?`2027-${String(Math.max(1,Math.min(...g.months)-1)).padStart(2,'0')}-01`:null;
  const date=active?day(j.deadline):rolling?add(today,7):observed||'2027-01-31';
  const kind=active?'当前投递':rolling?'先确认空缺':g.repeated?'2027重点观察':'2027储备目标';
  const reasons=j.match.items.filter(i=>i.outcome==='符合').map(i=>i.field),tasks=[];
  const submit=active?[today,day(j.opens)||today,day(j.advice?.date)||add(day(j.deadline),-3)].sort().at(-1):date;
  const goal=active?submit:rolling?date:[today,add(date,-14)].sort().at(-1);
  const prep=active?[today,add(goal,-2)].sort().at(-1):goal;
  const push=(type,title,detail,due=prep)=>tasks.push({id:g.key+'::'+type,target:g.key,school:g.school,role:g.title,title,detail,due,dueKind:'建议完成日',official:active?j.deadline:null,url:j.source_url,track:track(j),...state.tasks[g.key+'::'+type]});
  push('eligibility',barrier?'先核实关键资格，再决定投入':'向招聘方确认资格与考试范围',uncertain.map(i=>i.field+'：'+i.evidence).join('\n')||'逐项核对新公告的年龄、专业、身份、考试科目与材料要求。',active?[today,add(prep,-1)].sort().at(-1):prep);
  push('materials','建立本岗位报名材料清单',j.materials?`已录入公告材料：\n${j.materials}\n按原公告逐项检查签字、盖章、扫描及命名要求；历史材料不能直接作为2027必备清单。`:'公告材料尚未完整提取：打开原文和附件，列出材料、签章单位、报名方式与提交时刻，再修改本任务。');
  if(profile.degree_origin==='境外')push('major',profile.certification==='已取得'?'整理留服认证与专业认定材料':'核实认证要求并准备认证材料','对照毕业证、学位、认证书、成绩单与课程说明，向目标学校确认传播学对应专业范围。境外专业不自动等同国内专业代码。');
  if(uncertain.some(i=>/学生干部/.test(i.field)))push('leadership','核对学生干部任职证明要求','确认原公告是否适用于往届；如适用，请原学校出具职务、起止年月、任职年限及盖章证明。企业教育工作不能替代高校任职经历。');
  if(uncertain.some(i=>/语言/.test(i.field)))push('language','核实并准备语言能力证明',uncertain.some(i=>/六级|CET.?6/i.test(i.evidence||''))?'核对六级／同等语言能力的认定方式；先确认已有成绩和是否接受替代证明，再安排考试。':'按公告确认中英文写作与沟通能力的考核方式，准备语言作品、经历或成绩证明。公告未要求统一语言考试时，不自动安排六级考试。');
  if(uncertain.some(i=>/工作经历/.test(i.field)))push('experience','整理岗位职责与工作经历证据','按实际任职年月整理劳动合同、社保和职责证明；专项公文、宣传或高校工作经历需单独确认，不能仅以总工作年限替代。');
  push('study','完成一轮对应岗位练习',`进入学习备考的「${track(j)}」方向，完成知识卡、一次自编案例／写作练习，记录不足。新公告发布后按具体笔试与面试科目调整。`,active?prep:[today,add(goal,-14)].sort().at(-1));
  push('action',active?'提交报名并留存回执':rolling?'联系学校确认仍有空缺':'检查2027新公告并重新评估资格',active?`报名开始：${j.opens||'未披露'}；官方截止：${j.deadline}。建议提前提交；请同时核对材料期限 ${j.material_deadline||'未单独录入'}、审核、缴费与邮寄规则。`:'本日期是个人关注目标，不是报名截止。确认新公告、岗位表、人数与年龄计算日，重新生成报名计划。',submit);
  targets.push({...g,job:j,kind,date,barrier,uncertain,reasons,tasks,track:track(j),pinned:!!state.settings['pin:'+g.key],official:active?j.deadline:null,observation:observed});
 }
 targets.sort((a,b)=>Number(b.pinned)-Number(a.pinned)||Number(a.barrier)-Number(b.barrier)||(['当前投递','先确认空缺','2027重点观察','2027储备目标'].indexOf(a.kind)-['当前投递','先确认空缺','2027重点观察','2027储备目标'].indexOf(b.kind))||a.date.localeCompare(b.date));
 const chosen=targets.filter(t=>t.pinned||(!t.barrier&&(t.kind==='当前投递'||t.kind==='2027重点观察')));
 const tasks=[...chosen.flatMap(t=>t.tasks),...state.custom.map(t=>({...t,dueKind:'自定完成日',custom:true}))].sort((a,b)=>Number(!!a.done)-Number(!!b.done)||String(a.due).localeCompare(String(b.due)));
 return {ready,targets,tasks,chosen};
};
})();
