# -*- coding: utf-8 -*-
"""Private workspace documents, explicit statistics and recoverable local snapshots."""
import json,re,sqlite3,hashlib,zipfile,io
from pathlib import Path
from datetime import datetime,date,timedelta,timezone

WORKSPACE_COLUMNS={'workspace_items':('key','payload','revision','updated_at')}
class WorkspaceConflict(ValueError):pass
def init_workspace(con):con.execute('CREATE TABLE IF NOT EXISTS workspace_items(key TEXT PRIMARY KEY,payload TEXT NOT NULL,revision INTEGER NOT NULL,updated_at TEXT NOT NULL)')
def timestamp():return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='microseconds')
def validate_item(key,payload):
 if not isinstance(key,str) or not re.fullmatch(r'(preferences|note:[a-zA-Z0-9_-]{1,70}|draft:[0-9]{1,15}|course:[a-zA-Z0-9_-]{1,70}|question:[a-zA-Z0-9_-]{1,100}|recovery:[a-zA-Z0-9_-]{1,70})',key):raise ValueError('工作区项目名称不正确')
 if not isinstance(payload,dict):raise ValueError('工作区内容须为对象')
 if key.startswith(('course:','question:','recovery:')):
  from learning_tools import validate_learning
  return validate_learning(key,payload)
 if key=='preferences':
  if set(payload)-{'font','motion','focus_minutes'}:raise ValueError('偏好字段不正确')
  if payload.get('font','standard') not in ('standard','large') or payload.get('motion','system') not in ('system','reduced'):raise ValueError('阅读偏好不正确')
  if payload.get('focus_minutes',25) not in (25,40,50):raise ValueError('专注时长请选择25、40或50分钟')
 elif key.startswith('note:'):
  if set(payload)-{'title','content','tag'}:raise ValueError('笔记字段不正确')
  for k,n in [('title',80),('content',30000),('tag',40)]:
   if not isinstance(payload.get(k,''),str) or len(payload.get(k,''))>n:raise ValueError('笔记内容超出长度或格式不正确')
 elif key.startswith('draft:'):
  if set(payload)-{'content','language','tests'}:raise ValueError('作业草稿字段不正确')
  if not isinstance(payload.get('content',''),str) or len(payload.get('content',''))>40000:raise ValueError('草稿请保持在40000字以内')
  if payload.get('language','text') not in ('c','text'):raise ValueError('草稿语言不正确')
  tests=payload.get('tests',[])
  if not isinstance(tests,list) or len(tests)>5 or any(not isinstance(t,dict) or any(not isinstance(t.get(k,''),str) or len(t.get(k,''))>10000 for k in ('input','expected')) for t in tests):raise ValueError('草稿样例格式不正确')
 return payload
def workspace_get(con,key=''):
 if key:
  if not key.startswith(('course:','question:','recovery:')):validate_item(key,{})
  elif not re.fullmatch(r'(course|question|recovery):[a-zA-Z0-9_-]{1,100}',key):raise ValueError('学习资料名称不正确')
  row=con.execute('SELECT * FROM workspace_items WHERE key=?',(key,)).fetchone()
  return {'item':dict(row,payload=json.loads(row['payload'])) if row else None}
 return {'items':[dict(x,payload=json.loads(x['payload'])) for x in con.execute("SELECT * FROM workspace_items WHERE key LIKE 'note:%' ORDER BY updated_at DESC LIMIT 1000")]}
def workspace_post(con,data,delete=False):
 key=data.get('key')
 if isinstance(key,str) and key.startswith(('course:','question:','recovery:')):raise ValueError('请通过课程、题目或补救专用入口更新学习资料')
 payload=validate_item(key,data.get('payload',{}))
 if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
 old=con.execute('SELECT * FROM workspace_items WHERE key=?',(key,)).fetchone()
 if int(data.get('revision',0))!=(old['revision'] if old else 0):raise WorkspaceConflict('另一个窗口已修改这份内容。已保留你的输入，请重新载入或另存副本。')
 if key.startswith('draft:') and not con.execute('SELECT 1 FROM tasks WHERE id=?',(int(key.split(':')[1]),)).fetchone():raise ValueError('草稿对应的任务不存在')
 if delete:
  con.execute('DELETE FROM workspace_items WHERE key=?',(key,));return {'ok':True}
 if not old and key.startswith('note:') and con.execute("SELECT COUNT(*) FROM workspace_items WHERE key LIKE 'note:%'").fetchone()[0]>=1000:raise ValueError('笔记较多，请先导出归档')
 revision=(old['revision'] if old else 0)+1;updated=timestamp()
 con.execute('INSERT OR REPLACE INTO workspace_items VALUES(?,?,?,?)',(key,json.dumps(payload,ensure_ascii=False),revision,updated));return {'ok':True,'item':{'key':key,'payload':payload,'revision':revision,'updated_at':updated}}
