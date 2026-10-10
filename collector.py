"""Conservative official-announcement parser; ambiguous or protected attachments stay pending."""
from dataclasses import dataclass
from datetime import datetime,timedelta
from io import BytesIO
import hashlib,json,re,zipfile
from urllib.parse import urljoin,urlsplit
from lxml import html
from recruitment import registration, html_rows, table_jobs, category

EXCLUDE = re.compile(r'拟聘|公示|成绩|资格复审|面试通知|面试公告|笔试公告|参加笔试|考试公告|业务考核公告|体检事宜|进入.*名单|勤工助学|招聘会|兼职辅导员选聘|招标|采购|校内公开招聘')
AFFILIATED = re.compile(r'医院|附属.{0,5}(?:小学|中学|幼儿园)|基础教育集团')
RECRUIT = re.compile(r'招聘|选聘|招收')
DATE = re.compile(r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日(?:\s*(上午|下午|晚上)?\s*(\d{1,2})(?:时|点|[:：])(?:\s*(\d{1,2})分?)?)?')

@dataclass
class Document:
    url:str
    title:str
    text:str
    published:str|None
    links:list
    attachments:list
    digest:str
    tables:list=None

def read_document(raw,url):
    encoding='gb18030' if any(x in raw[:2000].lower() for x in [b'gb2312',b'gbk',b'gb18030']) else 'utf-8-sig'
    tree=html.fromstring(raw.decode(encoding,errors='replace'))
    nodes=tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," v_news_content ")]')
    if not nodes: nodes=tree.xpath('//*[@id="vsb_content"]')
    if not nodes: nodes=tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," article_con ")]')
    if not nodes:nodes=tree.xpath('//*[@id="zoom" or @id="content" or @id="article_content"]|//*[contains(@class,"wp_articlecontent") or contains(@class,"TRS_Editor") or contains(@class,"news_content")]')
    content=nodes[0] if nodes else None
    text=''
    if content is None:
        candidates=tree.xpath('//article|//main|//body')
        content=candidates[0] if candidates else tree
    if content is not None:
        clone=html.fromstring(html.tostring(content))
        for n in clone.xpath('.//script|.//style'): n.drop_tree()
        for n in clone.xpath('.//p|.//br|.//tr|.//li|.//h1|.//h2|.//h3'): n.tail='\n'+(n.tail or '')
        text=clone.text_content().strip()
        text=re.sub(r'[\t\xa0 ]+',' ',text)
        text=re.sub(r'\n\s*\n+','\n',text)
    titles=tree.xpath('//h1/text()|//h2/text()|//title/text()')
    title=next((t.strip() for t in titles if len(t.strip())>5 and RECRUIT.search(t)),titles[-1].strip() if titles else '')
    title=re.sub(r'[-—_](?:深圳大学|广东外语外贸大学|广东省人力资源和社会保障厅).*$', '',title).strip()
    links=[(urljoin(url,a.get('href')),a.text_content().strip()) for a in tree.xpath('//a[@href]')]
    attachments=[{'url':u,'title':t} for u,t in links if '/download.jsp?' in u or re.search(r'\.(?:xlsx?|pdf|docx?|zip)(?:$|\?)',u)]
    # Only header dates, never a date embedded in application conditions.
    pub=tree.xpath('//meta[@name="PubDate" or @name="pubdate"]/@content')
    if not pub:
        head=' '.join(tree.xpath('//*[contains(@class,"time") or contains(@class,"date") or contains(@class,"info")]//text()'))
        matches=re.findall(r'20\d{2}[-/]\d{1,2}[-/]\d{1,2}',head)
        pub=matches[:1]
    if not pub:
        m=re.search(r'发布时间\s*[:：]\s*(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})',tree.text_content())
        if m: pub=[f'{int(m[1]):04}-{int(m[2]):02}-{int(m[3]):02}']
    if not pub:
        m=re.search(r'(?:发布日期|发布时间|发布者.*?发布时间)\s*[:：]?\s*(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})',tree.text_content())
        if m:pub=[f'{int(m[1]):04}-{int(m[2]):02}-{int(m[3]):02}']
    published=pub[0].replace('/','-') if pub else None
    return Document(url,title,text,published,links,attachments,hashlib.sha256((text+'\n'+str(attachments)).encode()).hexdigest(),html_rows(raw))

