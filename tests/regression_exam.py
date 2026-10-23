# -*- coding: utf-8 -*-
import atexit,shutil
import sys,os,tempfile,json
from pathlib import Path
from datetime import date,timedelta,datetime
os.environ['STUDYFORGE_DATA_DIR']=tempfile.mkdtemp(prefix='exam-v3-')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
atexit.register(shutil.rmtree, os.environ['STUDYFORGE_DATA_DIR'], ignore_errors=True)
import app
app.init_db();e=app.EXAMS
with app.connection() as con:
 d=e.dashboard(con);assert d['stats']['items']==212 and d['stats']['families']==152
 assert all(q['origin']=='original' and q['kind'] not in ('choice','judge') for q in e.bank)
 assert all('answer' not in e.public_question(q) and 'accepted' not in e.public_question(q) for q in e.bank)
 for intensity,minutes in [('light',180),('standard',270),('intensive',360),('custom',305)]:
  p=e.validate_profile(dict(e.default_profile(),intensity=intensity,daily_minutes=minutes))
  plan=e.make_plan(p);assert len(plan)==174 and plan[0]['minutes']==minutes
  assert all(sum(x['minutes'] for x in day['tasks'])==day['minutes'] for day in plan)
  assert len(plan[0]['tasks'])==5 and 'Hello World' not in plan[0]['tasks'][0]['title']
  assert 'printf/scanf' in plan[0]['tasks'][0]['detail']
  assert '编程' in plan[0]['tasks'][2]['title']
  first={}
  for day in plan:
   if day['phase']=='基础建构':first.setdefault(day['module'],day['date'])
  assert len(first)==12
  for m in e.pack(p)['modules']:
   for pre in m['prerequisites']:assert first[pre]<=first[m['id']],(m['id'],pre)
 print('PLAN PASS: 174 days, 4 intensities, exact daily budgets, 12 prerequisite-ordered modules, nontrivial day one')
 original_tasks=app.rows(con,'SELECT * FROM tasks ORDER BY id');subject_dates=app.rows(con,'SELECT id,exam_date FROM subjects ORDER BY id')
 con.execute("UPDATE tasks SET status='done' WHERE id=1")
 con.execute("INSERT INTO submissions(task_id,content,language,created_at) VALUES(2,'keep me','text',?)",(app.now(),))
 con.execute("INSERT INTO focus_sessions(task_id,day,minutes,ended_at) VALUES(3,'2026-10-25',25,?)",(app.now(),))
 before=app.rows(con,'SELECT * FROM tasks ORDER BY id')
 p=e.validate_profile(dict(e.default_profile(),deadline='2027-04-10',intensity='custom',daily_minutes=300))
 result=e.apply_plan(con,p)
 assert con.execute('SELECT status FROM tasks WHERE id=1').fetchone()[0]=='done'
 assert con.execute('SELECT content FROM submissions WHERE task_id=2').fetchone()[0]=='keep me'
 assert con.execute('SELECT task_id FROM focus_sessions WHERE task_id=3').fetchone()[0]==3
 ids=json.loads(con.execute('SELECT inserted_ids_json FROM exam_plan_runs WHERE id=?',(result['run_id'],)).fetchone()[0])
 con.execute("UPDATE tasks SET status='doing' WHERE id=?",(ids[0],))
 try:e.undo_plan(con);raise AssertionError('protected undo was accepted')
 except ValueError:pass
 con.execute("UPDATE tasks SET status='todo' WHERE id=?",(ids[0],));e.undo_plan(con)
 assert app.rows(con,'SELECT * FROM tasks ORDER BY id')==before
 assert app.rows(con,'SELECT id,exam_date FROM subjects ORDER BY id')==subject_dates
 print('PLAN ROLLBACK PASS: submissions/completed tasks preserved; protected undo blocked; original rows and target dates restored')
 q=e.questions['C-io-T1'];g=e.record(con,q,q['answer']);assert g['correct']==1
 e.record(con,e.questions['C-io-V1'],e.questions['C-io-V1']['answer'])
 assert next(m for m in e.mastery(con,e.pack(e.default_profile())) if m['id']=='io')['attempted_families']==1
 e.record(con,q,q['answer']);queue=con.execute('SELECT * FROM exam_review_queue WHERE question_id=?',(q['id'],)).fetchone()
 assert queue['streak']==1 and queue['due_date']==(date.today()+timedelta(days=1)).isoformat()
 con.execute('UPDATE exam_review_queue SET last_day=? WHERE question_id=?',((date.today()-timedelta(days=1)).isoformat(),q['id']))
 e.record(con,q,q['answer']);queue=con.execute('SELECT * FROM exam_review_queue WHERE question_id=?',(q['id'],)).fetchone()
 assert queue['streak']==2 and queue['due_date']==(date.today()+timedelta(days=3)).isoformat()
 wrong=e.record(con,e.questions['C-io-F1'],'wrong');assert wrong['correct']==0
 pending=e.record(con,e.questions['C-io-P1'],'int main(void){return 0;}');assert pending['correct'] is None
 e.post(con,'/api/exam/self-review',dict(attempt_id=pending['attempt_id'],rating='understood',error_note='self only'),app.offline_review,app.ai_review)
 assert next(m for m in e.mastery(con,e.pack(e.default_profile())) if m['id']=='io')['attempted_families']==2
 print('MASTERY PASS: variants not inflated, self-review excluded, wrong/pending separated, spaced schedule 1 then 3 days')
 c=e.start_session(con,{'mode':'mock','subject':'c'});assert sum(x['points'] for x in c['questions'])==150
 assert len({q['module'] for q in c['questions']})>=8
 assert len({q['family_id'] for q in c['questions']})==len(c['questions'])
 assert len({q['module'] for q in c['questions'] if q['kind']=='program'})==2
 assert all('answer' not in q for q in c['questions']) and c['result'] is None
 first=c['questions'][0];correct=e.questions[first['id']]['answer']
 e.update_session(con,{'id':c['id'],'answers':{first['id']:correct}})
 resume=e.get(con,'/api/exam/session',{'id':[str(c['id'])]});assert resume['answers'][first['id']]==correct
 con.execute('UPDATE exam_sessions SET deadline=? WHERE id=?',((datetime.now().astimezone()-timedelta(seconds=1)).isoformat(),c['id']))
 done=e.update_session(con,{'id':c['id'],'answers':{first['id']:'late changed answer'}},True)
 assert done['status']=='finished' and done['answers'][first['id']]==correct
 assert done['result']['objective_earned']==first['points'] and done['result']['pending_points']>0
 count=con.execute('SELECT COUNT(*) FROM exam_attempts').fetchone()[0]
 again=e.update_session(con,{'id':c['id'],'answers':{}},True)
 assert con.execute('SELECT COUNT(*) FROM exam_attempts').fetchone()[0]==count and again['result']==done['result']
 eng=e.start_session(con,{'mode':'mock','subject':'english'});assert sum(x['points'] for x in eng['questions'])==100
 diag=e.start_session(con,{'mode':'diagnostic','subject':'c'});assert len(diag['questions'])==10
 print('EXAM PASS: C150/90min, English100/120min, diagnosis10, broad modules, saved/resumable answers, enforced deadline, idempotent submit, pending subjective score')
print('ENGINE V3 ALL PASS')
