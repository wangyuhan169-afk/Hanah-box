"""Build a self-contained browser-editable edition without copying personal data."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
html=(root/'web/index.html').read_text()
css=(root/'web/style.css').read_text()+'\n'+(root/'web/career.css').read_text()
script=(root/'web/app.js').read_text()
adapter=(root/'web/offline.js').read_text()
html=html.replace('<link rel="stylesheet" href="/career.css">','')
html=html.replace('<link rel="stylesheet" href="/style.css">', '<style>'+css+'</style>')
html=html.replace('<div id="alert" role="status"></div>', '<aside class="offlineBanner"><strong>离线可编辑版</strong><span>在此浏览器保存 · 不自动采集 · 请定期备份</span><button id="backup">备份数据</button><button id="restore">恢复备份</button><input id="backupFile" type="file" accept=".json,application/json" hidden></aside><div id="alert" role="status"></div>')
html=html.replace('<script src="/matching.js"></script>', '<script>'+(root/'web/matching.js').read_text()+'</script>')
html=html.replace('<script src="/planning.js"></script>', '<script>'+(root/'web/planning.js').read_text()+'</script>')
html=html.replace('<script src="/directory.js"></script>', '<script>window.HANAH_DIRECTORY_DATA='+json.dumps(json.loads((root/'data/guangdong_institutions.json').read_text()),ensure_ascii=False).replace('</','<\\/')+';</script>')
for module in ['strategy','knowledge','career_ui','coverage']:
    html=html.replace(f'<script src="/{module}.js"></script>', '<script>'+(root/f'web/{module}.js').read_text()+'</script>')
html=html.replace('<script src="/opportunities.js"></script>', '<script>'+(root/'web/opportunities.js').read_text()+'</script>')
html=html.replace('<script src="/app.js"></script>', '<script>const HANAH_SOURCES='+json.dumps(json.loads((root/'sources.json').read_text()),ensure_ascii=False)+';\n'+adapter+'\n'+script+'</script>')
(root/'dist').mkdir(exist_ok=True)
(root/'dist/hanah-editable.html').write_text(html)
print('Built dist/hanah-editable.html (no user data included)')

seed=json.loads((root/'data/verified_snapshot.json').read_text())
existing={j['id'] for j in seed['jobs']}
for job in json.loads((root/'data/reviewed_positions.json').read_text()):
    if job['id'] not in existing:seed['jobs'].append(job)
real_html=html.replace('const HANAH_SOURCES=', 'const HANAH_NOTICES='+json.dumps(seed.get('notices',[]),ensure_ascii=False).replace('</','<\\/')+';\nconst HANAH_JOBS='+json.dumps(seed['jobs'],ensure_ascii=False).replace('</','<\\/')+';\nconst HANAH_SOURCES=')
real_html=real_html.replace('离线可编辑版','真实招聘岗位快照').replace('在此浏览器保存 · 不自动采集 · 请定期备份','官方快照 '+seed['snapshot_at'][:10]+' · 自动更新请使用本地运行版 · 请定期备份')
(root/'dist/hanah-recruitment-real.html').write_text(real_html)
print('Built dist/hanah-recruitment-real.html with',len(seed['jobs']),'reviewed official roles')

profile_path=root/'private/profile.json'
if profile_path.exists():
    personal_html=real_html.replace('const HANAH_JOBS=', 'const HANAH_PROFILE='+json.dumps(json.loads(profile_path.read_text()),ensure_ascii=False).replace('</','<\\/')+';\nconst HANAH_JOBS=')
    personal_html=personal_html.replace('真实招聘岗位快照','WYH 个人备考快照').replace('官方快照 ','包含个人档案，请勿公开分享 · 官方快照 ')
    (root/'dist/hanah-WYH-editable.html').write_text(personal_html)
    print('Built private WYH edition with personal profile')