def recruitment_links(doc):
    host=urlsplit(doc.url).hostname
    out={}
    for u,t in doc.links:
        # Official bilingual position titles often omit the Chinese word for recruitment.
        if host=='www.cuhk.edu.cn' and re.fullmatch(r'https://www\.cuhk\.edu\.cn/zh-hans/recruitment/\d+',u) and re.search(r'Ref\.?\s*20\d{2}/',t,re.I):
            out[u]=t;continue
        if urlsplit(u).scheme=='https' and urlsplit(u).hostname==host and RECRUIT.search(t) and not EXCLUDE.search(t) and not AFFILIATED.search(t) and not re.search(r'\.(?:xlsx?|pdf|docx?|zip)(?:$|\?)',u) and (re.search(r'/info/|post_\d|/a(?:_|/)\d/|/page\.htm|/\d{4,}(?:\.html?|$)|article|content|news|/contents/',u,re.I)):out[u]=t
    return list(out.items())

def date_value(m):
    y,mo,d,period,h,minute=m.groups()
    day=f'{int(y):04}-{int(mo):02}-{int(d):02}'
    datetime.fromisoformat(day)
    if h:
        hour=int(h)
        if period in ['下午','晚上'] and hour<12:hour+=12
        if hour==24 and int(minute or 0)==0:
            return (datetime.fromisoformat(day)+timedelta(days=1)).date().isoformat()+'T00:00+08:00'
        if hour>23 or int(minute or 0)>59:raise ValueError('公告时间格式需要人工核验')
        return day+f'T{hour:02}:{int(minute or 0):02}+08:00'
    return day

def deadline(text):
    return registration(text).get('deadline')

def excerpt(text,starts,ends,default='公告未披露'):
    start=None
    for p in starts:
        m=re.search(p,text)
        if m and (start is None or m.start()<start.start()):start=m
    if not start:return default
    tail=text[start.end():]
    stop=len(tail)
    for p in ends:
        m=re.search(p,tail)
        if m:stop=min(stop,m.start())
    return tail[:stop].strip() or default

def application_info(doc):
    """Retain official instructions; a contact email alone is not an application method."""
    end=[r'(?:[一二三四五六七八九十]+[、．.]|[（(][二三四五六七八九十][）)])\s*(?:报名注意事项|资格审查|资格审核|资格复审|笔试|面试|考试|考核|体检|公示|聘用|薪酬|待遇|联系方式)',r'\n\s*[一二三四五六七八九十]+[、．.]']
    instructions=excerpt(doc.text,[r'报名方式',r'应聘方式',r'应聘流程',r'应聘程序',r'申请方式',r'[（(]一[）)]\s*报名'],end,'')
    if not instructions:
        pieces=re.split(r'[。\n]',doc.text)
        instructions='。\n'.join(s.strip() for s in pieces if re.search(r'(?:发送|投递|寄送|登录|进入|前往|注册)',s) and re.search(r'邮箱|邮件|招聘系统|报名系统|招聘平台|zp\.',s))
    normalized=re.sub(r'不设现场报名|不接受现场报名','',instructions)
    modes=[]
    if re.search(r'网上报名|网络报名|线上报名|在线报名|(?:登录|进入|前往)[^\n]{0,140}(?:系统|平台|zp\.)|(?:招聘|报名)(?:管理)?(?:系统|平台)[^\n]{0,80}(?:报名|投递|上传)',normalized):modes.append('在线')
    if re.search(r'采取邮件|邮件报名|电子邮件报名|(?:发送|投递|发)[^\n]{0,120}(?:邮箱|邮件)|报名邮箱|(?:发送|投递)[^\n]{0,120}@[A-Za-z]',normalized):modes.append('邮件')
    if re.search(r'邮寄报名|采取邮寄|(?:寄送|邮寄)[^\n]{0,25}报名',normalized):modes.append('邮寄')
    if '现场报名' in normalized:modes.append('现场')
    material=excerpt(doc.text,[r'(?:应聘|报名|申请)(?:时需提供的|需提交的|需提供的|所需)?材料(?:清单|包括|如下)?\s*[:：\n]',r'(?:提交|提供|准备|上传)(?:如下|以下|下列)材料\s*[:：\n]',r'需上传的材料\s*[:：\n]'],end+[r'[（(][二三四五六七八九十][）)]\s*(?:报名确认|报名注意事项|资格审查|资格审核)'],'')
    if not material and instructions and re.search(r'身份证|学历学位证|党员.*证明|学生干部.*证明|个人简历|报名表',instructions):material=instructions
    urls=list(dict.fromkeys(re.findall(r'https?://[^\s\u4e00-\u9fff)）<>，,。；;、\]】]+',instructions)))
    return {'method':' / '.join(modes) if modes else '待核实','application_details':instructions or '报名方式尚未从原文完整提取，请打开官方公告核对。','application_urls':urls,'materials':material or '材料清单尚未从原文完整提取，请打开官方公告核对报名、资格审查及岗位专属材料。'}

