"""Open the private local application; no hosting account or public sharing."""
import argparse,signal,json,subprocess,sys,time,urllib.error,urllib.request,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--no-browser',action='store_true');p.add_argument('--port',type=int,default=8000);a=p.parse_args()
url=f'http://127.0.0.1:{a.port}'
try:
 response=json.load(urllib.request.urlopen(url+'/healthz',timeout=1))
 if response.get('app')=='hanah':
  print('招聘库已经运行，正在打开。')
  if not a.no_browser:webbrowser.open(url)
  sys.exit(0)
except (OSError,ValueError):pass
process=subprocess.Popen([sys.executable,str(ROOT/'app.py'),'--port',str(a.port)],cwd=ROOT)
def stop_on_signal(*_):raise KeyboardInterrupt
signal.signal(signal.SIGTERM,stop_on_signal)
try:
 for _ in range(100):
  if process.poll() is not None:raise RuntimeError('启动失败，请检查上方错误或端口占用。')
  try:
   response=json.load(urllib.request.urlopen(url+'/healthz',timeout=1))
   if response.get('app')=='hanah':break
  except (OSError,ValueError):pass
  time.sleep(.2)
 else:raise RuntimeError('启动等待超时。')
 print('网页已启动。此窗口保持打开时，每4小时自动更新；下次启动会补查。关闭前请保留数据备份。')
 if not a.no_browser:webbrowser.open(url)
 process.wait()
except KeyboardInterrupt:pass
finally:
 if process.poll() is None:process.terminate();process.wait()
