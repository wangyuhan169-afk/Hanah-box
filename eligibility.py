"""Evidence-based personal triage; triage is not admission or credential certification."""
from datetime import date
import re
RANK={'高中':-1,'大专':0,'本科':1,'硕士':2,'博士':3}

def age_on(birth,as_of):
    b=date.fromisoformat(birth);d=date.fromisoformat(as_of[:10])
    return d.year-b.year-((d.month,d.day)<(b.month,b.day))

def assess(j,p,today,status='截止待核实'):
    items=[]
    def add(field,outcome,evidence):items.append({'field':field,'outcome':outcome,'evidence':evidence or '公告未明确，需核实'})
    e=j.get('evidence',{});f=j.get('attachment_fields',{});rules=j.get('eligibility',{})
    conditions=j.get('conditions','');full=j.get('official_text','')
    degree=j.get('degree');user=p.get('degree')
    add('学历',('符合' if RANK[user]>=RANK[degree] else '不符合') if user in RANK and degree in RANK and e.get('degree') else '需核实',e.get('degree'))
    majors=j.get('majors',[]);m=p.get('major','');major_rule=e.get('major','')
    major_result='符合' if m and major_rule and (m in majors or '不限' in majors) else '需核实'
    # Overseas subject titles need the recruiting unit's equivalence ruling, not an invented code.
    if p.get('degree_origin')=='境外' and '不限' not in majors:major_result='需核实'
    add('专业',major_result,major_rule)
    age_rule=rules.get('age_text') or f.get('年龄') or e.get('age','');ref=rules.get('age_as_of')
    limit=re.search(r'(\d+)\s*(?:周岁|岁)(?:及)?以下|不超过(\d+)\s*(?:周岁|岁)',age_rule)
    if not ref and re.search(r'年龄(?:及工作经历)?计算至报名截止日',full) and j.get('deadline'):ref=j['deadline'][:10]
    outcome='需核实';age_note=age_rule
    if limit and ref and p.get('birth_date'):
        age=age_on(p['birth_date'],ref);outcome='符合' if age<=int(limit[1] or limit[2]) else '需核实' if any(x in age_rule for x in ['放宽','职称','一般','原则']) else '不符合'
        age_note+=f'；计算基准 {ref}，届时 {age} 周岁'
    elif age_rule:age_note+='；年龄计算基准尚待核实'
    add('年龄',outcome,age_note)
    party=j.get('party_required');add('党员',('不符合' if party and p.get('party')=='否' else '符合') if party is not None and p.get('party') in ['是','否'] and e.get('party') else '需核实',e.get('party'))
    add('应届身份','不符合' if (rules.get('fresh_required') and p.get('fresh')=='否') or (rules.get('fresh_year') and p.get('graduation_year') and int(p['graduation_year'])!=rules['fresh_year']) else '符合' if rules.get('fresh_required') is False else '需核实',rules.get('fresh_text') or f.get('招聘对象') or e.get('fresh'))
    pref=p.get('establishment');add('编制','符合' if pref and (pref=='不限' or pref==j.get('establishment')) else '需核实',j.get('establishment'))
    if p.get('degree_origin')=='境外':add('境外学历认证','符合' if p.get('certification')=='已取得' else '需核实','本人认证状态：'+p.get('certification','待核实')+'；按公告取得证书、认证及专业认定')
    special=f.get('其他要求',f.get('职称及其它条件',''))+' '+f.get('备注','')+' '+conditions
    if '本科阶段为外国语言文学类B0502' in special and p.get('undergrad_major')=='环境科学':add('本科专业','不符合','岗位明确要求本科外国语言文学类B0502；本人本科环境科学')
    gender_text=rules.get('sex_text') or special
    if re.search(r'仅限男性|限男性|性别[：:]男',gender_text) and p.get('sex')=='女':add('性别 / 住宿','不符合',gender_text)
    elif re.search(r'适[宜合]男性报考',gender_text) and p.get('sex')=='女':add('性别 / 住宿','需核实',gender_text+'；适宜男性的表述不等同仅限男性，须向招聘方确认')
    elif any(x in gender_text for x in ['男生宿舍','男生公寓','男生社区']):add('性别 / 住宿','需核实',gender_text+'；住宿条件是否限定性别须问招聘方')
    elif any(x in gender_text for x in ['女生宿舍','女生公寓','女生社区']):add('住宿条件','需核实',gender_text)
    if re.search(r'学生干部|团委|学生会',special):add('学生干部证明','需核实',special+'；本人提供团委任职经历，任职年限及盖章证明待补充')
    experience=f.get('工作经历','');experience_text=experience+' '+special
    if re.search(r'(?:高校|高等院校|专职辅导员).*?(?:工作经历|工作经验)|(?:工作经历|工作经验).*?(?:高校|高等院校)',experience_text):
        add('高校工作经历','需核实',experience_text+'；企业教育经历不直接等同高校专职辅导员经历')
    elif experience and experience not in ['不限','无']:
        add('工作经历','需核实',experience_text+'；需核对具体岗位职责、起止和证明，十年为本人自述')
    elif re.search(r'\d+年以上.*?(?:工作经历|工作经验)',special,re.S):
        add('专项工作经历','需核实',special+'；须证明公告要求的具体工作，企业教育年限不能直接替代')
    if re.search(r'英语六级|CET.?6|俄语.*(?:能力|流利)|英语.*(?:工作能力|流利)|中英文.*(?:写作|口语|沟通)',special,re.I):
        add('语言能力','需核实',special+'；尚未提供公告要求的语言成绩或能力证明')
    if f.get('职称等级') and f['职称等级'] not in ['不限','无']:add('职称','需核实',f['职称等级']+'；本人尚未提供职称证书')
    summary='不符合' if any(i['outcome']=='不符合' for i in items) else '需进一步核实' if any(i['outcome']=='需核实' for i in items) else '符合已知条件'
    reasons=[i['field']+'：'+i['evidence'] for i in items if i['outcome']=='不符合']
    major_related=not majors or '不限' in majors or (bool(p.get('major')) and any(p['major'] in m for m in majors)) or (p.get('major')=='传播学' and bool(re.search(r'传播|新闻|新媒体',major_rule))) or (degree in ['本科','大专','高中'] and bool(p.get('undergrad_major')) and p['undergrad_major'] in major_rule)
    preferred=p.get('preferred_categories') or ['辅导员','行政','教辅','专业技术','教师','科研']
    if isinstance(preferred,str):preferred=re.split(r'[、,，]',preferred)
    relevant=major_related and j.get('category') in preferred and not re.search(r'值班员|保安|保洁|司机|医师',j.get('title',''))
    priority='明确门槛不符' if summary=='不符合' else '历年参考' if status in ['已截止','已取消'] else '优先核实' if relevant else '其他岗位'
    if priority=='优先核实' and j.get('verification') not in ['原文已核对','已核验']:priority='新增待核验'
    return {'summary':summary,'items':items,'priority':priority,'reasons':reasons,'current_age':age_on(p['birth_date'],today) if p.get('birth_date') else None,'relevant':bool(relevant)}