def parse_single(doc,source):
    text=doc.text
    if not text or EXCLUDE.search(doc.title) or not RECRUIT.search(doc.title):return []
    # GDUFS dispatch posts contain a literal single-role/count paragraph.
    explicit=re.search(r'岗位名称及名额\s*([^\n]{1,100})',text)
    role=None;count=None
    if explicit:
        m=re.search(r'(.+?)[，,]\s*(\d+)名',explicit.group(1))
        if m:role=m.group(1).strip();count=int(m.group(2))
    if not role:
        m=re.search(r'岗位名称\s*[:：]?\s*([^\n.。]{1,70}?)(?=工作内容|研究方向|\n|[.。]|$)',text)
        if m:role=m.group(1).strip()
    if not role:
        # Generic annual teacher plans / multi-role lists need their attachment, not a made-up role.
        if '计划表' in text or '具体岗位见附件' in text:return []
        for name in ['专职辅导员','辅导员','专职副研究员','副研究员','研究助理','思想政治理论课教师','学术带头人','师资博士后','科研博士后']:
            if name in doc.title or (name in text[:400] and name=='专职副研究员'):role=name;break
    if not role:return []
    named_count=re.search(r'[（(]\s*(\d+)名\s*[）)]',role)
    if named_count:
        count=int(named_count[1]);role=re.sub(r'[（(]\s*\d+名\s*[）)]','',role).strip()
    if count is None:
        m=re.search(r'(?:招聘|诚聘|副研究员|研究助理)\s*(\d+)\s*(?:名|人)',doc.title+'\n'+text[:500])
        if m:count=int(m.group(1))
    conditions=excerpt(text,[r'(?:二|三)、应聘条件',r'二、招聘条件',r'一、岗位条件',r'二、申请资格',r'一、招收条件',r'任职要求'],[r'(?:三|四)、(?:聘期待遇|薪酬|报名方式|聘用|招收学科)',r'薪资福利',r'二、岗位职责'])
    if conditions=='公告未披露':conditions=text
    duty=excerpt(text,[r'(?:一|二)、(?:招聘岗位|工作岗位|岗位职责)',r'岗位及工作内容',r'岗位职责'],[r'(?:二|三)、应聘条件',r'应聘条件',r'任职要求'],conditions)
    pay=excerpt(text,[r'(?:三|四|五)、(?:聘期待遇|薪酬待遇|工资福利待遇|薪酬及福利待遇|薪酬待遇)',r'三、薪资福利',r'三、 工资',r'薪资福利'],[r'(?:四|五|六)、(?:应聘|联系|合同)',r'应聘方式'], '公告未披露金额')
    edu=None
    # Do not upgrade a degree merely because a recommendation letter mentions a doctoral supervisor.
    for label,p in [('高中',r'高中及以上学历'),('大专',r'(?:大专|专科)(?:及以上)?学历'),('本科',r'本科(?:及以上|或硕士|毕业生|或以上)'),('硕士',r'硕士(?:研究生)?(?:及以上|毕业|学位|学历)'),('博士',r'博士(?:研究生)?(?:学位|学历|毕业|研究生)')]:
        if re.search(p,conditions):edu=label;break
    if edu is None and '博士' in conditions:edu='博士'
    if edu is None and re.search(r'学历和研究方向\s*[:：]\s*本科及以上',text):edu='本科'
    majors=['不限'] if '专业不限' in conditions else []
    m=re.search(r'(?:学历与专业[:：]?\s*[^。]*?学历[，,]|具有|所学专业为)([^。\n]{2,100}?)(?:等相关专业|相关专业|专业背景|类[，,。])',conditions)
    if m:majors=[x.strip() for x in re.split('[、，,]',m.group(1)) if x.strip()]
    party=True if re.search(r'(?:\n|[（(]一[）)]|\d\.)\s*(?:中国共产党党员|中共党员)[。；]',conditions) or '中国共产党党员。' in conditions else None
    location=excerpt(text,[r'工作地点\s*[:：]',r'具体工作地点\s*[:：]'],[r'\n',r'聘用期限',r'学历和研究方向'], '')
    area=next((d for d in ['南山区','白云区','番禺区','南海区','顺德区','禅城区'] if d in location),'区县待核实')
    job={'school':source['name'],'province':'广东省','city':source.get('city','城市待核实'),'district':area,'title':role,'department':doc.title,'count':count,'nature':'公办','degree':edu,'majors':majors,'category':'科研' if any(x in role for x in ['研究','博士后']) else '教师' if '教师' in role else '人才引进' if '带头人' in role else '行政','establishment':'劳务派遣' if '劳务派遣' in text else '合同制' if re.search(r'签订劳动合同|签订.*?劳动合同',text) else '公告未明确','salary':pay,'requirements':duty,'conditions':conditions,'source_url':doc.url,'source_title':doc.title,'published':doc.published,'official_text':text,'attachments':doc.attachments,'deadline':deadline(text),'rolling':bool(re.search(r'长期有效|长期招聘|常年接受|常年招聘|招满即止',text)),'method':'在线' if '登录' in text and ('报名' in text or '投递' in text) else '邮件','verification':'自动整理待核验','evidence':{'degree':conditions,'major':conditions,'party':conditions},'materials':excerpt(text,[r'(?:四|五)、应聘材料',r'五、应聘者请提供以下材料'],[r'(?:五|六)、应聘程序'], '未公布'),'exam':'公告要求面试 / 笔试，时间另行通知' if '面试' in text else '未公布'}
    age_lines=[line for line in conditions.splitlines() if '年龄' in line and re.search(r'\d+\s*(?:周岁|岁)',line)]
    job['eligibility']={'age_text':age_lines[0] if len(age_lines)==1 else ''}
    if job.get('deadline') and re.search(r'(?:年龄)?计算至报名截止日期',conditions):job['eligibility']['age_as_of']=job['deadline'][:10]
    job['nature']=source.get('nature','公办');job['school_level']=source.get('school_level','待核实');job['category']=category(role)
    job.update(registration(text,doc.published))
    if '专业不限' in conditions:job['majors']=['不限']
    if re.search(r'中共(?:预备)?党员|中共党员.*预备党员',conditions):job['party_required']=True
    job['salary_details']=job['salary']
    job['salary']=job['salary'][:140]+('…（详见详情）' if len(job['salary'])>140 else '')
    job['id']=hashlib.sha256((doc.url+'|'+role).encode()).hexdigest()[:20]
    return [job]

