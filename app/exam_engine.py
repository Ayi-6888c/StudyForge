# -*- coding: utf-8 -*-
"""Versioned exam content, transparent planning and paper-first practice. stdlib only."""
import json
import re
from datetime import date, datetime, timedelta

EXTRA_COLUMNS = {
 'exam_profile': ('id','payload','updated_at'),
 'exam_attempts': ('id','question_id','answer','correct','grade_source','self_rating','error_note','ai_feedback','duration_seconds','created_at'),
 'exam_review_queue': ('question_id','due_date','streak','errors','last_day'),
 'exam_sessions': ('id','mode','subject','paper_json','answers_json','result_json','started_at','deadline','finished_at','status'),
 'exam_plan_runs': ('id','profile_before','profile_after','old_tasks_json','inserted_ids_json','created_at','status')}

def stamp(): return datetime.now().astimezone().isoformat(timespec='seconds')
def records(con, sql, args=()): return [dict(x) for x in con.execute(sql,args).fetchall()]

class ExamEngine:
 def __init__(self, assets):
  self.packs=json.loads((assets/'exam_packs.json').read_text(encoding='utf-8'))['packs']
  raw=json.loads((assets/'question_bank.json').read_text(encoding='utf-8'))
  self.bank=raw['questions']; self.questions={q['id']:q for q in self.bank}
  self.content_version=raw['version']
  if raw.get('schema_version')!=1:raise ValueError('题库版本格式不受支持')
  if len(self.questions)!=len(self.bank): raise ValueError('题库ID重复')
  for q in self.bank:
   if q['origin']!='original' or not q['explanation'] or q['kind'] in ('choice','judge'):
    raise ValueError('内容包校验失败')
   if q['family_id'] not in self.questions or not isinstance(q['tests'],list) or len(q['tests'])>5 or '\x00' in q['code'] or '\x00' in q['answer']:raise ValueError('题库原型、样例或字符校验失败')
   if q['accepted'] is not None and (not isinstance(q['accepted'],list) or not q['accepted'] or not all(isinstance(x,str) for x in q['accepted'])):raise ValueError('参考答案匹配格式不正确')
  pack_ids=set()
  for pack in self.packs:
   if pack.get('planner_id')!='c-english-v1' or {r['subject'] for r in pack['rules']}!={'c','english'}:raise ValueError('此路线需要新增学科规划适配器，不能套用现有C与英语规划器')
   if pack['id'] in pack_ids or pack['schema_version']!=1:raise ValueError('路线包ID或版本不正确')
   pack_ids.add(pack['id']);seen=set()
   for m in pack['modules']:
    if m['id'] in seen or not set(m['prerequisites']).issubset(seen) or m['weight']<=0:raise ValueError('知识前置关系或课时权重不正确')
    seen.add(m['id'])
   if not pack['sources'] or any(not x['url'].startswith('https://') or not x['checked_at'] for x in pack['sources']):raise ValueError('路线缺少来源或核对日期')
   for rule in pack['rules']:
    template=pack['mock_templates'][rule['subject']]
    if template['minutes']!=rule['minutes'] or sum(s['count']*s['points'] for s in template['sections'])!=rule['points']:raise ValueError('模拟时长/满分与资料规则不一致')
    if any(s['kind'] in ('choice','judge') or s['count']<=0 or s['points']<=0 for s in template['sections']):raise ValueError('模拟模板不符合当前非选择题规则')

 def init(self,con):
  con.executescript('''
  CREATE TABLE IF NOT EXISTS exam_profile(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL,updated_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS exam_attempts(id INTEGER PRIMARY KEY,question_id TEXT NOT NULL,answer TEXT NOT NULL,correct INTEGER,grade_source TEXT NOT NULL,self_rating TEXT NOT NULL DEFAULT '',error_note TEXT NOT NULL DEFAULT '',ai_feedback TEXT NOT NULL DEFAULT '',duration_seconds INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
  CREATE INDEX IF NOT EXISTS idx_exam_attempt_q ON exam_attempts(question_id,id);
  CREATE TABLE IF NOT EXISTS exam_review_queue(question_id TEXT PRIMARY KEY,due_date TEXT NOT NULL,streak INTEGER NOT NULL DEFAULT 0,errors INTEGER NOT NULL DEFAULT 0,last_day TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS exam_sessions(id INTEGER PRIMARY KEY,mode TEXT NOT NULL,subject TEXT NOT NULL,paper_json TEXT NOT NULL,answers_json TEXT NOT NULL DEFAULT '{}',result_json TEXT NOT NULL DEFAULT '{}',started_at TEXT NOT NULL,deadline TEXT NOT NULL,finished_at TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'active');
  CREATE TABLE IF NOT EXISTS exam_plan_runs(id INTEGER PRIMARY KEY,profile_before TEXT NOT NULL,profile_after TEXT NOT NULL,old_tasks_json TEXT NOT NULL,inserted_ids_json TEXT NOT NULL,created_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active');
  ''')

 def default_profile(self):
  return {'pack_id':'hubei-hbnu-cs','target_year':2027,'start_date':'2026-10-25','deadline':'2027-04-16','intensity':'standard','daily_minutes':270,'base_level':'zero','course_name':'我的C语言视频课','video_mappings':{},'registration_checks':{}}

 def profile(self,con):
  row=con.execute('SELECT payload FROM exam_profile WHERE id=1').fetchone()
  return self.validate_profile(json.loads(row[0]) if row else self.default_profile())

 def validate_profile(self,data):
  p=self.default_profile();p.update({k:v for k,v in data.items() if k in p})
  if not any(x['id']==p['pack_id'] for x in self.packs):raise ValueError('尚未收录这个院校专业包，请先选择已核验的湖北师大计算机路线')
  a=date.fromisoformat(p['start_date']);b=date.fromisoformat(p['deadline'])
  if not 28<=(b-a).days+1<=730:raise ValueError('学习周期请设为28至730天；截止日是个人安排，不代表官方考试日')
  p['target_year']=int(p['target_year'])
  if not 2026<=p['target_year']<=2035:raise ValueError('目标年份请填2026至2035')
  presets={'light':180,'standard':270,'intensive':360}
  if p['intensity'] not in ('light','standard','intensive','custom'):raise ValueError('强度选项不正确')
  p['daily_minutes']=presets.get(p['intensity'],int(p['daily_minutes']))
  if not 150<=p['daily_minutes']<=480:raise ValueError('自定义时长请设为150至480分钟')
  if p['base_level'] not in ('zero','intro','solid'):raise ValueError('基础选项不正确')
  if not isinstance(p['video_mappings'],dict) or len(p['video_mappings'])>40:raise ValueError('视频章节映射格式不正确')
  p['video_mappings']={str(k)[:30]:str(v)[:200] for k,v in p['video_mappings'].items()}
  p['course_name']=str(p['course_name'])[:100]
  if not isinstance(p['registration_checks'],dict) or len(p['registration_checks'])>20:raise ValueError('报考清单格式不正确')
  p['registration_checks']={str(k)[:40]:bool(v) for k,v in p['registration_checks'].items()}
  return p

 def pack(self,p):return next(x for x in self.packs if x['id']==p['pack_id'])
 def available(self,pack):
  pools={pool for values in pack['question_pools'].values() for pool in values}
  return [q for q in self.bank if q['pool_id'] in pools]
 def save_profile(self,con,p):
  con.execute('INSERT INTO exam_profile(id,payload,updated_at) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at',(json.dumps(p,ensure_ascii=False),stamp()))

 def public_question(self,q):
  return {k:q[k] for k in ('id','family_id','subject','module','kind','difficulty','prompt','code','source_note','tests')}

 def mastery(self,con,pack):
  attempts=records(con,'SELECT * FROM exam_attempts ORDER BY id');available={q['id'] for q in self.available(pack)}
  latest={};first={}
  for a in attempts:
   q=self.questions.get(a['question_id'])
   if not q or q['id'] not in available or a['grade_source']!='auto':continue
   latest[q['family_id']]=(a,q);first.setdefault(q['family_id'],a['created_at'][:10])
  result=[]
  for m in pack['modules']:
   items=[(a,q) for a,q in latest.values() if q['module']==m['id'] and q['subject']=='c']
   good=sum(a['correct']==1 for a,q in items);n=len(items)
   delayed=sum(a['correct']==1 and a['created_at'][:10]>first[q['family_id']] for a,q in items)
   total=len({q['family_id'] for q in self.available(pack) if q['subject']=='c' and q['module']==m['id'] and q['accepted'] is not None})
   state='未测' if not n else ('回忆达标·编程另评' if n>=3 and good/n>=.8 and delayed>=1 else '练习中·需延迟复测')
   result.append(dict(m,attempted_families=n,correct_families=good,total_families=total,accuracy=round(good/n*100) if n else None,delayed=delayed,state=state))
  return result

 def dashboard(self,con):
  p=self.profile(con);pack=self.pack(p);today=date.today().isoformat()
  due=records(con,'SELECT * FROM exam_review_queue WHERE due_date<=? ORDER BY due_date,question_id',(today,))
  due=[dict(x,question=self.public_question(self.questions[x['question_id']])) for x in due if x['question_id'] in self.questions]
  sessions=records(con,'SELECT id,mode,subject,started_at,deadline,finished_at,status FROM exam_sessions ORDER BY id DESC LIMIT 12')
  attempted=con.execute('SELECT COUNT(*) FROM exam_attempts').fetchone()[0];bank=self.available(pack)
  return {'profile':p,'pack':pack,'packs':[{'id':x['id'],'province':x['province'],'institution':x['institution'],'target_major':x['target_major']} for x in self.packs],
   'stats':{'items':len(bank),'families':len({x['family_id'] for x in bank}),'c_items':sum(q['subject']=='c' for q in bank),'english_items':sum(q['subject']=='english' for q in bank),'attempts':attempted,'due':len(due)},
   'mastery':self.mastery(con,pack),'due':due,'sessions':sessions,'content_version':self.content_version,
   'latest_plan':(records(con,'SELECT id,created_at,status FROM exam_plan_runs ORDER BY id DESC LIMIT 1') or [None])[0]}

 def make_plan(self,p):
  pack=self.pack(p);start=date.fromisoformat(p['start_date']);end=date.fromisoformat(p['deadline']);days=(end-start).days+1
  edges=[round(days*.32),round(days*.62),round(days*.85),days]
  chain=[]
  for m in pack['modules']:chain.extend([m]*m['weight'])
  foundation_days=[d for d in range(edges[0]) if d%7!=6]
  lessons={d:chain[min(len(chain)-1,int(i*len(chain)/len(foundation_days)))] for i,d in enumerate(foundation_days)}
  plan=[];last=pack['modules'][0];history=[]
  for d in range(days):
   day=(start+timedelta(days=d)).isoformat();weekly=d%7==6
   phase=0 if d<edges[0] else 1 if d<edges[1] else 2 if d<edges[2] else 3
   if phase==0:m=lessons.get(d,last)
   else:m=pack['modules'][(d-edges[phase-1])%len(pack['modules'])]
   last=m;history.append(m)
   minutes=round(p['daily_minutes']*(.7 if weekly else 1)/5)*5
   c=round(minutes*.67/5)*5;english=minutes-c
   qty=8 if p['daily_minutes']<240 else 12 if p['daily_minutes']<330 else 18
   codes=2 if p['daily_minutes']<240 else 3 if p['daily_minutes']<330 else 4
   items=[];phase_name=['基础建构','专项巩固','综合迁移','限时冲刺'][phase]
   def task(title,detail,mins,kind='practice',subject='c'):
    if mins>0:items.append({'date':day,'subject':subject,'title':title,'detail':detail,'minutes':mins,'kind':kind,'module':m['id'],'phase':phase_name})
   if phase==3 and not weekly and d%3==0 and c>=95:
    task('90分钟闭卷模拟｜原创组卷','在“诊断与模考”开始C语言完整卷。先纸笔作答，不查看答案；交卷后区分自动匹配分和待复核分。模拟题型分配为软件自定义，并非官方分值比例。',90,'mock')
    task('模拟订正｜定位失分原因','把语法、跟踪、边界、思路问题分别记入错题；重写一道未完成的程序，次日再测。',c-90,'review')
   else:
    a=round(c*.3/5)*5;b=round(c*.2/5)*5;cc=round(c*.35/5)*5;r=c-a-b-cc
    mapping=p['video_mappings'].get(m['id'],'在自己的课程里找到本章对应小节')
    task(('回看与补缺' if weekly or phase>0 else '概念与示范')+'｜'+m['title'],f'目标：{m["concepts"]}。视频：{p["course_name"]} / {mapping}。每看10—15分钟停下复述并改写例题，不以看完视频作为掌握。',a,'review' if weekly or phase>0 else 'video')
    task('纸笔专项｜'+m['title'],f'完成{qty}题练习轮次（含旧题延迟复测，非每天{qty}道全新题）：输出跟踪、填空、补全、改错混合。首次遮住答案；匹配不足80%时先补缺再增加新题。第一遍先做当前章，做完可混合前置章节。',b)
    task('独立编程｜'+m['title'],f'独立写{codes}道由浅入深的短程序，优先本章原创编程题；每题写思路和正常/边界/特殊测试表，先手算预期再运行。{m["exit_standard"]}。进阶第4题可改写一道已完成题的数据范围或函数接口。',cc)
    past=[]
    for gap in (1,3,7):
     if d>=gap:past.append(f'{gap}天前的{history[d-gap]["title"]}')
    task('闭卷回忆与错题复测',('回忆：'+'；'.join(past) if past else '首次摸底：不运行地解释程序结构、变量、格式符及整除取模')+'。在错题复习页优先处理到期题。自评理解不等于自动通过；主观题对照评分点，记录仍不理解的原因。',r,'review')
   task('英语｜词汇输出＋语言运用',f'用{max(10,round(english*.25/5)*5)}分钟回忆{15 if english<80 else 25 if english<110 else 35}个词并造句；其余时间轮换语法填空、阅读简答、翻译和短文写作。采用非选择题训练。错词隔1/3/7天复测；每周保留一次作文订正。',english,'review' if weekly else 'practice','english')
   plan.append({'date':day,'phase':phase_name,'module':m['id'],'module_title':m['title'],'minutes':minutes,'weekly_review':weekly,'tasks':items})
  return plan

 def preview_plan(self,p):
  days=self.make_plan(p);phases=[]
  for name in ('基础建构','专项巩固','综合迁移','限时冲刺'):
   selected=[d for d in days if d['phase']==name]
   if selected:phases.append({'name':name,'start':selected[0]['date'],'end':selected[-1]['date'],'days':len(selected)})
  return {'profile':p,'days':len(days),'task_count':sum(len(d['tasks']) for d in days),'total_minutes':sum(d['minutes'] for d in days),'phases':phases,'first_days':days[:7],
   'notes':['每日分钟数指净学习时间，不含休息；每第7天降至约70%用于回顾。','题量是练习轮次，包含错题及延迟复测；题库规模与原型数量在专项题库中公开。','本计划不因自选“已有基础”自动跳过前置知识；先用基础诊断验证。', '周期短于90天时章节被压缩，建议先诊断并优先补薄弱点。' if len(days)<90 else '先完整覆盖，再专项巩固、综合迁移和限时模拟。']}

 def has_draft(self,con,tid):
  return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='workspace_items'").fetchone() and con.execute('SELECT 1 FROM workspace_items WHERE key=?',('draft:'+str(tid),)).fetchone())

 def apply_plan(self,con,p):
  before=self.profile(con);before['_subject_dates']={str(r['id']):r['exam_date'] for r in records(con,'SELECT id,exam_date FROM subjects')};days=self.make_plan(p)
  old=records(con,"SELECT * FROM tasks WHERE due_date BETWEEN ? AND ? AND (source='2026-plan' OR source LIKE 'exam-v3:%') AND status='todo' AND NOT EXISTS(SELECT 1 FROM submissions WHERE task_id=tasks.id) AND NOT EXISTS(SELECT 1 FROM focus_sessions WHERE task_id=tasks.id)",(p['start_date'],p['deadline']))
  old=[x for x in old if not self.has_draft(con,x['id'])]
  for x in old:con.execute('DELETE FROM tasks WHERE id=?',(x['id'],))
  subjects={}
  for key,name,icon,color in [('c','C 语言','</>','#709a77'),('english','大学英语','Aa','#a6879c')]:
   row=con.execute('SELECT id FROM subjects WHERE name=? ORDER BY id LIMIT 1',(name,)).fetchone()
   if row:sid=row[0]
   else:
    cur=con.execute('INSERT INTO subjects(name,icon,color,exam_date,created_at) VALUES(?,?,?,?,?)',(name,icon,color,'',stamp()));sid=cur.lastrowid
   subjects[key]=sid
   con.execute('UPDATE subjects SET exam_date=? WHERE id=?',(p['deadline'],sid))
  ids=[]
  for day in days:
   for t in day['tasks']:
    cur=con.execute('INSERT INTO tasks(subject_id,due_date,title,detail,minutes,kind,status,source,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(subjects[t['subject']],t['date'],t['title'],t['detail'],t['minutes'],t['kind'],'todo','exam-v3:'+p['pack_id']+':'+t['module'],stamp()));ids.append(cur.lastrowid)
  self.save_profile(con,p)
  run=con.execute('INSERT INTO exam_plan_runs(profile_before,profile_after,old_tasks_json,inserted_ids_json,created_at) VALUES(?,?,?,?,?)',(json.dumps(before,ensure_ascii=False),json.dumps(p,ensure_ascii=False),json.dumps(old,ensure_ascii=False),json.dumps(ids),stamp())).lastrowid
  return {'ok':True,'run_id':run,'removed_unstarted':len(old),'inserted':len(ids),'preserved_note':'已完成、进行中、含作业、专注、数据库草稿及自建任务均保留。','preview':self.preview_plan(p)}

 def undo_plan(self,con):
  run=con.execute("SELECT * FROM exam_plan_runs WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
  if not run:raise ValueError('没有可撤回的计划版本')
  ids=json.loads(run['inserted_ids_json'])
  for tid in ids:
   row=con.execute('SELECT status FROM tasks WHERE id=?',(tid,)).fetchone()
   if row and (self.has_draft(con,tid) or row[0]!='todo' or con.execute('SELECT 1 FROM submissions WHERE task_id=?',(tid,)).fetchone() or con.execute('SELECT 1 FROM focus_sessions WHERE task_id=?',(tid,)).fetchone()):raise ValueError('此计划已有学习记录；为保留作业，请调整后续未开始任务，而不整版撤回')
  for tid in ids:con.execute('DELETE FROM tasks WHERE id=?',(tid,))
  old=json.loads(run['old_tasks_json'])
  for t in old:
   fields=list(t);con.execute('INSERT INTO tasks('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')',tuple(t[k] for k in fields))
  previous=json.loads(run['profile_before'])
  for sid,old_date in previous.pop('_subject_dates',{}).items():con.execute('UPDATE subjects SET exam_date=? WHERE id=?',(old_date,int(sid)))
  self.save_profile(con,previous)
  con.execute("UPDATE exam_plan_runs SET status='undone' WHERE id=?",(run['id'],))
  return {'ok':True,'restored_tasks':len(old),'removed_tasks':len(ids)}

 def normalize(self,s,subject):
  s=re.sub(r'\s+','',str(s).strip())
  return s.casefold().rstrip('.。') if subject=='english' else s

 def grade(self,q,answer):
  accepted=q.get('accepted');correct=None
  if accepted is not None:correct=int(self.normalize(answer,q['subject']) in [self.normalize(x,q['subject']) for x in accepted])
  return {'correct':correct,'grade_source':'auto' if accepted is not None else 'pending','verdict':'参考匹配正确' if correct==1 else '参考匹配未通过' if correct==0 else '主观题待复核','answer':q['answer'],'explanation':q['explanation'],'rubric':q['rubric'],'note':'文字/代码等价解法可对照参考复核；主观题和自评分不计入自动掌握度。'}

 def record(self,con,q,answer,duration=0):
  g=self.grade(q,answer);today=date.today();ts=stamp()
  cur=con.execute('INSERT INTO exam_attempts(question_id,answer,correct,grade_source,duration_seconds,created_at) VALUES(?,?,?,?,?,?)',(q['id'],answer,g['correct'],g['grade_source'],max(0,min(86400,int(duration))),ts))
  old=con.execute('SELECT * FROM exam_review_queue WHERE question_id=?',(q['id'],)).fetchone()
  streak=(old['streak'] if old else 0);errors=(old['errors'] if old else 0)
  if g['correct']==1:
   streak=max(1,streak+1) if not old or old['last_day']<today.isoformat() else max(1,streak)
  else:streak=0;errors+=int(g['correct']==0)
  gap=(1,3,7,14,30)[min(streak-1,4)] if streak else 1
  # 首次正确次日回忆；同日重刷不推进复习间隔。
  if streak==1:gap=1
  due=(today+timedelta(days=gap)).isoformat()
  con.execute('INSERT INTO exam_review_queue(question_id,due_date,streak,errors,last_day) VALUES(?,?,?,?,?) ON CONFLICT(question_id) DO UPDATE SET due_date=excluded.due_date,streak=excluded.streak,errors=excluded.errors,last_day=excluded.last_day',(q['id'],due,streak,errors,today.isoformat()))
  return dict(g,attempt_id=cur.lastrowid,next_review=due)

 def session_view(self,row):
  paper=json.loads(row['paper_json']);finished=row['status']=='finished'
  return {'id':row['id'],'mode':row['mode'],'subject':row['subject'],'started_at':row['started_at'],'deadline':row['deadline'],'status':row['status'],'answers':json.loads(row['answers_json']),'questions':[dict(self.public_question(self.questions[x['id']]),points=x['points']) for x in paper],'result':json.loads(row['result_json']) if finished else None,'server_now':stamp()}

 def start_session(self,con,data):
  mode=data.get('mode','diagnostic');subject=data.get('subject','c')
  if mode not in ('diagnostic','mock') or subject not in ('c','english'):raise ValueError('诊断类型不正确')
  old=con.execute("SELECT * FROM exam_sessions WHERE status='active' AND mode=? AND subject=? ORDER BY id DESC LIMIT 1",(mode,subject)).fetchone()
  if old:return self.session_view(old)
  p=self.profile(con);pack=self.pack(p);paper=[];bank=self.available(pack)
  # 轮换原型而非参数变式，保证一卷不重复同族。
  offset=con.execute('SELECT COUNT(*) FROM exam_sessions').fetchone()[0]
  used=set()
  if mode=='diagnostic':
   pool=[q for q in bank if q['subject']==subject and q['accepted'] is not None and '-V' not in q['id']]
   if subject=='c':pool.sort(key=lambda q:(int(q['id'][-1]) if q['id'][-1].isdigit() else 0,q['module'],q['id']))
   for q in pool[offset:]+pool[:offset]:
    if q['family_id'] not in used:paper.append({'id':q['id'],'points':10});used.add(q['family_id'])
    if len(paper)==10:break
   minutes=20
  else:
   template=pack['mock_templates'][subject];minutes=template['minutes']
   for sec in template['sections']:
    pool=[q for q in bank if q['subject']==subject and q['kind']==sec['kind'] and '-V' not in q['id']]
    allowed_modules=sec.get('modules',[])
    if allowed_modules:
     ordered=[]
     for j in range(len(allowed_modules)):
      module=allowed_modules[(j+offset)%len(allowed_modules)]
      candidates=[q for q in pool if q['module']==module]
      if candidates:ordered.extend(candidates[offset%len(candidates):]+candidates[:offset%len(candidates)])
     # 先从不同章节各取一道，再补充同章题。
     first=[];rest=[];seen_modules=set()
     for q in ordered:
      if q['module'] not in seen_modules:first.append(q);seen_modules.add(q['module'])
      else:rest.append(q)
     pool=first+rest
    else:
     pool=[pool[(int(i*len(pool)/sec['count'])+offset)%len(pool)] for i in range(sec['count'])]+pool
    count=0
    for q in pool:
     if q['family_id'] in used:continue
     paper.append({'id':q['id'],'points':sec['points']});used.add(q['family_id']);count+=1
     if count==sec['count']:break
    if count!=sec['count']:raise ValueError('当前内容包题型数量不足')
  dt=datetime.now().astimezone();started=dt.isoformat(timespec='seconds');deadline=(dt+timedelta(minutes=minutes)).isoformat(timespec='seconds')
  sid=con.execute('INSERT INTO exam_sessions(mode,subject,paper_json,started_at,deadline) VALUES(?,?,?,?,?)',(mode,subject,json.dumps(paper),started,deadline)).lastrowid
  return self.session_view(con.execute('SELECT * FROM exam_sessions WHERE id=?',(sid,)).fetchone())

 def update_session(self,con,data,submit=False):
  row=con.execute('SELECT * FROM exam_sessions WHERE id=?',(int(data['id']),)).fetchone()
  if not row:raise ValueError('试卷不存在')
  if row['status']=='finished':return self.session_view(row)
  paper=json.loads(row['paper_json']);old=json.loads(row['answers_json'])
  expired=datetime.now().astimezone()>=datetime.fromisoformat(row['deadline'])
  if not expired:
   incoming=data.get('answers',{})
   if not isinstance(incoming,dict):raise ValueError('答案格式不正确')
   allowed={x['id'] for x in paper}
   for key,value in incoming.items():
    if key in allowed:old[key]=str(value)[:40000]
   con.execute('UPDATE exam_sessions SET answers_json=? WHERE id=?',(json.dumps(old,ensure_ascii=False),row['id']))
  if submit or expired:
   results=[];earned=0;maximum=0;pending=0
   for item in paper:
    q=self.questions[item['id']];answer=old.get(q['id'],'').strip()
    if not answer:g={'correct':0 if q['accepted'] is not None else None,'grade_source':'auto' if q['accepted'] is not None else 'pending','verdict':'未作答','answer':q['answer'],'explanation':q['explanation'],'rubric':q['rubric']}
    else:g=self.record(con,q,answer)
    if q['accepted'] is not None:maximum+=item['points'];earned+=item['points'] if g['correct']==1 else 0
    else:pending+=item['points']
    results.append(dict(g,id=q['id'],points=item['points']))
   result={'objective_earned':earned,'objective_max':maximum,'pending_points':pending,'total_points':sum(x['points'] for x in paper),'items':results,'note':'只有客观题参考匹配分；主观题待复核，不把部分自动分伪装为总成绩。模拟题分布为软件自定义。'}
   con.execute("UPDATE exam_sessions SET result_json=?,finished_at=?,status='finished' WHERE id=?",(json.dumps(result,ensure_ascii=False),stamp(),row['id']))
  return self.session_view(con.execute('SELECT * FROM exam_sessions WHERE id=?',(row['id'],)).fetchone())

 def get(self,con,path,query):
  if path=='/api/exam/dashboard':return self.dashboard(con)
  if path=='/api/exam/questions':
   selected=self.available(self.pack(self.profile(con)))
   for field in ('subject','module','kind'):
    value=query.get(field,['all'])[0]
    if value!='all':selected=[q for q in selected if q[field]==value]
   return {'questions':[self.public_question(q) for q in selected],'count':len(selected),'families':len({q['family_id'] for q in selected})}
  if path=='/api/exam/question':
   q=self.questions.get(query.get('id',[''])[0])
   if not q:raise ValueError('题目不存在')
   return self.public_question(q)
  if path=='/api/exam/reviews':
   queue=records(con,'SELECT * FROM exam_review_queue ORDER BY due_date,question_id')
   return {'items':[dict(x,question=self.public_question(self.questions[x['question_id']]),latest=(records(con,'SELECT answer,error_note,self_rating,created_at FROM exam_attempts WHERE question_id=? ORDER BY id DESC LIMIT 1',(x['question_id'],)) or [None])[0]) for x in queue if x['question_id'] in self.questions]}
  if path=='/api/exam/session':
   row=con.execute('SELECT * FROM exam_sessions WHERE id=?',(int(query.get('id',['0'])[0]),)).fetchone()
   if not row:raise ValueError('试卷不存在')
   return self.session_view(row)
  raise ValueError('学习接口不存在')

 def post(self,con,path,data,offline,ai):
  if path=='/api/exam/profile':
   p=self.validate_profile(data);self.save_profile(con,p);return {'ok':True,'profile':p}
  if path=='/api/exam/plan-preview':return self.preview_plan(self.validate_profile(data))
  if path=='/api/exam/plan-apply':return self.apply_plan(con,self.validate_profile(data))
  if path=='/api/exam/plan-undo':return self.undo_plan(con)
  if path=='/api/exam/answer':
   q=self.questions.get(str(data.get('question_id','')));answer=str(data.get('answer','')).strip()
   if not q or not answer or len(answer)>40000:raise ValueError('请选择题目并填写1至40000字答案')
   return self.record(con,q,answer,data.get('duration_seconds',0))
  if path=='/api/exam/self-review':
   rating=str(data.get('rating',''));note=str(data.get('error_note',''))[:1000]
   if rating not in ('understood','unclear'):raise ValueError('复核状态不正确')
   con.execute('UPDATE exam_attempts SET self_rating=?,error_note=? WHERE id=?',(rating,note,int(data['attempt_id'])))
   return {'ok':True,'note':'自评已保存；自动掌握度不因自评提高'}
  if path in ('/api/exam/code-check','/api/exam/ai-review'):
   row=con.execute('SELECT * FROM exam_attempts WHERE id=?',(int(data['attempt_id']),)).fetchone()
   if not row:raise ValueError('请先保存本次答案')
   q=self.questions[row['question_id']]
   check=offline(row['answer'],'c' if q['subject']=='c' and q['kind']=='program' else 'text',q['tests'])
   if path.endswith('code-check'):return check
   prompt=q['prompt']+'\n题目代码：'+q['code']+'\n参考解法（非唯一解）：'+q['answer']+'\n评分点：'+q['explanation']+'\n请区分语法、算法、边界、复杂度、表达；先给提示再给订正，不推断未运行的结果，不给冒充官方的分数。'
   feedback=ai(str(data.get('provider','ollama')),str(data.get('model','')),'C程序设计' if q['subject']=='c' else '大学英语',prompt,row['answer'],q['tests'],check['feedback'])
   if not feedback:raise ValueError('AI未返回文字反馈')
   con.execute('UPDATE exam_attempts SET ai_feedback=? WHERE id=?',(feedback,row['id']))
   return {'verdict':'AI辅助复核','feedback':feedback,'note':'辅助建议，不计作官方评分或自动掌握证据'}
  if path=='/api/exam/session-start':return self.start_session(con,data)
  if path=='/api/exam/session-save':return self.update_session(con,data)
  if path=='/api/exam/session-submit':return self.update_session(con,data,True)
  raise ValueError('学习接口不存在')
