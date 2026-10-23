# -*- coding: utf-8 -*-
"""V6: private courses, capacity-aware recovery and question annotations. No network calls."""
import json,re,hashlib,uuid
from datetime import date,timedelta,datetime,timezone
from urllib.parse import urlparse
TAGS=('概念不清','边界条件','输入输出','语法细节','算法思路','指针内存','审题粗心')
STATUS=('todo','learning','watched','practiced')
def stamp():return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='microseconds')
def text(v,n):return isinstance(v,str) and len(v)<=n
def validate_learning(key,p):
 if not isinstance(p,dict):raise ValueError('学习资料格式不正确')
 if key.startswith('course:'):
  if set(p)-{'title','provider','url','subject_id','track','archived','chapters'}:raise ValueError('课程字段不正确')
  if not text(p.get('title',''),100) or not text(p.get('provider',''),100) or not text(p.get('url',''),2000):raise ValueError('课程名称或链接过长')
  u=p.get('url','');parsed=urlparse(u)
  if u and (parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password):raise ValueError('课程链接请填写普通 http/https 地址')
  if type(p.get('subject_id',0)) is not int or p.get('track','other') not in ('c','english','other') or type(p.get('archived',False)) is not bool:raise ValueError('课程学科或状态不正确')
  ch=p.get('chapters',[])
  if not isinstance(ch,list) or len(ch)>200:raise ValueError('每门课程最多200章')
  seen=set()
  for x in ch:
   if not isinstance(x,dict) or set(x)-{'id','title','minutes','module','status','note'}:raise ValueError('章节字段不正确')
   if not re.fullmatch(r'[a-zA-Z0-9_-]{1,50}',str(x.get('id',''))) or x['id'] in seen:raise ValueError('章节标识重复或不正确')
   seen.add(x['id'])
   if not text(x.get('title',''),160) or not x.get('title','').strip() or not text(x.get('note',''),3000) or not text(x.get('module',''),40):raise ValueError('章节标题或笔记不正确')
   if type(x.get('minutes')) is not int or not 5<=x['minutes']<=240 or x.get('status') not in STATUS:raise ValueError('章节时长或进度不正确')
 elif key.startswith('question:'):
  if set(p)-{'favorite','tags','note'} or type(p.get('favorite',False)) is not bool or not text(p.get('note',''),1500):raise ValueError('题目笔记格式不正确')
  if not isinstance(p.get('tags',[]),list) or any(t not in TAGS for t in p.get('tags',[])) or len(p.get('tags',[]))!=len(set(p.get('tags',[]))):raise ValueError('错因标签不正确')
 elif key.startswith('recovery:'):
  if set(p)-{'moves','before_hash','after_hash','status','created_at','options'} or p.get('status') not in ('active','undone','superseded'):raise ValueError('补救记录格式不正确')
  if not isinstance(p.get('moves'),list) or len(p['moves'])>20000:raise ValueError('补救记录过长')
  for x in p['moves']:
   if not isinstance(x,dict) or set(x)!={'id','before','after'} or type(x['id']) is not int:raise ValueError('补救任务格式不正确')
   date.fromisoformat(x['before']);date.fromisoformat(x['after'])
  for k in ('before_hash','after_hash'):
   if not re.fullmatch('[a-f0-9]{64}',str(p.get(k,''))):raise ValueError('补救校验值不正确')
  if not text(p.get('created_at',''),100) or not isinstance(p.get('options'),dict):raise ValueError('补救快照不正确')
 return p

def all_items(con,prefix):return [dict(r,payload=json.loads(r['payload'])) for r in con.execute('SELECT * FROM workspace_items WHERE key LIKE ? ORDER BY updated_at DESC',(prefix+':%',))]
def fetch(con,key):
 row=con.execute('SELECT * FROM workspace_items WHERE key=?',(key,)).fetchone();return dict(row,payload=json.loads(row['payload'])) if row else None
def write(con,key,p,revision):
 from customer_workspace import WorkspaceConflict
 old=fetch(con,key)
 if type(revision) is not int or revision!=(old['revision'] if old else 0):raise WorkspaceConflict('另一个窗口已修改这份学习资料。输入仍保留，请刷新后再保存。')
 validate_learning(key,p);rev=revision+1;ts=stamp();con.execute('INSERT OR REPLACE INTO workspace_items VALUES(?,?,?,?)',(key,json.dumps(p,ensure_ascii=False),rev,ts));return {'key':key,'payload':p,'revision':rev,'updated_at':ts}
def allowed_questions(con,engine):
 from student_platform import route
 r=route(con)
 if not r or not r['offering'].get('learning_pack_id'):return {}
 return {q['id']:q for q in engine.available(engine.pack(engine.profile(con)))}
