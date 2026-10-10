// Personal triage from explicit announcement fields. No overseas subject-code equivalence inference.
(()=>{
const rank={'高中':-1,'大专':0,'本科':1,'硕士':2,'博士':3};
function ageOn(birth,ref){const b=birth.slice(0,10).split('-').map(Number),d=ref.slice(0,10).split('-').map(Number);return d[0]-b[0]-((d[1]<b[1]||(d[1]===b[1]&&d[2]<b[2]))?1:0)}
window.HANAH_MATCH=(j,p,today,status)=>{
 const items=[],add=(field,outcome,evidence)=>items.push({field,outcome,evidence:evidence||'公告未明确，需核实'}),e=j.evidence||{},f=j.attachment_fields||{},r=j.eligibility||{},full=j.official_text||'';
 add('学历',p.degree in rank&&j.degree in rank&&e.degree?(rank[p.degree]>=rank[j.degree]?'符合':'不符合'):'需核实',e.degree);
 const majors=j.majors||[],m=p.major||'';let major=m&&e.major&&(majors.includes(m)||majors.includes('不限'))?'符合':'需核实';if(p.degree_origin==='境外'&&!majors.includes('不限'))major='需核实';add('专业',major,e.major);
 const ageText=r.age_text||f['年龄']||e.age||'',limit=ageText.match(/(\d+)\s*(?:周岁|岁)(?:及)?以下|不超过(\d+)\s*(?:周岁|岁)/);let ref=r.age_as_of,note=ageText,outcome='需核实';
 if(!ref&&/年龄(?:及工作经历)?计算至报名截止日/.test(full)&&j.deadline)ref=j.deadline.slice(0,10);
 if(limit&&ref&&p.birth_date){const age=ageOn(p.birth_date,ref);outcome=age<=Number(limit[1]||limit[2])?'符合':/放宽|职称|一般|原则/.test(ageText)?'需核实':'不符合';note+=`；计算基准 ${ref}，届时 ${age} 周岁`}else if(ageText)note+='；年龄计算基准尚待核实';add('年龄',outcome,note);
 add('党员',j.party_required!=null&&['是','否'].includes(p.party)&&e.party?(j.party_required&&p.party==='否'?'不符合':'符合'):'需核实',e.party);
 const freshYear=r.fresh_year;add('应届身份',r.fresh_required&&p.fresh==='否'||freshYear&&p.graduation_year&&Number(p.graduation_year)!==freshYear?'不符合':r.fresh_required===false?'符合':'需核实',r.fresh_text||f['招聘对象']||e.fresh);
 add('编制',p.establishment&&(p.establishment==='不限'||p.establishment===j.establishment)?'符合':'需核实',j.establishment);
 if(p.degree_origin==='境外')add('境外学历认证',p.certification==='已取得'?'符合':'需核实','本人认证状态：'+(p.certification||'待核实')+'；按公告取得证书、认证及专业认定');
 const special=(f['其他要求']||f['职称及其它条件']||'')+' '+(f['备注']||'')+' '+(j.conditions||''),sex=r.sex_text||special;
 if(special.includes('本科阶段为外国语言文学类B0502')&&p.undergrad_major==='环境科学')add('本科专业','不符合','岗位明确要求本科外国语言文学类B0502；本人本科环境科学');
 if(/仅限男性|限男性|性别[：:]男/.test(sex)&&p.sex==='女')add('性别 / 住宿','不符合',sex);
 else if(/适[宜合]男性报考/.test(sex)&&p.sex==='女')add('性别 / 住宿','需核实',sex+'；适宜男性的表述不等同仅限男性，须向招聘方确认');
 else if(/男生宿舍|男生公寓|男生社区/.test(sex))add('性别 / 住宿','需核实',sex+'；住宿条件是否限定性别须问招聘方');
 else if(/女生宿舍|女生公寓|女生社区/.test(sex))add('住宿条件','需核实',sex);
 if(/学生干部|团委|学生会/.test(special))add('学生干部证明','需核实',special+'；本人提供团委任职经历，任职年限及盖章证明待补充');
 const xp=f['工作经历']||'',xpText=xp+' '+special;
 if(/(?:高校|高等院校|专职辅导员).*?(?:工作经历|工作经验)|(?:工作经历|工作经验).*?(?:高校|高等院校)/.test(xpText))add('高校工作经历','需核实',xpText+'；企业教育经历不直接等同高校专职辅导员经历');
 else if(xp&&!['不限','无'].includes(xp))add('工作经历','需核实',xpText+'；需核对具体岗位职责、起止和证明，十年为本人自述');
 else if(/\d+年以上[\s\S]*?(?:工作经历|工作经验)/.test(special))add('专项工作经历','需核实',special+'；须证明公告要求的具体工作，企业教育年限不能直接替代');
 if(/英语六级|CET.?6|俄语.*(?:能力|流利)|英语.*(?:工作能力|流利)|中英文.*(?:写作|口语|沟通)/i.test(special))add('语言能力','需核实',special+'；尚未提供公告要求的语言成绩或能力证明');
 if(f['职称等级']&&!['不限','无'].includes(f['职称等级']))add('职称','需核实',f['职称等级']+'；本人尚未提供职称证书');
 const summary=items.some(i=>i.outcome==='不符合')?'不符合':items.some(i=>i.outcome==='需核实')?'需进一步核实':'符合已知条件';
 const majorRelated=!majors.length||majors.includes('不限')||(!!p.major&&majors.some(v=>v.includes(p.major)))||(p.major==='传播学'&&/传播|新闻|新媒体/.test(e.major||''))||(['本科','大专','高中'].includes(j.degree)&&!!p.undergrad_major&&(e.major||'').includes(p.undergrad_major));
 const preferred=Array.isArray(p.preferred_categories)?p.preferred_categories:(p.preferred_categories||'辅导员、行政、教辅、专业技术、教师、科研').split(/[、,，]/);
 const relevant=majorRelated&&preferred.includes(j.category)&&!/值班员|保安|保洁|司机|医师/.test(j.title);
 let priority=summary==='不符合'?'明确门槛不符':['已截止','已取消'].includes(status)?'历年参考':relevant?'优先核实':'其他岗位';
 if(priority==='优先核实'&&!['原文已核对','已核验'].includes(j.verification))priority='新增待核验';
 return {summary,items,priority,reasons:items.filter(i=>i.outcome==='不符合').map(i=>i.field+'：'+i.evidence),current_age:p.birth_date?ageOn(p.birth_date,today):null,relevant};
};
})();
