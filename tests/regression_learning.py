# -*- coding: utf-8 -*-
import atexit,shutil
import sys,tempfile,os,json,copy,sqlite3,concurrent.futures
from pathlib import Path
os.environ['STUDYFORGE_DATA_DIR']=tempfile.mkdtemp(prefix='learning-engine-')
sys.path.insert(0,str((Path(__file__).resolve().parents[1]/'app').resolve()))
atexit.register(shutil.rmtree, os.environ['STUDYFORGE_DATA_DIR'], ignore_errors=True)
import app
from learning_tools import post,library,preview,fingerprint,validate_learning
from customer_workspace import WorkspaceConflict,validate_item
app.init_db()
with app.connection() as c:app.owner_route(c)
with app.connection() as c:
 # Start with a small deterministic schedule, not real learner records.
 c.execute('DELETE FROM tasks');sid=c.execute('SELECT id FROM subjects ORDER BY id').fetchone()[0]
 def task(title,day,minutes=40,status='todo',source='exam-v3:hubei-hbnu-cs:intro'):
  return c.execute('INSERT INTO tasks(subject_id,due_date,title,minutes,status,source,created_at) VALUES(?,?,?,?,?,?,?)',(sid,day,title,minutes,status,source,app.now())).lastrowid
 a=task('积压一','2026-10-20');b=task('积压二','2026-10-21');future=task('后续','2026-10-30');done=task('已完成','2026-10-21',status='done');doing=task('进行中','2026-10-21',status='doing');draft=task('草稿','2026-10-21');submitted=task('作业','2026-10-21');focus=task('专注','2026-10-21');fixed=task('自建','2026-10-25',20,source='custom')
 c.execute('INSERT INTO workspace_items VALUES(?,?,1,?)',('draft:'+str(draft),json.dumps({'content':'not submitted','language':'c','tests':[]}),app.now()))
 c.execute('INSERT INTO submissions(task_id,content,language,created_at) VALUES(?,?,?,?)',(submitted,'answer','text',app.now()))
 c.execute('INSERT INTO focus_sessions(task_id,day,minutes,ended_at) VALUES(?,?,?,?)',(focus,'2026-10-21',25,app.now()))
 original=[tuple(x) for x in c.execute('SELECT * FROM tasks ORDER BY id')];f=fingerprint(c)
 opt={'start':'2026-10-25','deadline':'2026-10-30','minutes':60,'rest_days':[0]};p=preview(c,opt)
 assert fingerprint(c)==f and p['movable']==3 and p['protected']==5 and p['can_apply'];assert p['moves'][0]['after']=='2026-10-25' and p['moves'][1]['after']=='2026-10-27';assert all(x['minutes']<=60 for x in p['days'])
 tight=preview(c,dict(opt,deadline='2026-10-25'));assert tight['overflow']==2 and not tight['can_apply']
 try:post(c,app.EXAMS,'/api/learning/recovery-apply',dict(opt,fingerprint='bad'));raise AssertionError('stale accepted')
 except WorkspaceConflict:pass
 run=post(c,app.EXAMS,'/api/learning/recovery-apply',dict(opt,fingerprint=p['fingerprint']));assert run['moved']==3
 assert c.execute('SELECT due_date FROM tasks WHERE id=?',(draft,)).fetchone()[0]=='2026-10-21'
 assert c.execute('SELECT status FROM tasks WHERE id=?',(done,)).fetchone()[0]=='done'
 post(c,app.EXAMS,'/api/learning/recovery-undo',{'key':run['key']});assert original==[tuple(x) for x in c.execute('SELECT * FROM tasks ORDER BY id')]
 p=preview(c,opt);run=post(c,app.EXAMS,'/api/learning/recovery-apply',dict(opt,fingerprint=p['fingerprint']));c.execute("UPDATE tasks SET status='doing' WHERE id=?",(a,))
 try:post(c,app.EXAMS,'/api/learning/recovery-undo',{'key':run['key']});raise AssertionError('protected undo accepted')
 except WorkspaceConflict:pass
 big=task('不可拆分','2026-10-21',100);assert big in preview(c,opt)['oversized_task_ids']
 c.execute('UPDATE tasks SET minutes=90 WHERE id=?',(fixed,));assert preview(c,opt)['fixed_over_capacity']
 print('RECOVERY PASS: preview nonmutating; chronological capacity/rest days; fixed workload counted; draft/submission/focus/status protected; no overflow apply; exact undo; stale apply and learned undo blocked')
 course={'title':'我的C语言视频','provider':'自有课程','url':'https://example.com/course','subject_id':sid,'track':'c','archived':False,'chapters':[{'id':'ch1','title':'变量与类型','minutes':45,'module':'types','status':'todo','note':''}]}
 # Choose actual module ID from the content pack.
 course['chapters'][0]['module']=app.EXAMS.pack(app.EXAMS.default_profile())['modules'][0]['id']
 x=post(c,app.EXAMS,'/api/learning/course',{'payload':course})['item'];key=x['key'];t=post(c,app.EXAMS,'/api/learning/course-task',{'key':key,'chapter_id':'ch1','date':'2026-10-28'});again=post(c,app.EXAMS,'/api/learning/course-task',{'key':key,'chapter_id':'ch1','date':'2026-10-29'});assert again['existing'] and t['id']==again['id'] and again['date']=='2026-10-28'
 updated=copy.deepcopy(course);updated['chapters'][0].update(status='watched',note='<script>文本</script>')
 x=post(c,app.EXAMS,'/api/learning/course',{'key':key,'payload':updated,'revision':1})['item'];assert x['revision']==2
 try:post(c,app.EXAMS,'/api/learning/course',{'key':key,'payload':course,'revision':1});raise AssertionError('course stale')
 except WorkspaceConflict:pass
 bad=copy.deepcopy(course);bad['url']='javascript:alert(1)'
 try:post(c,app.EXAMS,'/api/learning/course',{'payload':bad});raise AssertionError('unsafe URL')
 except ValueError:pass
 bad=copy.deepcopy(course);bad['chapters'][0]['module']='not-a-module'
 try:post(c,app.EXAMS,'/api/learning/course',{'payload':bad});raise AssertionError('unknown module')
 except ValueError:pass
 updated['archived']=True;post(c,app.EXAMS,'/api/learning/course',{'key':key,'payload':updated,'revision':2})
 try:post(c,app.EXAMS,'/api/learning/course-task',{'key':key,'chapter_id':'ch1','date':'2026-10-29'});raise AssertionError('archive')
 except ValueError:pass
 assert c.execute('SELECT id FROM tasks WHERE id=?',(t['id'],)).fetchone()
 print('COURSES PASS: real module validation; private chapter progress/notes; CAS conflict; 1 chapter = 1 task even with different dates; archived records and linked task retained; invalid URLs rejected')
 q=app.EXAMS.bank[0];note={'favorite':True,'tags':['边界条件'],'note':'下一次检查零和负数 <img src=x>'};post(c,app.EXAMS,'/api/learning/question',{'question_id':q['id'],'payload':note})
 data=library(c,app.EXAMS);assert data['cards'][0]['payload']==note and 'answer' not in data['cards'][0]['question'];assert len(data['courses'])==1
 try:post(c,app.EXAMS,'/api/learning/question',{'question_id':q['id'],'payload':note});raise AssertionError('question stale')
 except WorkspaceConflict:pass
 assert c.execute('SELECT COUNT(*) FROM exam_attempts').fetchone()[0]==0
 for row in c.execute('SELECT * FROM workspace_items'):validate_item(row['key'],json.loads(row['payload']))
 c.execute('DELETE FROM student_route');assert not library(c,app.EXAMS)['cards']
 try:post(c,app.EXAMS,'/api/learning/question',{'question_id':q['id'],'payload':note,'revision':1});raise AssertionError('no route gating')
 except ValueError:pass
 print('QUESTION CARDS PASS: persisted favorites/tags/notes; no answer leak; CAS and selected-route gate; no score/mastery inflation; all new workspace rows export/import structurally valid')
# Dedicated draft regression for plan replacement and undo.
with app.connection() as c:
 c.execute('DELETE FROM tasks');p=app.EXAMS.default_profile();p['deadline']='2026-11-22';run=app.EXAMS.apply_plan(c,p);tid=json.loads(c.execute('SELECT inserted_ids_json FROM exam_plan_runs WHERE id=?',(run['run_id'],)).fetchone()[0])[0]
 c.execute('INSERT INTO workspace_items VALUES(?,?,1,?)',('draft:'+str(tid),json.dumps({'content':'draft-only','language':'c','tests':[]}),app.now()))
 try:app.EXAMS.undo_plan(c);raise AssertionError('draft undo')
 except ValueError:pass
 app.EXAMS.apply_plan(c,p);assert c.execute('SELECT id FROM tasks WHERE id=?',(tid,)).fetchone();assert c.execute('SELECT payload FROM workspace_items WHERE key=?',('draft:'+str(tid),)).fetchone()
 print('DRAFT REGRESSION PASS: draft-only task survives plan replacement; plan undo refuses to discard draft')
print('LEARNING V6 ALL PASS')
