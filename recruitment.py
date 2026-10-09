"""Evidence-preserving registration dates and public HTML job tables."""
import hashlib, re
from datetime import date

def registration(text, published=None):
    """Never interpret a sole opening date as a deadline; retain source wording."""
    candidates=[]
    for pattern in [r'(?:报名|应聘|申请)(?:截止时间|截止日期|截止)\s*[：:为]?\s*([^\n。]{1,180})',r'(?:报名时间|报名有效期|报名期限)\s*[：:为]?\s*([^。]{1,240})',r'应聘人员请于([^。]{1,180})']:
        for m in re.finditer(pattern,text):
            chunk=re.split(r'\n\s*[（(][二三四五六七八九十][）)]',m[1])[0].split('报名方式')[0].split('报名材料')[0]
            # Complete omitted year/month only within an explicit registration range.
            normalized=re.sub(r'(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?',lambda m:f'{m[1]}年{m[2]}月{m[3]}日',chunk)
            first=re.search(r'(20\d{2})年(\d{1,2})月(\d{1,2})日',normalized)
            if first:
                year,month=first[1],first[2]
                normalized=re.sub(r'(?<![年月\d])(\d{1,2})月(\d{1,2})日',lambda m:f'{year}年{m[1]}月{m[2]}日',normalized)
                normalized=re.sub(r'(?:至|到|—|~|～|\-)\s*(\d{1,2})日',lambda m:'至'+year+'年'+month+'月'+m[1]+'日',normalized)
            values=[]
            for d in re.finditer(r'(20\d{2})年(\d{1,2})月(\d{1,2})日(?:\s*(上午|下午|晚上)?\s*(\d{1,2})(?:时|点|[:：])(?:\s*(\d{1,2})分?)?)?',normalized):
                try:
                    result=date(int(d[1]),int(d[2]),int(d[3])).isoformat()
                    if d[5]:
                        hour=int(d[5])+(12 if d[4] in ['下午','晚上'] and int(d[5])<12 else 0)
                        if hour>23 or int(d[6] or 0)>59:continue
                        result+=f'T{hour:02}:{int(d[6] or 0):02}+08:00'
                    values.append(result)
                except ValueError:continue
            if not values:continue
            is_end='截止' in m[0] or bool(re.search(r'至|截至|截止|之前|日前|日\s*前',chunk))
            opening=values[0] if len(values)>1 else published[:10] if published and re.search(r'即日起|自公告发布',chunk) else None
            ending=values[-1] if len(values)>1 or is_end else None
            candidates.append({'opens':opening,'deadline':ending,'schedule_evidence':m[0].strip(),'opens_basis':'报名区间原文' if len(values)>1 else '原文即日起，采用公告发布日期' if opening else '未明确'})
            if len(values)>1:return candidates[-1]
    return candidates[0] if candidates else {'opens':None,'deadline':None,'schedule_evidence':'未识别到明确报名区间','opens_basis':'未明确'}

def category(role):
    return '辅导员' if '辅导员' in role else '教师' if re.search(r'教师|教学岗|教授|讲师',role) else '科研' if re.search(r'研究|博士后',role) else '教辅' if re.search(r'实验|教辅|图书|心理',role) else '行政'

def html_rows(raw):
    from lxml import html
    encoding='gb18030' if any(x in raw[:2000].lower() for x in [b'gb2312',b'gbk',b'gb18030']) else 'utf-8-sig'
    tree=html.fromstring(raw.decode(encoding,errors='replace'))
    result=[]
    for n,table in enumerate(tree.xpath('//table[not(.//table)]')):
        cells={}
        for r,tr in enumerate(table.xpath('./tr|./tbody/tr|./thead/tr')):
            c=0
            for td in tr.xpath('./td|./th'):
                while (r,c) in cells:c+=1
                value=' '.join(td.text_content().split())
                down=min(int(td.get('rowspan','1')),100);across=min(int(td.get('colspan','1')),30)
                for y in range(r,r+down):
                    for x in range(c,c+across):cells[y,x]=value
                c+=across
        if cells:
            width=max(c for r,c in cells)+1;height=max(r for r,c in cells)+1
            rows=[[cells.get((r,c),'') for c in range(width)] for r in range(height)]
            if width>=3:result.append(('正文岗位表'+str(n+1),rows))
    return result