def attachment_text(raw,name):
    if name.lower().endswith(('.xls','.xlsx')):
        return '\n'.join('\t'.join(row) for _,rows in spreadsheet_rows(raw) for row in rows)
    if raw.lstrip().startswith(b'<'):
        raise ValueError('附件返回网页，可能需要人工验证码；未当作附件解析')
    if name.lower().endswith('.pdf'):
        from markitdown import MarkItDown
        text=MarkItDown().convert_stream(BytesIO(raw),file_extension='.pdf').text_content
        if len(text.strip())<40:raise ValueError('扫描附件无可提取文字，需要人工核验')
        return text
    if name.lower().endswith('.xlsx'):
        from openpyxl import load_workbook
        w=load_workbook(BytesIO(raw),data_only=True,read_only=True)
        return '\n'.join('\t'.join(str(c or '') for c in row) for s in w for row in s.values)
    raise ValueError('当前未支持此附件格式，保留原链接供人工核验')

def spreadsheet_rows(raw):
    """Read BIFF, OOXML and Excel 2003 XML; expand only explicitly merged cells."""
    def value(v):return str(int(v)) if isinstance(v,float) and v.is_integer() else str(v or '').strip()
    if raw.startswith(b'PK'):
        from openpyxl import load_workbook
        book=load_workbook(BytesIO(raw),data_only=True)
        out=[]
        for sheet in book:
            rows=[[value(c.value) for c in row] for row in sheet]
            for area in sheet.merged_cells.ranges:
                v=rows[area.min_row-1][area.min_col-1]
                for r in range(area.min_row-1,area.max_row):
                    for c in range(area.min_col-1,area.max_col):rows[r][c]=v
            out.append((sheet.title,rows))
        return out
    if raw.startswith(b'\xd0\xcf\x11\xe0'):
        import xlrd
        book=xlrd.open_workbook(file_contents=raw,formatting_info=True);out=[]
        for sheet in book.sheets():
            rows=[[value(c) for c in sheet.row_values(r)] for r in range(sheet.nrows)]
            for r0,r1,c0,c1 in sheet.merged_cells:
                v=rows[r0][c0]
                for r in range(r0,r1):
                    for c in range(c0,c1):rows[r][c]=v
            out.append((sheet.name,rows))
        return out
    from lxml import etree
    tree=etree.fromstring(raw,parser=etree.XMLParser(resolve_entities=False,no_network=True))
    ns={'s':'urn:schemas-microsoft-com:office:spreadsheet'};key='{'+ns['s']+'}'
    sheets=tree.xpath('//s:Worksheet',namespaces=ns)
    if not sheets:raise ValueError('附件不是可识别的 Excel，可能返回验证码网页；需人工核验')
    out=[]
    for sheet in sheets:
        cells={};rindex=0
        for row in sheet.xpath('./s:Table/s:Row',namespaces=ns):
            rindex=int(row.get(key+'Index',rindex+1))-1;cindex=0
            for cell in row.xpath('./s:Cell',namespaces=ns):
                cindex=int(cell.get(key+'Index',cindex+1))-1
                v=''.join(cell.xpath('./s:Data//text()',namespaces=ns)).strip()
                down=int(cell.get(key+'MergeDown','0'));across=int(cell.get(key+'MergeAcross','0'))
                for r in range(rindex,rindex+down+1):
                    for c in range(cindex,cindex+across+1):cells[r,c]=v
                cindex+=across+1
            rindex+=1
        if cells:
            height=max(r for r,c in cells)+1;width=max(c for r,c in cells)+1
            out.append((sheet.get(key+'Name','岗位表'),[[cells.get((r,c),'') for c in range(width)] for r in range(height)]))
    return out

