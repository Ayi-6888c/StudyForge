# -*- coding: utf-8 -*-
"""Windows native notification + current-user scheduled task. No GPT or remote calls."""
import json,os,re,sys,subprocess,hashlib,threading,uuid,sqlite3
from pathlib import Path
from datetime import datetime,date,timedelta,timezone
from contextlib import contextmanager
TZ=timezone(timedelta(hours=8));LOCK=threading.RLock()
DEFAULT={'enabled':False,'time':'20:30','start_date':'2026-10-25','stop_date':'','completed':False,'last_sent_day':'','last_result':None}
class DesktopReminder:
 def __init__(self,data_dir,assets_dir,app_dir,launch):
  self.data=Path(data_dir).resolve();self.assets=Path(assets_dir).resolve();self.app=Path(app_dir).resolve();self.launch=[str(x) for x in launch]
  self.key=hashlib.sha256(str(self.app).casefold().encode('utf8')).hexdigest()[:12];self.appid='StudyForge.Local.'+self.key;self.task='StudyForge.LocalReminder.'+self.key;self.protocol='studyforge-'+self.key
  self.config=self.data/'desktop-reminder.json';self.shortcut=Path(os.environ.get('APPDATA',''))/'Microsoft/Windows/Start Menu/Programs'/('拾光学习-'+self.key+'.lnk')
 def read(self):
  if not self.config.exists():return dict(DEFAULT)
  try:
   d=json.loads(self.config.read_text(encoding='utf8'));return dict(DEFAULT,**d)
  except (ValueError,OSError):raise ValueError('本机提醒设置读取失败，请先保留原文件后检查')
 def write(self,c):
  self.data.mkdir(parents=True,exist_ok=True);p=self.config.with_name('desktop-reminder-'+uuid.uuid4().hex+'.tmp');p.write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf8');os.replace(str(p),str(self.config))
 @contextmanager
 def locked(self):
  import msvcrt
  self.data.mkdir(parents=True,exist_ok=True)
  with LOCK:
   with open(self.data/'desktop-reminder.lock','a+b') as f:
    f.seek(0,2)
    if f.tell()==0:f.write(b'0');f.flush()
    f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_LOCK,1)
    try:yield
    finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
 def ps(self,operation,**fields):
  if os.name!='nt':raise ValueError('本机通知使用Windows桌面组件')
  exe=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
  args=[str(exe),'-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File',str(self.assets/'windows_reminder.ps1'),'-Operation',operation,'-AppId',self.appid,'-TaskName',self.task]
  for k,v in fields.items():
   if v is not None and str(v):args.extend(['-'+k,str(v)])
  p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,creationflags=0x08000000)
  if p.returncode:raise ValueError('Windows本机提醒操作未完成：'+p.stderr.decode('utf8','replace').strip()[:800])
  try:return json.loads(p.stdout.decode('utf-8-sig').strip())
  except ValueError:raise ValueError('Windows本机提醒返回格式不正确')
 def validate(self,d):
  if not isinstance(d,dict) or set(d)-{'enabled','time','start_date','stop_date','completed'}:raise ValueError('提醒设置字段不正确')
  c=self.read()
  for k in ('enabled','completed'):
   if type(d.get(k,c[k])) is not bool:raise ValueError('提醒开关格式不正确')
  c.update(d)
  if not isinstance(c['time'],str) or not re.fullmatch(r'([01][0-9]|2[0-3]):[0-5][0-9]',c['time']):raise ValueError('提醒时间请填写24小时制')
  start=date.fromisoformat(c['start_date'])
  if start<date(2026,10,25):raise ValueError('学习提醒从2026年10月25日起开始')
  if c['stop_date'] and date.fromisoformat(c['stop_date'])<start:raise ValueError('停止日期须晚于开始日期')
  if c['completed']:c['enabled']=False
  return c
 def identity(self):
  import pythoncom,winreg
  from win32com.shell import shell
  from win32com.propsys import propsys,pscon
  pythoncom.CoInitialize()
  try:
   link=pythoncom.CoCreateInstance(shell.CLSID_ShellLink,None,pythoncom.CLSCTX_INPROC_SERVER,shell.IID_IShellLink)
   link.SetPath(self.launch[0]);link.SetArguments(subprocess.list2cmdline(self.launch[1:]+['--desktop-open','--reminder-data',str(self.data)]));link.SetWorkingDirectory(str(self.app));link.SetDescription('拾光学习 · 本机学习提醒')
   if (self.app/'studyforge.ico').exists():link.SetIconLocation(str(self.app/'studyforge.ico'),0)
   store=link.QueryInterface(propsys.IID_IPropertyStore);store.SetValue(pscon.PKEY_AppUserModel_ID,propsys.PROPVARIANTType(self.appid));store.Commit();self.shortcut.parent.mkdir(parents=True,exist_ok=True);link.QueryInterface(pythoncom.IID_IPersistFile).Save(str(self.shortcut),0)
  finally:pythoncom.CoUninitialize()
  # Only our path-derived app/protocol keys are registered, under the current Windows user.
  for path,values in [('Software\\Classes\\AppUserModelId\\'+self.appid,{'DisplayName':'拾光学习'}),('Software\\Classes\\'+self.protocol,{'':'URL:拾光学习','URL Protocol':''}),('Software\\Classes\\'+self.protocol+'\\shell\\open\\command',{'':subprocess.list2cmdline(self.launch+['--desktop-open','--reminder-data',str(self.data)])+' "%1"'})]:
   with winreg.CreateKey(winreg.HKEY_CURRENT_USER,path) as key:
    for name,value in values.items():winreg.SetValueEx(key,name,0,winreg.REG_SZ,value)
 def install(self,c):
  self.identity();start=c['start_date']+'T'+c['time']+':00+08:00';end=c['stop_date']+'T00:00:00+08:00' if c['stop_date'] else ''
  return self.ps('install',Executable=self.launch[0],Arguments=subprocess.list2cmdline(self.launch[1:]+['--desktop-reminder','--reminder-data',str(self.data)]),StartBoundary=start,EndBoundary=end)
 def status(self):
  with self.locked():c=self.read()
  task=self.ps('status') if c['enabled'] else {'registered':False,'task_name':self.task}
  return {'config':c,'task':task,'scope':'这台Windows电脑共用的本机提醒；通知不展示学生私人作业。','note':'通过Windows通知中心提醒，不向GPT聊天发消息，不请求AI。电脑需开机并登录；勿扰模式可能只保留在通知中心。错过后仅在当晚2小时内补发，不唤醒电脑。'}
 def configure(self,d):
  with self.locked():
   old=self.read();c=self.validate(d)
   if c['enabled']:
    try:task=self.install(c);self.write(c)
    except Exception:
     if old['enabled']:
      try:self.install(old)
      except Exception:pass
     else:
      try:self.ps('remove')
      except Exception:pass
     raise
   else:
    self.write(c);task=self.ps('remove')
   return {'ok':True,'config':c,'task':task}
 def decision(self,c,now):
  now=now.astimezone(TZ);day=now.date().isoformat()
  if not c['enabled'] or c['completed']:return 'disabled'
  if day<c['start_date']:return 'before_start'
  if c['stop_date'] and day>=c['stop_date']:return 'after_stop'
  due=datetime.combine(now.date(),datetime.strptime(c['time'],'%H:%M').time(),TZ);minutes=(now-due).total_seconds()/60
  if not 0<=minutes<=120:return 'outside_evening_window'
  if c['last_sent_day']==day:return 'already_sent_today'
  return 'due'
 def run(self,test=False,now=None):
  with self.locked():
   c=self.read();moment=now or datetime.now(TZ);why='test' if test else self.decision(c,moment)
   if why not in ('due','test'):return {'ok':True,'sent':False,'reason':why}
   self.identity();tag=('test' if test else moment.astimezone(TZ).strftime('%Y%m%d'))+uuid.uuid4().hex[:6]
   result=self.ps('notify',Launch=self.protocol+'://today',Title='拾光学习 · 测试通知' if test else '今晚的学习，留一份真实记录。',Body='本机提醒已接通。正式学习提醒从10月25日起生效，不会向GPT聊天发消息。' if test else 'C语言：代码或笔试答案、3组测试和错因；英语：完成情况。点击打开软件，查看今日安排。',Tag=tag)
   result.update({'tested':test,'at':moment.astimezone(TZ).isoformat(),'task_name':self.task})
   if not test:
    if result.get('accepted'):c['last_sent_day']=moment.astimezone(TZ).date().isoformat()
    c['last_result']=result;self.write(c)
   return dict(result,ok=True,sent=result.get('accepted',False))
 def remove(self):
  import winreg
  result=self.configure({'enabled':False})
  # Delete our known leaf keys only. No recursive filesystem operations.
  for path in ('Software\\Classes\\'+self.protocol+'\\shell\\open\\command','Software\\Classes\\'+self.protocol+'\\shell\\open','Software\\Classes\\'+self.protocol+'\\shell','Software\\Classes\\'+self.protocol,'Software\\Classes\\AppUserModelId\\'+self.appid):
   try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,path)
   except FileNotFoundError:pass
  if self.shortcut.exists():self.shortcut.unlink()
  return result