def library(con,engine):
 allowed=allowed_questions(con,engine);cards=[]
 for item in all_items(con,'question'):
  q=allowed.get(item['key'][9:])
  if q:cards.append(dict(item,question=engine.public_question(q)))
 courses=all_items(con,'course')
 for c in courses:c['linked_tasks']={x['source'].split(':')[-1]:dict(x) for x in con.execute('SELECT id,title,due_date,status,source FROM tasks WHERE source LIKE ?',('course-v6:'+c['key'].split(':')[1]+':%',))}
 runs=all_items(con,'recovery');latest=next((x for x in runs if x['payload']['status']=='active'),None)
 return {'courses':courses,'cards':cards,'tags':TAGS,'latest_recovery':{'key':latest['key'],'created_at':latest['updated_at'],'count':len(latest['payload']['moves'])} if latest else None}
def fingerprint(con):
 obj={t:[dict(r) for r in con.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in ('tasks','submissions','focus_sessions')}
 obj['drafts']=[dict(r) for r in con.execute("SELECT * FROM workspace_items WHERE key LIKE 'draft:%' ORDER BY key")]
 return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False).encode('utf8')).hexdigest()
def is_system(t):return t['source']=='2026-plan' or t['source'].startswith(('exam-v3:','route-v4:'))
def preview(con,d):
 start=date.fromisoformat(d.get('start',''));end=date.fromisoformat(d.get('deadline',''));capacity=d.get('minutes');rest=d.get('rest_days',[])
 if not 0<=(end-start).days<=730 or type(capacity) is not int or not 30<=capacity<=600 or not isinstance(rest,list) or len(set(rest))!=len(rest) or any(type(v) is not int or v not in range(7) for v in rest) or len(rest)==7:raise ValueError('请选择有效日期、30–600分钟日容量和休息日')
 tasks=[dict(r) for r in con.execute('SELECT * FROM tasks ORDER BY due_date,id')];drafts={int(r[0][6:]) for r in con.execute("SELECT key FROM workspace_items WHERE key LIKE 'draft:%'")};evidence={r[0] for r in con.execute('SELECT task_id FROM submissions UNION SELECT task_id FROM focus_sessions WHERE task_id IS NOT NULL')}
 # Past unfinished work and future work are moved together; protected and custom tasks stay fixed.
 movable=[t for t in tasks if is_system(t) and t['status']=='todo' and t['id'] not in drafts|evidence]
 ids={t['id'] for t in movable};used={};fixed=[]
 for t in tasks:
  if t['id'] not in ids and t['status']!='done':used[t['due_date']]=used.get(t['due_date'],0)+t['minutes'];fixed.append(t)
 cursor=start;moves=[];overflow=[];overlarge=[]
 for t in movable:
  if t['minutes']>capacity:overlarge.append(t['id']);overflow.append(t);continue
  while cursor<=end and (cursor.weekday() in rest or used.get(cursor.isoformat(),0)+t['minutes']>capacity):cursor+=timedelta(days=1)
  if cursor>end:overflow.append(t);continue
  day=cursor.isoformat();used[day]=used.get(day,0)+t['minutes'];moves.append({'id':t['id'],'before':t['due_date'],'after':day,'title':t['title'],'minutes':t['minutes']})
 days=[{'date':k,'minutes':v,'over_capacity':v>capacity} for k,v in sorted(used.items()) if start.isoformat()<=k<=end.isoformat()]
 blocked=[x for x in days if x['over_capacity']]
 return {'fingerprint':fingerprint(con),'options':{'start':start.isoformat(),'deadline':end.isoformat(),'minutes':capacity,'rest_days':rest},'movable':len(movable),'protected':sum(is_system(t) for t in tasks if t['id'] not in ids),'moves':moves,'overflow':len(overflow),'overflow_minutes':sum(t['minutes'] for t in overflow),'oversized_task_ids':overlarge,'fixed_over_capacity':blocked,'days':days,'can_apply':bool(moves) and not overflow and not blocked,'note':'保留完成/进行中、作业、专注和数据库草稿；自建任务与课程任务不移动并占用容量。所有尚未开始的系统任务按原顺序整体重排；不会拆分、丢弃或自动标记完成。'}
