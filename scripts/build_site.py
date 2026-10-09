"""Build the public static site without any private profile, records, or credentials."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(ROOT/'scripts/build_offline.py')],check=True)
text=(ROOT/'dist/hanah-recruitment-real.html').read_text()
bootstrap=(ROOT/'web/site_boot.js').read_text()
text=text.replace('const HANAH_JOBS=',bootstrap+'\nconst HANAH_JOBS=',1)
text=text.replace('真实招聘岗位快照','广东高校招聘 · 浏览器版')
text=text.replace('官方快照 '+json.loads((ROOT/'data/verified_snapshot.json').read_text())['snapshot_at'][:10]+' · 自动更新请使用本地运行版 · 请定期备份','<span id="snapshotInfo">正在同步官方快照</span> · 个人编辑仅保存在本浏览器 · 请定期备份')
text=text.replace('<meta name="viewport"','<meta name="referrer" content="no-referrer"><meta http-equiv="Content-Security-Policy" content="default-src \'self\'; script-src \'self\' \'unsafe-inline\'; style-src \'self\' \'unsafe-inline\'; img-src \'self\' data:; connect-src \'self\'; object-src \'none\'; base-uri \'none\'; form-action \'none\'"><meta name="viewport"')
finish="""
document.querySelector('#refresh').textContent='同步最新快照';
document.querySelector('#refresh').onclick=async()=>{try{await window.HANAH_SITE.refresh();await load();message('最新快照已同步；官网采集由定时任务执行，新增内容仍须核验。')}catch{message('同步失败，已有岗位与个人记录保留。')}};
document.querySelector('#sourcesPanel .sub').textContent='定时任务检查配置官网并更新公开快照；访问失败和新内容待核验会保留。同步按钮读取最新快照。个人档案、收藏及备注不会发送到网站。';
window.HANAH_SITE.due().then(()=>load()).catch(()=>{});
setInterval(()=>window.HANAH_SITE.due().then(()=>load()).catch(()=>{}),300000);
"""
text=text.replace('</body>','<script>'+finish+'</script></body>')
out=ROOT/'site';out.mkdir(exist_ok=True)
(out/'index.html').write_text(text)
(out/'snapshot.json').write_bytes((ROOT/'data/verified_snapshot.json').read_bytes())
(out/'.nojekyll').write_text('')
profile=ROOT/'private/profile.json'
if profile.exists():
 private=json.loads(profile.read_text())
 for field in ['name','birth_date','degree_school','undergrad_school','student_leadership','work_experience','leadership_note']:
  value=private.get(field)
  if value and value in text:raise RuntimeError('Private profile field leaked into public site: '+field)
 snapshot=json.loads((out/'snapshot.json').read_text())
 if 'profile' in snapshot or any(any(k in j for k in ['personal','match','_local_edit']) for j in snapshot['jobs']):raise RuntimeError('Public snapshot includes private record fields')
print('Public site:',len(json.loads((out/'snapshot.json').read_text())['jobs']),'positions; private profile excluded')