def cli():
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--desktop-reminder',action='store_true');parser.add_argument('--desktop-reminder-remove',action='store_true');parser.add_argument('--desktop-open',action='store_true');parser.add_argument('--reminder-data');args,extra=parser.parse_known_args()
 frozen=getattr(sys,'frozen',False);app=Path(sys.executable if frozen else __file__).resolve().parent;assets=Path(getattr(sys,'_MEIPASS',app));data=Path(args.reminder_data or os.environ.get('STUDYFORGE_DATA_DIR',str(app/'data')));launch=[sys.executable] if frozen else [sys.executable,str(app/'app.py')];service=DesktopReminder(data,assets,app,launch)
 try:
  if args.desktop_open:
   import urllib.request
   from desktop_window import open_window
   from urllib.parse import urlparse
   try:
    info=json.loads((data/'desktop-server.json').read_text(encoding='utf8'));url=info['url'];parts=urlparse(url)
    if parts.scheme!='http' or parts.hostname!='127.0.0.1' or parts.username or parts.path!='/':raise ValueError('invalid local URL')
    with urllib.request.urlopen(url+'desktop.js',timeout=1) as response:
     if response.status!=200 or b'const desktopUI=' not in response.read():raise ValueError('not study app')
    open_window(url+'?view=today')
   except Exception:
    env=dict(os.environ,STUDYFORGE_DATA_DIR=str(data));subprocess.Popen(launch,env=env,creationflags=0x08000000)
   result={'opened':True}
  else:result=service.remove() if args.desktop_reminder_remove else service.run()
  output=json.dumps(result,ensure_ascii=False)
  if sys.stdout:print(output)
  return 0
 except Exception as e:
  data.mkdir(parents=True,exist_ok=True);(data/'desktop-reminder-error.txt').write_text(str(e),encoding='utf8')
  if sys.stderr:print(str(e),file=sys.stderr)
  return 1