def table_jobs(doc,source,tables):
    jobs=[]
    aliases={'招聘岗位':'岗位名称','岗位':'岗位名称','任教专业':'岗位名称','需求岗位':'岗位名称','岗位（职位）名称':'岗位名称','岗位名称及代码':'岗位名称','需求人数':'招聘人数','人数':'招聘人数','招聘数量':'招聘人数','招聘部门':'工作部门','教学单位':'工作部门','用人部门':'工作部门','部门':'工作部门','学历':'学历要求','学历、学位':'学历学位','学历学位要求':'学历学位','专业':'专业要求','专业及代码':'专业要求','岗位要求':'其他要求','任职条件':'其他要求','招聘要求':'其他要求','岗位条件':'其他要求','任职要求':'其他要求'}
    for sheet,rows in tables:
        headers=None;start=0
        for i,row in enumerate(rows[:10]):
            normalized=[aliases.get(re.sub(r'\s','',v),re.sub(r'\s','',v)) for v in row]
            if '岗位名称' in normalized and ('招聘人数' in normalized or '其他要求' in normalized):headers=normalized;start=i+1;break
        if headers is None:
            # A compact official table may omit a heading row: number, department,
            # role, explicit conditions, count. Require all five cells.
            usable=[row for row in rows if len(row)==5 and re.fullmatch(r'\d+',row[0]) and re.fullmatch(r'\d+',row[4]) and re.search(r'学历|学位',row[3])]
            if not usable:continue
            headers=['序号','工作部门','岗位名称','其他要求','招聘人数'];rows=usable;start=0
        for num,row in enumerate(rows[start:],start=start+1):
            f={h:row[i] for i,h in enumerate(headers) if i<len(row) and h}
            role=f.get('岗位名称','');count=f.get('招聘人数','')
            if not role or len(role)>80 or not re.fullmatch(r'\d+|若干|多名|不限',count):continue
            conditions='\n'.join(k+'：'+v for k,v in f.items() if v)
            degree_text=' '.join(f.get(k,'') for k in ['学历要求','学位要求','学历学位']) or f.get('其他要求','')
            degree=next((d for d,p in [('大专',r'大专|专科'),('本科',r'本科|学士'),('硕士',r'硕士'),('博士',r'博士')] if re.search(p,degree_text)),None)
            teaching=sheet.startswith('正文岗位表') and '任教专业' in rows[0]
            if teaching:role+='教师'
            major=f.get('专业要求','') or (f.get('岗位名称','') if teaching else '');party=f.get('政治面貌','') or f.get('其他要求','')
            code=f.get('岗位代码') or f.get('序号') or str(num)
            jobs.append({'id':hashlib.sha256((doc.url+'|'+code+'|'+role).encode()).hexdigest()[:20], 'school':source['name'],'city':source.get('city','城市待核实'),'province':'广东省','district':source.get('district','工作校区待核实'),'nature':source.get('nature','待核实'),'school_level':source.get('school_level','待核实'),'title':role,'category':category(role),'department':f.get('工作部门','部门待核实'),'code':f.get('岗位代码'),'count':int(count) if count.isdigit() else None,'degree':degree,'majors':['不限'] if '专业不限' in conditions or major=='不限' else [major] if major else [],'conditions':conditions+'\n通用要求见官方公告','requirements':f.get('岗位职责',conditions),'party_required':True if '中共党员' in party or '预备党员' in party else False if f.get('政治面貌')=='不限' else None,'evidence':{'degree':degree_text,'major':major or ('专业不限' if '专业不限' in conditions else ''),'party':party},'eligibility':{'age_text':f.get('年龄','') or f.get('其他要求',''),'fresh_text':f.get('招聘对象','')},'establishment':'合同制' if re.search(r'合同制|非事业编制',doc.title+doc.text) else '公告未明确','salary':'金额与具体待遇见官方公告','source_url':doc.url,'source_title':doc.title,'published':doc.published,'official_text':doc.text,'attachments':doc.attachments,'attachment_fields':f,'attachment_sheet':sheet,'attachment_row':num,'verification':'自动整理待核验','rolling':bool(re.search(r'长期招聘|长期有效|招满即止|招满为止',doc.text)),'exam':f.get('考试方式','详见官方公告'),**registration(doc.text,doc.published)})
    return jobs