def effective_source(doc,source):
    for name,location in source.get('schools',{}).items():
        if doc.title.startswith(name) and not AFFILIATED.search(doc.title):return {'name':name,**location}
    return source

def parse_spreadsheet_jobs(doc,source,raw,attachment):
    source=effective_source(doc,source);jobs=[]
    for sheet,rows in spreadsheet_rows(raw):
        header=next((i for i,r in enumerate(rows) if '岗位名称' in r and ('招聘人数' in r)),None)
        if header is None:continue
        aliases={'学历':'学历要求','学位':'学位要求','学历学位要求':'学历学位','学历、学位':'学历学位','招聘人数（人）':'招聘人数','专业':'专业要求','岗位要求':'其他要求','任职要求':'其他要求','部门名称':'工作部门','最低专业技术资格':'职称等级','与岗位有关的其它条件':'其他要求','专业名称及编号(须注明专业代码)':'专业要求','专业名称及编号（须注明专业代码）':'专业要求'}
        headings=[aliases.get(re.sub(r'\s','',h),re.sub(r'\s','',h)) for h in rows[header]]
        for number,row in enumerate(rows[header+1:],start=header+2):
            fields={h:row[i] if i<len(row) else '' for i,h in enumerate(headings) if h}
            role=fields.get('岗位名称','');count=fields.get('招聘人数','')
            if not role or not re.fullmatch(r'\d+',count):continue
            code=fields.get('岗位代码') or fields.get('序号') or str(number)
            degree_text=' '.join(fields.get(k,'') for k in ['学历要求','学位要求','学历学位','学历/学位'])
            degree=next((d for d in ['高中','大专','本科','硕士','博士'] if d in degree_text),None)
            if degree is None and '学士' in degree_text:degree='本科'
            major=fields.get('专业要求',fields.get('招聘专业（代码）',''))
            # A punctuation mark inside an official major name is not a separator.
            separator=r'[,，;；\n]\s*(?=[（(][AB]\d)' if re.match(r'[（(][AB]\d',major) else r'、(?=[^、]*[（(][AB]\d)'
            majors=[m.strip() for m in re.split(separator,major) if m.strip()]
            # Preserve a universal major rule exactly; never treat one unrestricted level as all levels.
            if major=='不限' or major=='研究生：不限；本科：不限':majors=['不限']
            party=fields.get('政治面貌','')
            conditions='\n'.join(f'{k}：{v}' for k,v in fields.items() if v)
            pay=excerpt(doc.text,[r'三、薪酬待遇'],[r'四、招聘'], '金额未披露，详见原文')
            job={'id':hashlib.sha256((doc.url+'|'+code+'|'+role).encode()).hexdigest()[:20],
                'school':source['name'],'province':'广东省','city':source.get('city','城市待核实'),
                'district':source.get('district','多校区 / 区县待核实'),'title':role,'code':fields.get('岗位代码') or None,
                'department':fields.get('工作部门','部门未明确'),'count':int(count),'nature':source.get('nature','待核实'),'school_level':source.get('school_level','待核实'),
                'degree':degree,'majors':majors,'category':'辅导员' if '辅导员' in role else '行政' if '工作人员' in role else '教师' if any(t in role for t in ['教师','教学岗']) else '教辅' if '教辅' in role else '专业技术' if '专业技术' in role else '行政',
                'establishment':'事业编制' if re.search(r'事业(?:单位)?编制人员',doc.text) else '公告未明确',
                'salary':'具体待遇及金额见官方公告','salary_details':pay,
                'requirements':fields.get('岗位职责',conditions),'conditions':conditions+'\n工作校区：'+source.get('location_note','岗位表未指定具体工作校区，须与招聘方确认')+'\n通用报名条件及材料见下方完整公告。',
                'party_required':True if '中共党员' in party or '中共党员' in conditions else False if party=='不限' else None,
                'evidence':{'degree':degree_text,'major':major,'party':party or fields.get('其他要求') or fields.get('职称及其它条件','')},
                'source_url':doc.url,'source_title':doc.title,'published':doc.published,'official_text':doc.text,
                'attachments':doc.attachments,'attachment_url':attachment['url'],'attachment_row':number,
                'attachment_sheet':sheet,'attachment_fields':fields,'deadline':deadline(doc.text),
                'rolling':bool(re.search(r'滚动招聘|招满为止|长期报名',doc.text)),'method':'邮件' if re.search(r'实行邮件报名|采取邮件报名',doc.text) else '在线',
                'verification':'自动整理待核验','exam':fields.get('考试方式','详见完整公告'),
                'materials':'完整公告四、招聘程序中的报名材料清单；按岗位要求提供佐证材料。',
                'vacancy_note':'初始岗位表名额，滚动招聘剩余名额须向学校核实' if '滚动招聘' in doc.text else '原岗位表名额'}
            job['eligibility']={'age_text':fields.get('年龄') or fields.get('其他要求',''),'fresh_text':fields.get('招聘对象',''),'fresh_required':False if fields.get('招聘对象')=='不限' else True if fields.get('招聘对象') in ['应届毕业生','2026年应届毕业生'] else None}
            if fields.get('招聘对象')=='2026年应届毕业生':job['eligibility']['fresh_year']=2026
            if re.search(r'年龄(?:及工作经历)?计算至报名首日',doc.text):
                interval=re.search(r'(?:应聘人员请于|首批报名时间为|报名时间为)\s*([^\n]{0,150})',doc.text)
                first=DATE.search(interval[1]) if interval else None
                if first:job['eligibility']['age_as_of']=date_value(first)[:10]
            # This official notice has a role-specific year-end period and two conflicting generic dates.
            if 'post_4898413.html' in doc.url and '2026050023' in doc.text:
                if fields.get('岗位代码')=='2026050023':job.update(deadline='2026-12-31',rolling=True)
                else:job.update(deadline=None,deadline_variants=['2026-05-28T23:59+08:00','2026-05-30'],deadline_note='原文网络报名写5月28日，其他岗位又写5月30日；均已过去，期限冲突须核实')
            location=fields.get('工作地点','')
            if location:
                job['work_location']=location
                for label,city in [('广州','广州市'),('珠海','珠海市'),('中山','中山市'),('惠州','惠州市'),('东莞','东莞市'),('佛山','佛山市'),('肇庆','肇庆市')]:
                    if label in location:job['city']=city;job['district']=location;break
            jobs.append(job)
    return jobs

