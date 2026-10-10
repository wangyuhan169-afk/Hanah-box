"""Private recruitment library. Python 3.12+, SQLite and official-source parsers."""
import argparse, base64, binascii, hashlib, hmac, io, json, os, sqlite3, threading, time, zipfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen, Request
from xml.sax.saxutils import escape
ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('HANAH_DB', str(ROOT / '.data/library.sqlite')))
TZ = ZoneInfo('Asia/Shanghai')
STAGES = ['考虑中','准备材料','已报名','待考试','已结束']
LOCK = threading.Lock()

def now(): return datetime.now(TZ)
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    return c

def init():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS personal(id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sources(url TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS notices(url TEXT PRIMARY KEY, body TEXT NOT NULL);
        ''')
        for s in json.loads((ROOT/'sources.json').read_text()):
            old=c.execute('SELECT body FROM sources WHERE url=?',(s['url'],)).fetchone()
            merged={**(json.loads(old['body']) if old else {}),**s}
            c.execute('INSERT OR REPLACE INTO sources VALUES (?,?)',(s['url'],json.dumps(merged,ensure_ascii=False)))

def parse_date(s):
    if not s: return None
    d = datetime.fromisoformat(s)
    return d.replace(tzinfo=TZ) if d.tzinfo is None else d.astimezone(TZ)

def advice(j):
    if j.get('rolling'): return {'date':None,'reason':'滚动招聘 / 招满即止，建议尽快投递'}
    end = parse_date(j.get('deadline'))
    if not end: return {'date':None,'reason':'截止时间待核实'}
    days = 5 if j.get('review_required') else 3
    reason = f'官方截止前{days}天，预留提交与审核时间'
    if j.get('method') == '邮寄':
        if j.get('mail_rule') not in ['寄出','送达']:
            return {'date':None,'reason':'邮寄截止按寄出还是送达计算，需核实'}
        if j['mail_rule'] == '送达' and not j.get('shipping_days'):
            return {'date':None,'reason':'请填写预计物流天数后计算'}
        days = (int(j.get('shipping_days') or 0) if j['mail_rule']=='送达' else 0) + 2
        reason = f'按{j["mail_rule"]}期限，物流与缓冲共{days}天'
    suggested = end - timedelta(days=days)
    material = parse_date(j.get('material_deadline'))
    if material and material < suggested:
        suggested = material
        reason += '；采用更早的材料提交期限'
    opening = parse_date(j.get('opens'))
    if opening and suggested < opening:
        suggested = opening
        reason += '；报名窗口较短，建议开放后尽快投递'
    exact = 'T' in j.get('deadline','') or ' ' in j.get('deadline','')
    return {'date':suggested.isoformat(timespec='minutes') if exact else suggested.date().isoformat(),
            'reason':reason + ('' if exact else '；官方未明确截止时刻，请提前完成')}

def status(j):
    if j.get('cancelled'): return '已取消'
    if j.get('deadline_variants') and all(parse_date(s).date()<now().date() for s in j['deadline_variants']):return '已截止'
    end = parse_date(j.get('deadline'))
    # Date-only deadlines include the whole calendar day, without inventing an official time.
    if end and (end.date() < now().date() if len(j['deadline'])==10 else end < now()): return '已截止'
    if j.get('rolling'): return '滚动招聘'
    opening = parse_date(j.get('opens'))
    if opening and opening > now(): return '即将报名'
    return '正在报名' if end else '截止待核实'

def match(j,p):
    if p.get('degree') or p.get('major') or p.get('birth_date') or p.get('degree_origin'):
        from eligibility import assess
        return assess(j,p,now().date().isoformat(),status(j))
    results=[]
    degree_rank={'高中':-1,'大专':0,'本科':1,'硕士':2,'博士':3}
    for field,label in [('degree','学历'),('major','专业'),('age','年龄'),('party','党员'),('fresh','应届身份'),('establishment','编制')]:
        evidence=j.get('evidence',{}).get(field) or '未录入对应原文'
        outcome='需核实'
        value=p.get(field)
        if field=='degree' and value in degree_rank and j.get('degree') in degree_rank and evidence!='未录入对应原文':
            outcome='符合' if degree_rank[value]>=degree_rank[j['degree']] else '不符合'
        if field=='major' and value and j.get('majors') and evidence!='未录入对应原文':
            outcome='符合' if value in j['majors'] or '不限' in j['majors'] else '需核实'
        if field=='party' and value in ['是','否'] and j.get('party_required') is not None and evidence!='未录入对应原文':
            outcome='不符合' if j['party_required'] and value=='否' else '符合'
        if field=='establishment' and value:
            outcome='符合' if value=='不限' or value==j.get(field) else ('不符合' if j.get(field) else '需核实')
        # Age and fresh-graduate definitions require an explicit announcement cutoff / definition.
        results.append({'field':label,'outcome':outcome,'evidence':evidence})
    summary='不符合' if any(x['outcome']=='不符合' for x in results) else ('需进一步核实' if any(x['outcome']=='需核实' for x in results) else '符合已知条件')
    return {'summary':summary,'items':results}

def reminders(j,personal):
    notes=[]
    if personal.get('stage') not in ['已报名','待考试','已结束'] and status(j) not in ['已截止','已取消']:
        d=parse_date(j.get('deadline'))
        if d and (d.date()-now().date()).days in [7,3,1,0]: notes.append(f'距官方截止{(d.date()-now().date()).days}天')
        a=advice(j); sd=parse_date(a['date'])
        if sd and sd.date()==now().date(): notes.append('今天是建议投递日')
        elif sd and sd.date()<now().date(): notes.append('已过建议时间，仍可报名，请尽快提交')
    if j.get('changes'): notes.append('公告有变更，请查看记录')
    exam=parse_date(j.get('exam_date'))
    if exam and 0 <= (exam.date()-now().date()).days <= 3: notes.append('考试临近，请确认安排')
    return notes

def state():
    with connect() as c:
        jobs=[json.loads(r['body']) for r in c.execute('SELECT body FROM jobs')]
        personal={r['id']:json.loads(r['body']) for r in c.execute('SELECT * FROM personal')}
        p=c.execute("SELECT body FROM settings WHERE key='profile'").fetchone()
        profile=json.loads(p['body']) if p else {}
        career_row=c.execute("SELECT body FROM settings WHERE key='career'").fetchone()
        career=json.loads(career_row['body']) if career_row else {}
        notices=[json.loads(r['body']) for r in c.execute('SELECT body FROM notices')]
        by_url={n['url']:n for n in notices}
        for j in jobs:
            notice=by_url.get(j.get('source_url'),{})
            j['changes']=j.get('changes',[])+notice.get('changes',[])
            if notice.get('changes') and (not j.get('last_verified') or notice['changes'][-1]['at']>j['last_verified']):
                j['verification']='变更待复核'
            j['personal']=personal.get(j['id'],{})
            j['status']=status(j); j['advice']=advice(j); j['match']=match(j,profile)
            j['reminders']=reminders(j,j['personal'])
        return {'jobs':jobs,'profile':profile,'career':career,'coverage':{'schools':sorted({j['school'] for j in jobs if j.get('verification') in ['原文已核对','已核验']}),'cities':sorted({j['city'] for j in jobs if j.get('verification') in ['原文已核对','已核验']})},'sources':[json.loads(r['body']) for r in c.execute('SELECT body FROM sources')],
                'notices':[json.loads(r['body']) for r in c.execute('SELECT body FROM notices')],'today':now().date().isoformat()}

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.href=None; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a': self.href=dict(attrs).get('href'); self.parts=[]
    def handle_data(self,data):
        if self.href is not None: self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.href is not None:
            self.links.append((self.href,''.join(self.parts).strip())); self.href=None

def fetch(url):
    with urlopen(Request(url,headers={'User-Agent':'HanahRecruitment/1.0 (personal official notice monitor)'}),timeout=15) as r:
        raw=r.read(4_000_001)
        if len(raw)>4_000_000: raise ValueError('页面过大，请人工查看')
        return raw,raw.decode(r.headers.get_content_charset() or 'utf-8',errors='replace')

def check_sources():
    from collector import read_document, recruitment_links, collect_document, effective_source, AFFILIATED
    if not LOCK.acquire(blocking=False): return
    try:
        with connect() as c: sources=[json.loads(r['body']) for r in c.execute('SELECT body FROM sources')]
        for source in sources:
            attempt=now().isoformat(timespec='seconds'); source['last_attempt']=attempt
            checks=[]; targets={}; successes=0
            for url in source.get('list_urls',[source['url']]):
                try:
                    raw,_=fetch(url); doc=read_document(raw,url)
                    for u,title in recruitment_links(doc):
                        if source.get('schools') and (AFFILIATED.search(title) or not any(title.startswith(n) for n in source['schools'])):continue
                        targets[u]=title
                    checks.append({'url':url,'ok':True,'at':attempt});successes+=1
                except Exception as e:checks.append({'url':url,'ok':False,'error':str(e)[:220],'at':attempt})
            with connect() as c:
                retained=[json.loads(r['body']) for r in c.execute('SELECT body FROM notices')]
                jobs=[json.loads(r['body']) for r in c.execute('SELECT body FROM jobs')]
            host=urlsplit(source['url']).hostname
            for n in retained:
                if urlsplit(n['url']).hostname==host:targets[n['url']]=n['title']
            for j in jobs:
                if urlsplit(j['source_url']).hostname==host:targets[j['source_url']]=j.get('source_title') or j['title']
            for url,title in targets.items():
                with connect() as c:
                    old=c.execute('SELECT body FROM notices WHERE url=?',(url,)).fetchone()
                    notice=json.loads(old['body']) if old else {'url':url,'school':source['name'],'title':title,'first_seen':attempt,'verification':'待核验','changes':[]}
                try:
                    raw,_=fetch(url);doc=read_document(raw,url)
                    if not doc.text:raise ValueError('未找到公告正文，页面结构可能变化，需核验')
                    attachment_cache={}
                    def load_attachment(u):
                        if urlsplit(u).scheme!='https' or urlsplit(u).hostname!=host:
                            raise ValueError('跨域附件需另行登记官方来源并人工核验')
                        if u not in attachment_cache:attachment_cache[u]=fetch(u)[0]
                        return attachment_cache[u]
                    parsed,digest,attachment_errors=collect_document(doc,source,load_attachment)
                    # A blocked attachment must not invalidate or erase an existing reviewed snapshot.
                    if attachment_errors:
                        notice['attachment_errors']=attachment_errors
                        if notice.get('hash'):digest=notice['hash']
                    else:notice.pop('attachment_errors',None)
                    if (notice.get('hash') and notice['hash']!=digest) or (notice.get('body_hash') and notice['body_hash']!=doc.digest):
                        notice['changes'].append({'at':attempt,'text':'公告正文或岗位附件内容变化，需要复核条件、期限与岗位'})
                    notice.update(hash=digest,body_hash=doc.digest,last_checked=attempt,error=None,attachments=doc.attachments,published=doc.published,school=effective_source(doc,source)['name'])
                    snapshot_dir=DB.parent/'snapshots';snapshot_dir.mkdir(exist_ok=True)
                    key=hashlib.sha256(url.encode()).hexdigest()[:20]
                    (snapshot_dir/(key+'.html')).write_bytes(raw)
                    for u,content in attachment_cache.items():
                        (snapshot_dir/(hashlib.sha256(u.encode()).hexdigest()[:20]+Path(urlsplit(u).path).suffix)).write_bytes(content)
                    for j in parsed:
                        with connect() as c:
                            record=c.execute('SELECT body FROM jobs WHERE id=?',(j['id'],)).fetchone()
                        previous=json.loads(record['body']) if record else None
                        if previous and previous.get('document_hash')==digest:
                            previous['last_checked']=attempt
                            with connect() as c:c.execute('UPDATE jobs SET body=? WHERE id=?',(json.dumps(previous,ensure_ascii=False),previous['id']))
                            continue
                        j.update(document_hash=digest,last_checked=attempt)
                        if previous:
                            j['verification']='变更待复核'
                            j['last_verified']=previous.get('last_verified')
                        save_job(j)
                    if not parsed:notice['verification']='待核对岗位附件或多岗位内容'
                except Exception as e:notice['error']=str(e)[:220]
                with connect() as c:c.execute('INSERT OR REPLACE INTO notices VALUES (?,?)',(url,json.dumps(notice,ensure_ascii=False)))
            source['checks']=checks;source['discovered']=len(targets)
            errors=[x['error'] for x in checks if not x['ok']]
            source['error']='；'.join(errors)[:400] if errors else None
            if successes:source['last_success']=attempt
            if not targets:source['warning']='未发现公告或栏目访问失败，不能据此认定无招聘'
            else:source.pop('warning',None)
            with connect() as c:c.execute('UPDATE sources SET body=? WHERE url=?',(json.dumps(source,ensure_ascii=False),source['url']))
    finally: LOCK.release()

def save_job(j):
    if not isinstance(j,dict): raise ValueError('岗位必须为对象')
    for k in ['school','title','source_url']:
        if not isinstance(j.get(k),str) or not j[k].strip(): raise ValueError(f'缺少 {k}')
    host=urlsplit(j['source_url']).hostname
    with connect() as c:
        registered=[json.loads(r['body']) for r in c.execute('SELECT body FROM sources')]
        allowed={host for s in registered for host in [urlsplit(s['url']).hostname,*s.get('official_hosts',[]),*[urlsplit(u).hostname for u in s.get('list_urls',[])]]}
        if urlsplit(j['source_url']).scheme!='https' or host not in allowed: raise ValueError('来源须为已登记官方域名的 HTTPS 链接')
        for key in ['deadline','opens','material_deadline','exam_date']: parse_date(j.get(key))
        if int(j.get('shipping_days') or 0) < 0: raise ValueError('物流天数不得为负')
        j.setdefault('id',hashlib.sha256((j['source_url']+'|'+j['title']+'|'+str(j.get('code',''))).encode()).hexdigest()[:20])
        old=c.execute('SELECT body FROM jobs WHERE id=?',(j['id'],)).fetchone()
        j['changes']=json.loads(old['body']).get('changes',[]) if old else []
        if old:
            previous=json.loads(old['body'])
            fields=[k for k in j if k not in ['changes','last_verified','last_checked','document_hash','snapshot_at'] and j[k]!=previous.get(k)]
            if fields: j['changes'].append({'at':now().isoformat(),'text':'岗位记录更新：'+', '.join(fields)})
        j.setdefault('verification','待核验'); j.setdefault('province','广东省')
        j.setdefault('nature','公办'); j.setdefault('salary','公告未披露')
        if j['verification'] in ['已核验','原文已核对']: j['last_verified']=now().isoformat(timespec='seconds')
        c.execute('INSERT OR REPLACE INTO jobs VALUES (?,?)',(j['id'],json.dumps(j,ensure_ascii=False)))
    return j['id']

def xlsx(jobs):
    cols=[('school','院校'),('province','省份'),('city','城市'),('district','区县'),('title','岗位'),('requirements','岗位要求'),('salary','薪资待遇'),('conditions','报名条件'),('method','报名方式'),('application_details','报名方式完整说明'),('materials','所需材料'),('opens','报名开始'),('deadline','官方截止'),('school_level','院校层次'),('schedule_evidence','日期原文依据'),('source_url','原公告'),('advice_date','建议最晚投递'),('advice_reason','计算依据'),('stage','报名进度'),('note','私人备注'),('verification','核验状态'),('status','报名状态'),('match_summary','个人资格初筛'),('match_priority','个人优先级')]
    prepared=[]
    for j in jobs:
        a=advice(j)
        prepared.append({**j,'match_summary':j.get('match',{}).get('summary','未按个人档案筛选'),'match_priority':j.get('match',{}).get('priority','未按个人档案筛选'),'advice_date':a['date'] or '待核实 / 尽快','advice_reason':a['reason'],**{k:j.get('personal',{}).get(k,'') for k in ['stage','note']}})
    rows=[[label for _,label in cols]]+[[str(j.get(k,'未公布')) for k,_ in cols] for j in prepared]
    sheet='<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    for i,row in enumerate(rows,1):
        sheet+=f'<row r="{i}">'+''.join(f'<c t="inlineStr"><is><t>{escape(v)}</t></is></c>' for v in row)+'</row>'
    sheet+='</sheetData></worksheet>'
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="招聘岗位" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml',sheet)
    return out.getvalue()

class Handler(BaseHTTPRequestHandler):
    def authorized(self):
        password = os.environ.get('HANAH_PASSWORD')
        if not password:
            return True  # Password-free operation is limited to a loopback listener.
        try:
            scheme, encoded = self.headers.get('Authorization', '').split(' ', 1)
            if scheme.lower() != 'basic':
                raise ValueError('unsupported authentication')
            credentials = base64.b64decode(encoded, validate=True).decode('utf-8')
            if hmac.compare_digest(credentials.encode(), ('hanah:' + password).encode()):
                return True
        except (ValueError, UnicodeError, binascii.Error):
            pass
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Hanah", charset="UTF-8"')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', '0')
        self.end_headers()
        return False

    def respond(self,data,status=200,kind='application/json; charset=utf-8'):
        raw=json.dumps(data,ensure_ascii=False).encode() if kind.startswith('application/json') else data
        self.send_response(status); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/healthz': return self.respond({'ok':True,'app':'hanah'})
        if not self.authorized(): return
        if path=='/api/state': return self.respond(state())
        files={'/':'index.html',**{'/'+p.name:p.name for p in (ROOT/'web').glob('*.js')},'/style.css':'style.css','/career.css':'career.css'}
        if path in files:
            name=files[path]; kind={'html':'text/html','js':'text/javascript','css':'text/css'}[name.split('.')[-1]]
            return self.respond((ROOT/'web'/name).read_bytes(),kind=kind+'; charset=utf-8')
        self.respond({'error':'未找到'},404)
    def do_POST(self):
        if not self.authorized(): return
        try:
            # Only same-origin browser writes; default server binds to loopback.
            origin=self.headers.get('Origin')
            if origin and urlsplit(origin).netloc!=self.headers.get('Host'): return self.respond({'error':'来源不允许'},403)
            size=int(self.headers.get('Content-Length','0'))
            if not 0 <= size <= 1_000_000: raise ValueError('请求过大或长度无效')
            body=json.loads(self.rfile.read(size) or '{}')
            if not isinstance(body,dict): raise ValueError('请求必须为对象')
            path=urlsplit(self.path).path
            if path=='/api/refresh':
                threading.Thread(target=check_sources,daemon=True).start(); return self.respond({'ok':True})
            if path=='/api/jobs': return self.respond({'id':save_job(body)})
            if path=='/api/export':
                jobs=[j for j in state()['jobs'] if j['id'] in body.get('ids',[])]
                return self.respond(xlsx(jobs),kind='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            with connect() as c:
                if path=='/api/profile': c.execute("INSERT OR REPLACE INTO settings VALUES ('profile',?)",(json.dumps(body,ensure_ascii=False),))
                elif path=='/api/career':
                    plan=body.get('state')
                    if not isinstance(plan,dict) or len(json.dumps(plan))>500000: raise ValueError('计划数据无效或过大')
                    c.execute("INSERT OR REPLACE INTO settings VALUES ('career',?)",(json.dumps(plan,ensure_ascii=False),))
                elif path=='/api/personal':
                    if body.get('stage') not in STAGES: raise ValueError('无效报名进度')
                    if not c.execute('SELECT 1 FROM jobs WHERE id=?',(body.get('id'),)).fetchone(): raise ValueError('岗位不存在')
                    c.execute('INSERT OR REPLACE INTO personal VALUES (?,?)',(body['id'],json.dumps(body,ensure_ascii=False)))
                else: return self.respond({'error':'未找到'},404)
            self.respond({'ok':True})
        except (ValueError,TypeError,KeyError) as e: self.respond({'error':str(e)},400)

def seed_snapshot():
    path=ROOT/'data/verified_snapshot.json'
    if not path.exists():return
    seed=json.loads(path.read_text())
    with connect() as c:
        profile_path=ROOT/'private/profile.json'
        if profile_path.exists() and not os.environ.get('HANAH_IGNORE_PROFILE'):
            c.execute("INSERT OR IGNORE INTO settings VALUES ('profile',?)",(json.dumps(json.loads(profile_path.read_text()),ensure_ascii=False),))
        for j in seed['jobs']:
            old=c.execute('SELECT body FROM jobs WHERE id=?',(j['id'],)).fetchone()
            if old:
                previous=json.loads(old['body'])
                if previous.get('document_hash')==j.get('document_hash'):
                    changed=False
                    if 'eligibility' not in previous and j.get('eligibility'):
                        previous['eligibility']=j['eligibility'];changed=True
                    if 'application_details' not in previous and j.get('application_details'):
                        previous['application_details']=j['application_details']
                        previous['application_urls']=j.get('application_urls',[]);changed=True
                        if not previous.get('changes'):previous['method']=j.get('method','待核实')
                        if previous.get('materials') in ['未公布','完整公告四、招聘程序中的报名材料清单；按岗位要求提供佐证材料。']:previous['materials']=j.get('materials',previous['materials'])
                    if changed:c.execute('UPDATE jobs SET body=? WHERE id=?',(json.dumps(previous,ensure_ascii=False),j['id']))
            c.execute('INSERT OR IGNORE INTO jobs VALUES (?,?)',(j['id'],json.dumps(j,ensure_ascii=False)))
        for n in seed['notices']:
            c.execute('INSERT OR IGNORE INTO notices VALUES (?,?)',(n['url'],json.dumps(n,ensure_ascii=False)))
        for source in seed['sources']:
            row=c.execute('SELECT body FROM sources WHERE url=?',(source['url'],)).fetchone()
            if row:
                current=json.loads(row['body'])
                if not current.get('last_attempt'):
                    c.execute('UPDATE sources SET body=? WHERE url=?',(json.dumps({**current,**source},ensure_ascii=False),source['url']))

def backup_daily():
    folder=DB.parent/'backups';folder.mkdir(exist_ok=True)
    target=folder/(now().date().isoformat()+'.sqlite')
    if target.exists():return
    temp=folder/(now().date().isoformat()+'.partial')
    with connect() as source, sqlite3.connect(temp) as destination:source.backup(destination)
    temp.replace(target)

def scheduler():
    while True:
        with connect() as c:
            rows=[json.loads(r['body']) for r in c.execute('SELECT body FROM sources')]
        if any(not s.get('last_attempt') or now()-parse_date(s['last_attempt'])>=timedelta(hours=4) for s in rows): check_sources()
        backup_daily()
        time.sleep(60)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,default=int(os.environ.get('PORT','8000'))); p.add_argument('--host',default='127.0.0.1'); p.add_argument('--check',action='store_true'); p.add_argument('--init',action='store_true'); p.add_argument('--empty',action='store_true',help='Do not preload the reviewed official snapshot (for isolated tests)'); a=p.parse_args()
    if not a.check and not a.init and a.host not in ['127.0.0.1','localhost','::1'] and not os.environ.get('HANAH_PASSWORD'):
        p.error('公网监听必须先设置 HANAH_PASSWORD；通过 HTTPS 反向代理访问。')
    init()
    if not a.empty: seed_snapshot()
    backup_daily()
    if a.check: check_sources()
    elif not a.init:
        threading.Thread(target=scheduler,daemon=True).start()
        server = ThreadingHTTPServer((a.host,a.port),Handler)
        print(f'Hanah library listening on {a.host}:{a.port}',flush=True)
        server.serve_forever()