def snapshot_database(db_path,reason='daily'):
 db_path=Path(db_path).resolve();folder=db_path.parent/'snapshots';folder.mkdir(exist_ok=True)
 stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d') if reason=='daily' else datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S-%f')
 name=reason+'-'+stamp+'.sqlite3';target=folder/name
 if not target.exists():
  source=sqlite3.connect(str(db_path),timeout=20);dest=sqlite3.connect(str(target))
  try:source.backup(dest)
  finally:dest.close();source.close()
 # Only our own direct snapshot files are eligible for bounded retention.
 files=sorted((x for x in folder.glob('*.sqlite3') if re.fullmatch(r'(daily|before-import)-[0-9-]+\.sqlite3',x.name)),key=lambda x:x.stat().st_mtime,reverse=True)
 for p in files[14:]:
  if p.resolve().parent==folder.resolve():p.unlink()
 return {'name':target.name,'created_at':timestamp(),'bytes':target.stat().st_size}
def snapshot_list(db_path):
 folder=Path(db_path).parent/'snapshots'
 return [{'name':p.name,'bytes':p.stat().st_size,'modified':datetime.fromtimestamp(p.stat().st_mtime,timezone(timedelta(hours=8))).isoformat()} for p in sorted(folder.glob('*.sqlite3'),key=lambda x:x.stat().st_mtime,reverse=True) if re.fullmatch(r'(daily|before-import)-[0-9-]+\.sqlite3',p.name)][:14]
def statistics(con):
 today=datetime.now(timezone(timedelta(hours=8))).date();days=[(today-timedelta(days=i)).isoformat() for i in range(6,-1,-1)]
 focus={x['day']:x['minutes'] for x in con.execute('SELECT day,SUM(minutes) minutes FROM focus_sessions GROUP BY day')}
 submissions=con.execute('SELECT COUNT(*) FROM submissions').fetchone()[0]
 activity={x[0] for x in con.execute('SELECT day FROM focus_sessions UNION SELECT day FROM journals')}
 activity.update(x[0][:10] for x in con.execute('SELECT created_at FROM submissions'))
 streak=0;cursor=today if today.isoformat() in activity else today-timedelta(days=1)
 while cursor.isoformat() in activity:streak+=1;cursor-=timedelta(days=1)
 done=con.execute("SELECT COUNT(*) FROM tasks WHERE status='done'").fetchone()[0]
 overdue=con.execute("SELECT COUNT(*) FROM tasks WHERE due_date<? AND status<>'done'",(today.isoformat(),)).fetchone()[0]
 return {'today':today.isoformat(),'week':[{'day':d,'minutes':focus.get(d,0)} for d in days],'week_minutes':sum(focus.get(d,0) for d in days),'active_days':sum(d in activity for d in days),'streak':streak,'submissions':submissions,'done_tasks':done,'overdue_tasks':overdue,'note':'专注、提交和小结是学习行为记录，不代表考试掌握度。'}
def full_backup(root):
 root=Path(root).resolve();stream=io.BytesIO();manifest={}
 with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
  candidates=[root/'platform.sqlite3',root/'studyforge.sqlite3',root/'companion.sqlite3']+sorted((root/'students').glob('*/studyforge.sqlite3'))
  for path in candidates:
   if not path.is_file():continue
   resolved=path.resolve()
   if root not in resolved.parents:raise ValueError('数据路径不正确')
   import tempfile
   with tempfile.TemporaryDirectory(prefix='studyforge-backup-') as tmp:
    destination=Path(tmp)/'copy.sqlite3';a=sqlite3.connect(str(path));b=sqlite3.connect(str(destination))
    try:a.backup(b)
    finally:a.close();b.close()
    data=destination.read_bytes();name='data/'+path.relative_to(root).as_posix();z.writestr(name,data);manifest[name]=hashlib.sha256(data).hexdigest()
  z.writestr('MANIFEST.json',json.dumps({'version':5,'created_at':timestamp(),'files':manifest,'restore':'关闭程序后整组恢复data；包含本机账号和全部学生，请妥善保管。'},ensure_ascii=False,indent=2))
 return stream.getvalue()