def collect_document(doc,source,loader):
    source=effective_source(doc,source);jobs=[];digests=[];errors=[]
    for a in doc.attachments:
        name=a['title'].lower();path=urlsplit(a['url']).path.lower()
        is_zip=name.endswith('.zip') or path.endswith('.zip')
        if not is_zip and ('岗位' not in a['title'] or not (name.endswith(('.xls','.xlsx','.pdf')) or path.endswith(('.xls','.xlsx','.pdf')))):continue
        try:
            raw=loader(a['url']);parsed=[]
            if is_zip:
                with zipfile.ZipFile(BytesIO(raw)) as package:
                    for member in package.infolist():
                        if member.file_size>8_000_000:raise ValueError('压缩包内附件过大，需人工核验')
                        title=member.filename
                        if '岗位' in title and title.lower().endswith(('.xls','.xlsx')):
                            content=package.read(member)
                            parsed.extend(parse_spreadsheet_jobs(doc,source,content,a) or table_jobs(doc,source,spreadsheet_rows(content)))
            elif name.endswith('.pdf') or path.endswith('.pdf'):
                markdown=attachment_text(raw,'.pdf')
                raise ValueError('PDF已先转为Markdown，复杂岗位表仍须核对列对应关系；保留官方附件')
            else:parsed=parse_spreadsheet_jobs(doc,source,raw,a) or table_jobs(doc,source,spreadsheet_rows(raw))
            if not parsed:raise ValueError('岗位表未识别到完整表头和岗位行，需人工核验')
            jobs.extend(parsed);digests.append((a['url'],hashlib.sha256(raw).hexdigest()))
        except Exception as e:errors.append(a['title']+'：'+str(e)[:180])
    digest=hashlib.sha256((doc.digest+json.dumps(digests,ensure_ascii=False)).encode()).hexdigest() if digests else doc.digest
    parsed=jobs or table_jobs(doc,source,doc.tables or []) or parse_jobs(doc,source)
    info=application_info(doc)
    dates=registration(doc.text,doc.published)
    for j in parsed:
        j.update(info)
        if dates['opens'] and not j.get('opens'):j['opens']=dates['opens']
        j['schedule_evidence']=dates['schedule_evidence'];j['opens_basis']=dates['opens_basis']
        rules=j.setdefault('eligibility',{})
        if dates['opens'] and re.search(r'年龄(?:及工作经历)?计算至报名首日',doc.text):rules['age_as_of']=dates['opens'][:10]
        if dates['deadline'] and re.search(r'年龄(?:及工作经历)?计算至报名截止日',doc.text):rules['age_as_of']=dates['deadline'][:10]
        j['school_level']=source.get('school_level',j.get('school_level','待核实'))
        j['nature']=source.get('nature',j.get('nature','待核实'))
    return parsed,digest,errors

