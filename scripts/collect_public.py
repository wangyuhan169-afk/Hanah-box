"""Bounded, concurrent collection. Preserve historical records and unresolved notices."""
import concurrent.futures,hashlib,json,sys,re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from collector import read_document,recruitment_links,collect_document,effective_source,AFFILIATED
from recruitment import registration
STAMP=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')

def merge_job(previous,job):
    if not previous:return job
    if previous.get('verification') not in ['原文已核对','已核验','变更待复核']:
        # Reparse unchanged documents when parser capabilities improve.
        return {**job,'changes':previous.get('changes',[])}
    if previous.get('document_hash')==job['document_hash']:
        previous.update(last_checked=STAMP)
        for key in ['opens','opens_basis','schedule_evidence','school_level']:
            if not previous.get(key):previous[key]=job.get(key)
    else:
        previous.update(last_checked=STAMP,verification='变更待复核')
        previous.setdefault('changes',[]).append({'at':STAMP,'text':'官方内容已变化，保留原核对条件并等待复核'})
    return previous

def deduplicate(rows):
    unique={};result=[]
    for job in rows:
        # Shared official attachment, sheet and row identify the same advertised post.
        url=job.get('attachment_url','');parts=urlsplit(url)
        fileid=parse_qs(parts.query).get('wbfileid')
        attachment=(parts.hostname,parts.path,fileid[0]) if fileid else url
        key=(job['school'],attachment,job.get('attachment_sheet'),job.get('attachment_row'),job['title'],job.get('opens'))
        if not job.get('attachment_url') or key not in unique:
            result.append(job)
            if job.get('attachment_url'):unique[key]=job
        else:
            existing=unique[key]
            existing['source_urls']=list(dict.fromkeys([existing['source_url'],*existing.get('source_urls',[]),job['source_url']]))
            existing['merged_ids']=list(dict.fromkeys([*existing.get('merged_ids',[]),job['id']]))
    return result

def fetch(url):
    with urlopen(Request(url,headers={'User-Agent':'HanahRecruitment/2.0 (public official notice monitor)'}),timeout=12) as response:
        if urlsplit(response.url).scheme!='https':raise ValueError('跳转至非HTTPS链接，保留人工核验入口')
        raw=response.read(8_000_001)
        if len(raw)>8_000_000:raise ValueError('附件超过8MB，保留人工核验入口')
        return raw

def collect(source):
    source=dict(source);source['last_attempt']=STAMP;targets={};checks=[];found=[];notices=[]
    for url in source.get('list_urls',[source['url']])[:8]:
        try:
            doc=read_document(fetch(url),url)
            for u,t in recruitment_links(doc):
                if source.get('schools') and (AFFILIATED.search(t) or not any(t.startswith(n) for n in source['schools'])):continue
                targets[u]=t
            checks.append({'url':url,'ok':True,'at':STAMP})
        except Exception as exc:checks.append({'url':url,'ok':False,'error':str(exc)[:180],'at':STAMP})
    # Explicit official URLs are retained even if a list page omits them.
    targets={**{url:targets.get(url,'官方公告待读取') for url in source.get('seed_urls',[])},**targets}
    for url,title in list(targets.items())[:source.get('max_announcements',24)]:
        notice={'url':url,'title':title,'school':source['name'],'first_seen':STAMP,'verification':'待核验','changes':[]}
        try:
            doc=read_document(fetch(url),url)
            if AFFILIATED.search(doc.title):continue
            host=urlsplit(source['url']).hostname
            def attachment(u):
                if urlsplit(u).scheme!='https' or urlsplit(u).hostname not in [host,urlsplit(doc.url).hostname,*source.get('official_hosts',[]),*source.get('attachment_hosts',[])]:raise ValueError('附件域名尚未登记，须人工核验')
                return fetch(u)
            jobs,digest,errors=collect_document(doc,source,attachment)
            notice.update(title=doc.title,school=effective_source(doc,source)['name'],published=doc.published,last_checked=STAMP,hash=digest,body_hash=doc.digest,attachments=doc.attachments,attachment_errors=errors,parsed_jobs=len(jobs),schedule=registration(doc.text,doc.published))
            if not jobs:notice['verification']='待核对岗位附件或正文结构'
            for job in jobs:
                job.update(document_hash=digest,last_checked=STAMP)
                found.append(job)
        except Exception as exc:notice['error']=str(exc)[:220]
        notices.append(notice)
    source.update(checks=checks,discovered=len(targets),parsed_jobs=len(found),unresolved_notices=sum(not n.get('parsed_jobs') or bool(n.get('attachment_errors')) or bool(n.get('error')) for n in notices))
    errors=[c['error'] for c in checks if not c['ok']]
    source['error']='；'.join(errors)[:400] if errors else None
    if any(c['ok'] for c in checks):source['last_success']=STAMP
    source['coverage_state']='已有结构化岗位' if found else '有公告待解析' if targets else '栏目访问失败' if source['error'] else '栏目未发现公告'
    print(source['name'],len(found),'岗位 /',source['unresolved_notices'],'待核验公告',flush=True)
    return source,found,notices

def main():
    sources=json.loads((ROOT/'sources.json').read_text(encoding='utf-8'))
    old=json.loads((ROOT/'data/verified_snapshot.json').read_text(encoding='utf-8'))
    jobs={j['id']:j for j in old['jobs']};notices={n['url']:n for n in old.get('notices',[])};checked=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for source,found,discovered in pool.map(collect,sources):
            checked.append(source)
            for notice in discovered:
                previous=notices.get(notice['url'],{})
                notice['first_seen']=previous.get('first_seen',notice['first_seen']);notice['changes']=previous.get('changes',[])
                if previous.get('hash') and previous['hash']!=notice.get('hash') and not notice.get('error'):notice['changes'].append({'at':STAMP,'text':'官方正文或附件变更，请复核'})
                notices[notice['url']]=notice
            for job in found:
                previous=jobs.get(job['id'])
                jobs[job['id']]=merge_job(previous,job)
    metadata={s['name']:s for s in sources}
    for source in sources:
        for name,location in source.get('schools',{}).items():metadata.setdefault(name,location)
    for j in jobs.values():
        for key in ['personal','match','_local_edit']:j.pop(key,None)
        meta=metadata.get(j['school'],{})
        j['school_level']=meta.get('school_level',j.get('school_level','待核实'))
        if meta.get('nature'):j['nature']=meta['nature']
        dates=registration(j.get('official_text',''),j.get('published'))
        if not j.get('opens'):j['opens']=dates['opens']
        j.setdefault('opens_basis',dates['opens_basis']);j.setdefault('schedule_evidence',dates['schedule_evidence'])
        j['collected_at']=j.get('last_checked') or j.get('last_verified') or old['snapshot_at']
    rows=deduplicate(jobs.values())
    reviewed=[j for j in rows if j.get('verification') in ['原文已核对','已核验']]
    result={'version':1,'snapshot_at':STAMP,'jobs':rows,'sources':checked,'notices':list(notices.values()),'coverage':{'verified_schools':sorted({j['school'] for j in reviewed}),'verified_cities':sorted({j['city'] for j in reviewed})}}
    target=ROOT/'data/verified_snapshot.json';temp=target.with_suffix('.tmp')
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(target)
    print('Snapshot:',len(jobs),'jobs;',len(checked),'source checks')
if __name__=='__main__':main()
