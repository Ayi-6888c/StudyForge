# -*- coding: utf-8 -*-
from pathlib import Path
import atexit,shutil
import sys,tempfile,json,sqlite3,zipfile,io,datetime
sys.path.insert(0,str((Path(__file__).resolve().parents[1]/'app').resolve()))
import companion
from student_platform import StudentPlatform,validate_selection,write_route,init_routes
from customer_workspace import full_backup
root=Path(tempfile.mkdtemp(prefix='companion-tests-'));assets=(Path(__file__).resolve().parents[1]/'app').resolve();p=StudentPlatform(root,assets)
atexit.register(shutil.rmtree, str(root), ignore_errors=True)
class Desktop:
 protocol='unit-only';calls=[]
 def identity(self):self.calls.append('identity')
 def ps(self,*a,**k):self.calls.append(k);return {'accepted':True}
d=Desktop();c=companion.Companion(root,assets,p,d);owner={'id':1,'role':'owner'};student={'id':2,'role':'student'};other={'id':3,'role':'student'}
for u,source,offering in [(owner,'510203','hb-04-080901'),(student,'520201','hb-08-101101'),(other,'510203','hb-10-040107')]:
 db=sqlite3.connect(str(p.database_path(u)));init_routes(db)
 try:
  selection=validate_selection(p,dict(province='hubei',source_code=source,offering_id=offering,catalog_revision=p.active()[0],target_year=2027,start_date='2026-10-25',deadline='2026-11-22',intensity='standard',daily_minutes=270,acknowledged=True));write_route(db,selection);db.commit()
 except ValueError:
  if u==student:
   cat=p.catalog(source,2027);o=next(o for o in cat['offerings'] if o['major_name']=='护理学' and o['match']['state']=='matched' and o['evidence']['selection_ready']);selection=validate_selection(p,dict(province='hubei',source_code=source,offering_id=o['id'],catalog_revision=p.active()[0],target_year=2027,start_date='2026-10-25',deadline='2026-11-22',intensity='standard',daily_minutes=270,acknowledged=True));write_route(db,selection);db.commit()
  else:raise
 db.close()
assert len(c.feed(owner)['items'])==5;assert len(c.feed(student)['items'])==1;assert len(c.feed(other)['items'])==2
assert len(c.feed(owner)['coverage'])==31 and sum(x['selectable'] for x in c.feed(owner)['coverage'])==1
assert not c.prefs(owner)['enabled'];assert not c.notification_candidates(owner);c.save_prefs(owner,{'enabled':True,'windows':True});assert not c.notification_candidates(owner),'historical seed must not push'
try:c.save_prefs(student,{'enabled':True,'windows':True});raise AssertionError('student Windows control')
except ValueError:pass
old_fetch=companion.fetch_official
companion.fetch_official=lambda url:'<a href="/2027/0105/article.htm">2027年普通专升本招生考试改革公告</a><a href="/2027/0105/adult.htm">2027年成人高考专升本通知</a><a href="/2027/0105/unrelated.htm">2027届毕业生图像采集通知</a><a href="https://evil.invalid/a">专升本资料</a>'
res=c.refresh(owner);assert all(x['status']=='ok' for x in res['results']);new=[n for n in c.feed(owner)['items'] if n.get('year')==2027];assert len(new)==2 and not any('成人' in n['title'] for n in c.feed(owner)['items']);assert all('待核对' in n['status'] for n in new)
assert c.feed(owner)['items'][0]['year']==2027,'current-year candidate must precede historical cards'
assert all(x['status']=='cached' for x in c.refresh(owner)['results'])
for n in new:c.post(owner,'/api/companion/read',{'ids':[n['id']]})
assert all(n['read'] for n in c.feed(owner)['items'] if n.get('year')==2027)
with c.db() as db:db.execute("UPDATE checks SET checked_at='2020-01-01T00:00:00+08:00'")
companion.fetch_official=lambda url:'<a href="/2026/1023/new.htm">2027年普通专升本新公告</a>'
c.refresh(owner);noon=datetime.datetime.now(companion.TZ).replace(hour=12);assert len(c.notification_candidates(owner,noon))==2;assert not c.notification_candidates(owner,noon.replace(hour=23));assert all(n['published_at']=='' and n.get('notice_eligible') for n in c.notification_candidates(owner,noon))
prefs=c.prefs(owner);prefs['last_notice_day']=noon.date().isoformat()
with c.db() as db:db.execute('INSERT OR REPLACE INTO prefs VALUES(?,?)',(1,json.dumps(prefs)))
assert not c.notification_candidates(owner,noon)
with c.db() as db:db.execute("UPDATE checks SET checked_at='2020-01-01T00:00:00+08:00'")
def fail(url):raise ValueError('synthetic timeout')
companion.fetch_official=fail;old=len(c.feed(owner)['items']);assert all(x['status']=='error' for x in c.refresh(owner)['results']);assert len(c.feed(owner)['items'])==old
companion.fetch_official=old_fetch
x=c.chat(owner,{'question':'我需要考什么，是否能报？'});assert '高级语言程序设计' in x['answer'] and '2027年正式要求尚未录入' in x['answer'];assert x['mode']=='资料问答'
assert not c.get(student,'/api/companion/chat')['items'];f=c.post(student,'/api/companion/feedback',{'category':'功能建议','content':'<script>alert(1)</script>我想更容易找到今天任务'});assert len(c.get(student,'/api/companion/feedback')['items'])==1;assert not c.get(other,'/api/companion/feedback')['items']
try:c.get(student,'/api/companion/admin-feedback');raise AssertionError('admin isolation')
except PermissionError:pass
c.post(owner,'/api/companion/admin-feedback',{'id':f['id'],'status':'已受理','reply':'已收到，先优化入口'});assert c.get(student,'/api/companion/feedback')['items'][0]['reply']=='已收到，先优化入口'
calls=[]
def fake_ollama(path,body=None,timeout=3):
 calls.append((path,body));return {'models':[{'name':'test-local'},{'name':'remote:cloud'},{'name':'other','remote_host':'x'}]} if path=='/api/tags' else {'message':{'content':'这是一条仅用于接口测试的假模型回答，不是实际推理'}}
c.ollama=fake_ollama;assert c.ai_status()['models']==['test-local'];c.chat(owner,{'question':'解释一下循环','mode':'local_ai','model':'test-local','include_context':False});body=calls[-1][1];assert '湖北师范' not in json.dumps(body,ensure_ascii=False) and len(body['messages'])==2
c.post(owner,'/api/companion/clear-chat',{});assert not c.get(owner,'/api/companion/chat')['items'];assert c.get(student,'/api/companion/feedback')['items']
with zipfile.ZipFile(io.BytesIO(full_backup(root))) as z:assert 'data/companion.sqlite3' in z.namelist()
assert d.calls==[],'tests must not create real desktop notices'
assert companion.eligible_title('2027年普通专升本改革') and not companion.eligible_title('2027年成人高考专升本改革')
print('COMPANION UNIT PASS:31 coverage gates;route filtering;official-title candidates vs reviewed facts;adult/unrelated/external excluded;5min cache;fetch failure retention;no historical push;student isolation/admin replies;reference-year guard;mock-only AI contract and context opt-out;export/full backup;0 real model calls/Windows notifications')