def parse_jobs(doc,source):
    if doc.url=='https://www.xhsysu.edu.cn/info/1137/16066.htm':
        # One explicitly named department row, not an invented count or separate vacancy per subject.
        if not all(t in doc.text for t in ['华阳湖','艺术设计与传媒学院','新媒体、影视','副高及以上职称者','长期招聘']):return []
        row=doc.text.split('艺术设计与传媒学院',1)[1].split('外国语学院',1)[0]
        requirements=row.split('55岁以下',1)[-1].split('具有以下条件之一即可投递',1)[0].strip()
        conditions='岗位表：具有博士学位或副高及以上职称，满足其一即可投递。基本条件另写博士学位，两处表述需向招聘方核实。\n'+requirements
        job={'id':hashlib.sha256((doc.url+'|华阳湖|艺术设计与传媒学院教师岗').encode()).hexdigest()[:20],
            'school':source['name'],'province':'广东省','city':'东莞市','district':'华阳湖校区 / 区县待核实',
            'title':'艺术设计与传媒学院教师岗','department':'华阳湖校区 · 艺术设计与传媒学院','count':None,'nature':'民办','category':'教师',
            'degree':None,'degree_display':'博士或副高职称（条款待确认）','majors':['新媒体、影视、计算机类相关专业','艺术设计学（视觉传达方向）','播音与主持艺术','服装设计','书法学'],
            'establishment':'公告未明确','salary':'未披露金额；按学校工资制度，一事一议，科研津贴须满足条件',
            'salary_details':excerpt(doc.text,[r'三、福利待遇'],[r'四、应聘流程']),
            'requirements':requirements,'conditions':conditions,'attachment_fields':{'职称等级':'博士学位或副高及以上职称，岗位表与通用条件存在差异，须确认'},
            'evidence':{'degree':conditions.split('\n')[0],'major':requirements,'party':'公告未限定党员'},'party_required':False,
            'eligibility':{'age_text':'岗位表55岁以下；通用条件原则上50岁，紧缺专业或副高及以上可放宽至55岁'},
            'source_url':doc.url,'source_title':doc.title,'published':doc.published,'official_text':doc.text,'attachments':doc.attachments,
            'deadline':None,'rolling':True,'method':'邮件','materials':excerpt(doc.text,[r'2、应聘材料'],[r'3、邮件附件']),
            'exam':'公告未明确考核时间','verification':'自动整理待核验','vacancy_note':'长期招聘，名额及当前空缺未披露，须向学院确认'}
        return [job]
    if '百人计划' not in doc.title:
        return parse_single(doc,source)
    if not all(x in doc.text for x in ['三、岗位要求','1. 教授','2. 副教授','3. 助理教授']):
        return []
    common=excerpt(doc.text,[r'二、基本条件'],[r'三、岗位要求'])
    pay=excerpt(doc.text,[r'四、薪酬待遇与支持条件'],[r'五、应聘方式'])
    jobs=[]
    for role,number,next_number in [('教授',1,2),('副教授',2,3),('助理教授',3,4)]:
        specific=excerpt(doc.text,[rf'{number}\. {role}'],[rf'{next_number}\. ',r'四、薪酬待遇'])
        salary=re.search(rf'(?<![\u4e00-\u9fff]){role}综合年薪(\d+)万元起',pay)
        conditions=common+'\n'+specific
        jobs.append({'id':hashlib.sha256((doc.url+'|'+role).encode()).hexdigest()[:20],
            'school':source['name'],'province':'广东省','city':source.get('city','城市待核实'),'district':'区县待核实',
            'title':role+'（百人计划）','department':'深圳大学百人计划','nature':'公办',
            'category':'教师','degree':'博士','majors':[],'count':None,'establishment':'公告未明确',
            'salary':f'综合年薪{salary[1]}万元起' if salary else '详见原文薪酬条款',
            'salary_details':pay,'requirements':specific,'conditions':conditions,
            'evidence':{'degree':common,'major':'公告未列具体专业，按学科发展需要','party':common},
            'source_url':doc.url,'source_title':doc.title,'published':doc.published,
            'official_text':doc.text,'attachments':doc.attachments,'deadline':None,'rolling':False,
            'method':'在线','verification':'自动整理待核验'})
    return jobs