def post(con,engine,path,d):
 from customer_workspace import WorkspaceConflict
 if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
 if path=='/api/learning/course':
  key=d.get('key') or 'course:'+uuid.uuid4().hex
  if not re.fullmatch(r'course:[a-zA-Z0-9_-]{1,70}',key):raise ValueError('课程标识不正确')
  p=validate_learning(key,d.get('payload'));old=fetch(con,key)
  if not p.get('title','').strip() or not p.get('chapters'):raise ValueError('请填写课程名称和至少一章')
  if not con.execute('SELECT 1 FROM subjects WHERE id=?',(p['subject_id'],)).fetchone():raise ValueError('请先创建或选择自己的学科')
  if not old and len(all_items(con,'course'))>=100:raise ValueError('课程已达100门，请先归档整理')
  # Validate against the actual loaded pack module IDs rather than silently guessing chapter alignment.
  validmods={m['id'] for m in engine.pack(engine.default_profile()).get('modules',[])}
  if any(x.get('module') and (p['track']!='c' or x['module'] not in validmods) for x in p['chapters']):raise ValueError('章节知识点对应关系不正确')
  linked=list(con.execute('SELECT source FROM tasks WHERE source LIKE ?',('course-v6:'+key.split(':')[1]+':%',)))
  if old and linked and (p['subject_id']!=old['payload']['subject_id'] or any(x[0].split(':')[-1] not in {c['id'] for c in p['chapters']} for x in linked)):raise ValueError('课程已有任务，请保留原学科和已关联章节；可归档后新建课程')
  return {'ok':True,'item':write(con,key,p,d.get('revision',0))}
 if path=='/api/learning/course-task':
  c=fetch(con,str(d.get('key','')))
  if not c or not c['key'].startswith('course:') or c['payload'].get('archived'):raise ValueError('课程不存在或已归档')
  chapter=next((x for x in c['payload']['chapters'] if x['id']==d.get('chapter_id')),None)
  if not chapter:raise ValueError('章节不存在')
  day=date.fromisoformat(d.get('date','')).isoformat();source='course-v6:'+c['key'].split(':')[1]+':'+chapter['id'];old=con.execute('SELECT id,due_date FROM tasks WHERE source=?',(source,)).fetchone()
  if old:return {'ok':True,'id':old['id'],'date':old['due_date'],'existing':True}
  detail='课程：'+c['payload']['title']+'\n章节：'+chapter['title']+'\n学习要求：看课后合上视频，写出要点，独立完成一道相关练习。看完不等于掌握。'+ ('\n知识点：'+chapter['module'] if chapter.get('module') else '')
  cur=con.execute("INSERT INTO tasks(subject_id,due_date,title,detail,minutes,kind,status,source,created_at) VALUES(?,?,?,?,?,'practice','todo',?,?)",(c['payload']['subject_id'],day,chapter['title'],detail,chapter['minutes'],source,stamp()))
  return {'ok':True,'id':cur.lastrowid,'date':day,'existing':False}
 if path=='/api/learning/question':
  qid=str(d.get('question_id',''))
  if qid not in allowed_questions(con,engine):raise ValueError('这道题不属于你当前路线的学习包')
  key='question:'+qid;return {'ok':True,'item':write(con,key,validate_learning(key,d.get('payload')),d.get('revision',0))}
 if path=='/api/learning/recovery-preview':return preview(con,d)
 if path=='/api/learning/recovery-apply':
  p=preview(con,d)
  if d.get('fingerprint')!=p['fingerprint']:raise WorkspaceConflict('学习记录已变化，请重新预览；原安排未改动。')
  if not p['can_apply']:raise ValueError('当前容量装不下全部任务，或固定任务已超量。请增加时间、延后截止日或调整固定任务后重新预览。')
  for x in p['moves']:con.execute('UPDATE tasks SET due_date=? WHERE id=?',(x['after'],x['id']))
  for old in all_items(con,'recovery'):
   if old['payload']['status']=='active':old['payload']['status']='superseded';write(con,old['key'],old['payload'],old['revision'])
  con.execute("UPDATE exam_plan_runs SET status='recovered' WHERE status='active'")
  item=write(con,'recovery:'+uuid.uuid4().hex,{'moves':[{k:x[k] for k in ('id','before','after')} for x in p['moves']],'before_hash':p['fingerprint'],'after_hash':fingerprint(con),'status':'active','created_at':stamp(),'options':p['options']},0)
  return {'ok':True,'key':item['key'],'moved':len(p['moves'])}
 if path=='/api/learning/recovery-undo':
  item=fetch(con,str(d.get('key','')))
  if not item or not item['key'].startswith('recovery:') or item['payload']['status']!='active':raise ValueError('没有可撤回的补救安排')
  p=item['payload']
  if fingerprint(con)!=p['after_hash']:raise WorkspaceConflict('补救之后已有任务、作业、专注或草稿变化，保留当前进度，不整版撤回。')
  for x in p['moves']:con.execute('UPDATE tasks SET due_date=? WHERE id=?',(x['before'],x['id']))
  p['status']='undone';write(con,item['key'],p,item['revision']);return {'ok':True,'restored':len(p['moves'])}
 raise ValueError('学习操作不存在')
