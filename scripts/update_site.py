"""Collect official announcements in an isolated database; never read private user data."""
import json,os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory() as folder:
 os.environ['HANAH_DB']=str(Path(folder)/'public.sqlite')
 os.environ['HANAH_IGNORE_PROFILE']='1'
 import app
 app.init();app.seed_snapshot();app.check_sources()
 with app.connect() as c:
  jobs=[json.loads(r['body']) for r in c.execute('SELECT body FROM jobs')]
  sources=[json.loads(r['body']) for r in c.execute('SELECT body FROM sources')]
  notices=[json.loads(r['body']) for r in c.execute('SELECT body FROM notices')]
 for j in jobs:
  for k in ['personal','match','_local_edit']:j.pop(k,None)
 for j in jobs:
  notice=next((n for n in notices if n['url']==j['source_url']),{})
  if any(not j.get('last_verified') or n['at']>j['last_verified'] for n in notice.get('changes',[])):j['verification']='变更待复核'
 reviewed=[j for j in jobs if j.get('verification') in ['原文已核对','已核验']]
 result={'version':1,'snapshot_at':app.now().isoformat(timespec='seconds'),'jobs':jobs,'sources':sources,'notices':notices,'coverage':{'verified_schools':sorted({j['school'] for j in reviewed}),'verified_cities':sorted({j['city'] for j in reviewed})}}
 (ROOT/'data/verified_snapshot.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print('Public collection completed:',len(jobs),'records;',sum(bool(s.get('error')) for s in sources),'sources report access errors')
