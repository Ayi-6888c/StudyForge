# -*- coding: utf-8 -*-
"""Local identities, per-student stores and draft/publish admissions catalog."""
import hashlib,hmac,json,re,secrets,sqlite3,time,threading
from contextlib import contextmanager
from datetime import date,datetime,timedelta
from http.cookies import SimpleCookie
from urllib.parse import urlparse

def stamp():return datetime.now().astimezone().isoformat(timespec='seconds')
def dump(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'))
def safe_url(s):
 if not isinstance(s,str) or len(s)>1800:return False
 p=urlparse(s);return p.scheme in ('http','https') and bool(p.hostname) and not p.username and not p.password
def validate_catalog(data):
 if not isinstance(data,dict) or data.get('schema_version')!=1:raise ValueError('目录须使用schema_version=1')
 for k,limit in [('provinces',34),('schools',1000),('source_majors',1500),('offerings',10000)]:
  if not isinstance(data.get(k),list) or not 1<=len(data[k])<=limit:raise ValueError('目录字段或数量不正确：'+k)
 if not isinstance(data.get('version'),str) or not 1<=len(data['version'])<=80:raise ValueError('请填写目录版本名称')
 provinces={};schools={};sources={};ids=set()
 for p in data['provinces']:
  if p.get('id') in provinces or not re.fullmatch(r'[a-z][a-z0-9-]{0,39}',p.get('id','')):raise ValueError('省份ID重复或格式不正确')
  if not safe_url(p.get('source_url')):raise ValueError('省份缺少官方来源链接')
  provinces[p['id']]=p
 for s in data['schools']:
  if s.get('id') in schools or s.get('province') not in provinces:raise ValueError('学校ID重复或所属省份不存在')
  if not s.get('name') or not safe_url(s.get('source_url')):raise ValueError('学校缺少名称或来源')
  schools[s['id']]=s
 for s in data['source_majors']:
  if s.get('code') in sources or not re.fullmatch(r'[45]\d{5}K?',s.get('code','')) or not s.get('name'):raise ValueError('专科专业代码、名称或唯一性不正确')
  sources[s['code']]=s
 for o in data['offerings']:
  if o.get('id') in ids or not re.fullmatch(r'[A-Za-z0-9-]{2,100}',o.get('id','')) or o.get('school_id') not in schools:raise ValueError('招生项目ID重复、格式错误或学校不存在')
  ids.add(o['id'])
  if not isinstance(o.get('major_name'),str) or not 1<=len(o['major_name'])<=50:raise ValueError('本科专业名称不正确')
  if o.get('candidate_type')!='ordinary':raise ValueError('当前匹配器只处理普通考生，请分版本维护其他类别')
  if not isinstance(o.get('year'),int) or not 2020<=o['year']<=2035:raise ValueError('招生项目年份不正确')
  if o.get('offering_status') not in ('verified','pending','withdrawn'):raise ValueError('招生状态不正确')
  if not safe_url(o.get('source_url')):raise ValueError('招生项目缺少来源链接')
  date.fromisoformat(o.get('checked_at',''))
  e=o.get('eligibility',{})
  if e.get('status') not in ('verified','pending') or not isinstance(e.get('any'),bool) or not isinstance(e.get('closed'),bool):raise ValueError('专业对应规则状态不正确')
  if not safe_url(e.get('source_url')) or not isinstance(e.get('note'),str) or len(e['note'])>5000:raise ValueError('对应规则需要核验说明及来源')
  for key in ('names','prefixes','codes'):
   if not isinstance(e.get(key),list) or len(e[key])>1500 or any(not isinstance(x,str) or len(x)>150 for x in e[key]):raise ValueError('专业对应规则格式不正确')
  if any(not re.fullmatch(r'[45]\d(?:\d{2})?',x) for x in e['prefixes']):raise ValueError('类别范围须为2位或4位专科目录代码')
  if any(not re.fullmatch(r'[45]\d{5}K?',x) for x in e['codes']):raise ValueError('对应规则引用的专科专业代码格式不正确')
  if e['status']=='verified' and not (e['any'] or e['names'] or e['prefixes'] or e['codes']):raise ValueError('已核验范围需要明确的匹配条件')
  if not isinstance(o.get('exam_subjects'),list) or len(o['exam_subjects'])>10:raise ValueError('考试科目格式不正确')
  for x in o['exam_subjects']:
   if not x.get('name') or not safe_url(x.get('source_url')):raise ValueError('考试科目须填写名称与来源')
   for key in ('points','minutes'):
    if x.get(key) is not None and (not isinstance(x[key],int) or not 1<=x[key]<=1000):raise ValueError('分数或时长须为正整数或null')
  if o.get('learning_pack_id') not in ('','hubei-hbnu-cs'):raise ValueError('学习包适配器尚未接入')
  if o.get('learning_pack_id') and (schools[o['school_id']]['name']!='湖北师范大学' or o['major_name']!='计算机科学与技术'):raise ValueError('湖北师大计科学习包只适用于该校该专业，不套用到其他院校')
 return data

def match(o,source,year):
 e=o['eligibility'];hit=False;reason='专业对应范围待核对'
 if source and (source.get('code')=='manual' or not re.fullmatch(r'[45]\d{5}K?',source.get('code',''))):return {'state':'pending','label':'专业名称需人工核实','reason':'旧名称或手填名称没有核实到目录代码，不自动推定可报。'}
 if source and any(source['code'].startswith(p) for p in e.get('excluded_prefixes',[])):return {'state':'not_matched','label':'不在明确允许范围','reason':'学校对应要求明确排除了当前专科专业所属类别。'}
 if o['offering_status']=='withdrawn':return {'state':'withdrawn','label':'参考目录已停招','reason':'此招生项目在当前版本已标记停招'}
 if o['offering_status']!='verified':return {'state':'pending','label':'招生项目待核','reason':'本项目尚待核实，已有专业对应条件不代表招生项目已确认'}
 if e['status']=='verified' and source:
  if e['any']:hit=True;reason='学校'+str(o['year'])+'年对应要求注明不限专科专业，且当前专业不在明确排除范围'
  elif source['code'] in e['codes'] or source['name'] in e['names']:hit=True;reason='学校'+str(o['year'])+'年对应表明确列出“'+source['name']+'”'
  elif any(source['code'].startswith(p) for p in e['prefixes']):hit=True;reason='学校'+str(o['year'])+'年对应表明确允许当前专业所属类别（'+('、'.join(dict.fromkeys(source['category'] if len(p)==4 else source['group'] for p in e['prefixes'] if source['code'].startswith(p))))+'）'
 if hit:return {'state':'matched','label':str(o['year'])+'对应表明确允许','reason':reason+('；'+str(year)+'年正式招生及其他资格条件须依据当年文件' if year!=o['year'] else '；仍须通过学校资格审核')}
 if e['status']=='verified' and e['closed'] and source:return {'state':'not_matched','label':'参考范围未匹配','reason':'未命中已整理的明确限定范围，请核对当年学校简章'}
 return {'state':'pending','label':'对应范围待核','reason':'未命中不等于不可报；相近专业、旧专业名称和附加条件需对照学校原文确认'}

class StudentPlatform:
 def __init__(self,data_dir,assets):
  self.root=data_dir;self.path=data_dir/'platform.sqlite3';self.assets=assets;self.lock=threading.RLock()
  data_dir.mkdir(parents=True,exist_ok=True)
  with self.connection() as c:
   c.executescript('''
   CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE COLLATE NOCASE NOT NULL,display_name TEXT NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL,created_at TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),expires INTEGER NOT NULL);
   CREATE TABLE IF NOT EXISTS catalog_versions(id INTEGER PRIMARY KEY,label TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,actor_id INTEGER,note TEXT NOT NULL,base_id INTEGER);
   CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor_id INTEGER,action TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS login_failures(username TEXT PRIMARY KEY,count INTEGER NOT NULL,window_start INTEGER NOT NULL);
   ''')
   for name,definition in [('recovery_hash',"TEXT NOT NULL DEFAULT ''"),('recovery_created',"TEXT NOT NULL DEFAULT ''")]:
    if name not in [x[1] for x in c.execute('PRAGMA table_info(users)')]:c.execute('ALTER TABLE users ADD COLUMN '+name+' '+definition)
   c.execute("CREATE TABLE IF NOT EXISTS session_details(token_hash TEXT PRIMARY KEY REFERENCES sessions(token_hash) ON DELETE CASCADE,created_at TEXT NOT NULL,device TEXT NOT NULL)")
   if not c.execute('SELECT 1 FROM users WHERE id=1').fetchone():c.execute('INSERT INTO users(id,username,display_name,password_hash,role,created_at) VALUES(1,?,?,?,?,?)',('local-owner','我的学习空间','','owner',stamp()))
   if not c.execute("SELECT 1 FROM settings WHERE key='catalog_active'").fetchone():
    raw=json.loads((assets/'hubei_catalog.json').read_text(encoding='utf8'));validate_catalog(raw)
    cur=c.execute('INSERT INTO catalog_versions(label,payload,created_at,actor_id,note,base_id) VALUES(?,?,?,?,?,?)',(raw['version'],dump(raw),stamp(),1,'内置湖北参考目录',None))
    c.execute('INSERT INTO settings VALUES(?,?)',('catalog_active',str(cur.lastrowid)))
 @contextmanager
 def connection(self):
  c=sqlite3.connect(str(self.path),timeout=20);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
  try:
   with c:yield c
  finally:c.close()
 def public_user(self,u):return dict(id=u['id'],username=u['username'],display_name=u['display_name'],role=u['role'],claimed=bool(u['password_hash']))
 def session(self,handler,allow_guest=False):
  token=''
  try:
   cookie=SimpleCookie();cookie.load(handler.headers.get('Cookie',''));token=cookie['sf_session'].value if 'sf_session' in cookie else ''
  except Exception:pass
  with self.connection() as c:
   row=c.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?',(hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone() if token else None
   if row:return dict(row)
   owner=c.execute('SELECT * FROM users WHERE id=1').fetchone()
   if allow_guest and not owner['password_hash']:
    self.issue(handler,1,c);return dict(owner)
  return None
 def issue(self,handler,uid,c,remember=True):
  token=secrets.token_urlsafe(32);expires=int(time.time())+(7*86400 if remember else 12*3600)
  c.execute('DELETE FROM sessions WHERE expires<?',(int(time.time()),))
  th=hashlib.sha256(token.encode()).hexdigest()
  c.execute('INSERT INTO sessions(token_hash,user_id,expires) VALUES(?,?,?)',(th,uid,expires))
  c.execute('INSERT INTO session_details VALUES(?,?,?)',(th,stamp(),'本机浏览器'))
  handler.session_cookie='sf_session='+token+'; HttpOnly; SameSite=Strict; Path=/'+('; Max-Age=604800' if remember else '')
 def auth(self,handler,path,data,user):
  if path in ('/api/auth/profile','/api/auth/password','/api/auth/recovery-code','/api/auth/logout-others'):return self.account_action(handler,path,data,user)
  if path=='/api/auth/recover':return self.recover(data)
  username=str(data.get('username','')).strip().lower();password=data.get('password','');display=str(data.get('display_name','')).strip()
  with self.connection() as c:
   if path=='/api/auth/logout':
    cookie=SimpleCookie();cookie.load(handler.headers.get('Cookie',''));token=cookie['sf_session'].value if 'sf_session' in cookie else ''
    c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),));handler.session_cookie='sf_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0';return {'ok':True}
   if path not in ('/api/auth/register','/api/auth/login','/api/auth/claim'):raise ValueError('账号操作不存在')
   if not re.fullmatch(r'[a-z0-9_\-]{3,32}',username):raise ValueError('账号请用3—32位英文字母、数字、下划线或短横线')
   if not isinstance(password,str) or not 8<=len(password)<=128:raise ValueError('密码请设为8—128位')
   if 'confirm_password' in data and password!=data['confirm_password']:raise ValueError('两次输入的密码不一致')
   failure=c.execute('SELECT * FROM login_failures WHERE username=?',(username,)).fetchone()
   if failure and failure['count']>=10 and time.time()-failure['window_start']<300:raise ValueError('登录尝试较多，请5分钟后再试')
   if path.endswith('login'):
    u=c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
    if not u or not self.verify(password,u['password_hash']):
     n=failure['count']+1 if failure and time.time()-failure['window_start']<300 else 1;start=failure['window_start'] if n>1 else int(time.time())
     c.execute('INSERT OR REPLACE INTO login_failures VALUES(?,?,?)',(username,n,start));return {'error':'账号或密码不正确','status':400}
    c.execute('DELETE FROM login_failures WHERE username=?',(username,));self.issue(handler,u['id'],c,data.get('remember',True) is not False);return {'ok':True,'user':self.public_user(u)}
   if not display or len(display)>30:raise ValueError('请填写1—30字的昵称')
   if c.execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone():raise ValueError('这个账号已被使用')
   ph=self.hash_password(password)
   if path.endswith('claim'):
    owner=c.execute('SELECT * FROM users WHERE id=1').fetchone()
    if not user or user['id']!=1 or owner['password_hash']:raise ValueError('当前学习空间已经设置账号，请使用登录')
    c.execute('UPDATE users SET username=?,display_name=?,password_hash=? WHERE id=1',(username,display,ph));uid=1
    c.execute('DELETE FROM sessions WHERE user_id=1')
   else:
    cur=c.execute('INSERT INTO users(username,display_name,password_hash,role,created_at) VALUES(?,?,?,?,?)',(username,display,ph,'student',stamp()));uid=cur.lastrowid
   recovery=self.make_recovery(c,uid)
   self.issue(handler,uid,c,data.get('remember',True) is not False);self.audit(c,uid,'account.created','本地学习账号')
   return {'ok':True,'user':self.public_user(c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()),'new_student':uid!=1,'recovery_code':recovery}
 def token_hash(self,handler):
  cookie=SimpleCookie();cookie.load(handler.headers.get('Cookie',''));token=cookie['sf_session'].value if 'sf_session' in cookie else '';return hashlib.sha256(token.encode()).hexdigest()
 def make_recovery(self,c,uid):
  raw=secrets.token_hex(16).upper();code='SG-'+'-'.join(raw[i:i+4] for i in range(0,len(raw),4))
  c.execute('UPDATE users SET recovery_hash=?,recovery_created=? WHERE id=?',(self.hash_password(raw),stamp(),uid));return code
 def recovery_value(self,code):
  value=re.sub('[^A-Z0-9]','',str(code).upper());return value[2:] if value.startswith('SG') else value
 def recover(self,data):
  username=str(data.get('username','')).strip().lower();password=data.get('password','')
  if not re.fullmatch(r'[a-z0-9_\-]{3,32}',username) or not isinstance(password,str) or not 8<=len(password)<=128:raise ValueError('请核对账号格式和8—128位的新密码')
  if password!=data.get('confirm_password',password):raise ValueError('两次输入的新密码不一致')
  with self.connection() as c:
   key='recover:'+username;f=c.execute('SELECT * FROM login_failures WHERE username=?',(key,)).fetchone()
   if f and f['count']>=10 and time.time()-f['window_start']<300:raise ValueError('尝试较多，请5分钟后再试')
   u=c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone();code=self.recovery_value(data.get('recovery_code',''))
   if not u or len(code)!=32 or not self.verify(code,u['recovery_hash']):
    count=f['count']+1 if f and time.time()-f['window_start']<300 else 1;c.execute('INSERT OR REPLACE INTO login_failures VALUES(?,?,?)',(key,count,f['window_start'] if count>1 else int(time.time())));return {'error':'账号或恢复码不正确','status':400}
   c.execute('UPDATE users SET password_hash=? WHERE id=?',(self.hash_password(password),u['id']));c.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],));c.execute('DELETE FROM login_failures WHERE username IN (?,?)',(key,username));newcode=self.make_recovery(c,u['id']);self.audit(c,u['id'],'account.recovered','恢复码重置密码，旧会话与旧恢复码失效')
   return {'ok':True,'recovery_code':newcode,'username':username}
 def account_get(self,handler,user):
  if not user:raise PermissionError('请先登录')
  with self.connection() as c:
   u=c.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone();sessions=[dict(x) for x in c.execute("SELECT s.token_hash,s.expires,COALESCE(d.created_at,'') created_at,COALESCE(d.device,'本机浏览器') device FROM sessions s LEFT JOIN session_details d ON d.token_hash=s.token_hash WHERE s.user_id=? AND s.expires>? ORDER BY created_at DESC",(user['id'],int(time.time())))]
   for x in sessions:x['current']=x.pop('token_hash')==self.token_hash(handler)
   events=[dict(x) for x in c.execute("SELECT action,detail,created_at FROM audit WHERE actor_id=? AND action LIKE 'account.%' ORDER BY id DESC LIMIT 8",(user['id'],))]
   return {'user':self.public_user(u),'sessions':sessions,'recovery_ready':bool(u['recovery_hash']),'recovery_created':u['recovery_created'],'events':events,'storage':'local','cloud_connected':False}
 def account_action(self,handler,path,data,user):
  if not user:raise PermissionError('请先登录')
  with self.connection() as c:
   u=c.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone()
   if path.endswith('profile'):
    name=str(data.get('display_name','')).strip()
    if not 1<=len(name)<=30:raise ValueError('昵称请填写1—30字')
    c.execute('UPDATE users SET display_name=? WHERE id=?',(name,user['id']));self.audit(c,user['id'],'account.profile','更新昵称');return {'ok':True,'user':self.public_user(c.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone())}
   if not self.verify(str(data.get('current_password','')),u['password_hash']):raise ValueError('当前密码不正确')
   if path.endswith('password'):
    password=data.get('password','')
    if not isinstance(password,str) or not 8<=len(password)<=128:raise ValueError('新密码请设为8—128位')
    if password!=data.get('confirm_password',password):raise ValueError('两次输入的新密码不一致')
    c.execute('UPDATE users SET password_hash=? WHERE id=?',(self.hash_password(password),user['id']));c.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],));self.issue(handler,user['id'],c);self.audit(c,user['id'],'account.password','修改密码并退出其他会话');return {'ok':True}
   if path.endswith('recovery-code'):
    code=self.make_recovery(c,user['id']);self.audit(c,user['id'],'account.recovery','重新生成恢复码，旧码失效');return {'ok':True,'recovery_code':code}
   if path.endswith('logout-others'):
    c.execute('DELETE FROM sessions WHERE user_id=? AND token_hash<>?',(user['id'],self.token_hash(handler)));self.audit(c,user['id'],'account.sessions','退出其他登录会话');return {'ok':True}
   raise ValueError('账号操作不存在')
 def hash_password(self,password):
  salt=secrets.token_hex(16);return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),240000).hex()
 def verify(self,password,value):
  if not value:return False
  salt,expected=value.split(':',1);return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),240000).hex(),expected)
 def audit(self,c,uid,action,detail):c.execute('INSERT INTO audit(actor_id,action,detail,created_at) VALUES(?,?,?,?)',(uid,action,detail,stamp()))
 def database_path(self,user):
  if user['id']==1:return self.root/'studyforge.sqlite3'
  p=self.root/'students'/str(int(user['id']));p.mkdir(parents=True,exist_ok=True);return p/'studyforge.sqlite3'
 def active(self):
  with self.connection() as c:
   row=c.execute("SELECT v.* FROM catalog_versions v JOIN settings s ON s.key='catalog_active' AND v.id=CAST(s.value AS INTEGER)").fetchone()
   return row['id'],json.loads(row['payload'])
 def catalog(self,source_code='',year=2027):
  rev,data=self.active();source=next((x for x in data['source_majors'] if x['code']==source_code),None)
  school={x['id']:x for x in data['schools']};items=[]
  for o in data['offerings']:
   x=dict(o);x['school_name']=school[o['school_id']]['name'];x['province']=school[o['school_id']]['province'];x['match']=match(o,source,year);items.append(x)
  return dict(data,revision=rev,offerings=items,coverage={'schools':len(data['schools']),'listed_schools':len({o['school_id'] for o in items}),'offerings':len(items),'majors':len({o['major_name'] for o in items}),'structured_rules':sum(o['eligibility']['status']=='verified' for o in items),'learning_packs':sum(bool(o['learning_pack_id']) for o in items)})
 def admin_get(self,user):
  self.require_owner(user)
  with self.connection() as c:
   versions=[dict(r) for r in c.execute('SELECT id,label,created_at,actor_id,note,base_id FROM catalog_versions ORDER BY id DESC LIMIT 50')]
   draft=c.execute("SELECT value FROM settings WHERE key='catalog_draft'").fetchone();active=self.active()[0]
   audit=[dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 30')]
  return {'versions':versions,'active':active,'catalog':self.active()[1],'draft':json.loads(draft[0]) if draft else None,'audit':audit}
 def require_owner(self,user):
  if not user or user['role']!='owner':raise PermissionError('此操作需要本机资料管理员账号')
 def diff(self,before,after):
  result={}
  for key,pk in [('provinces','id'),('schools','id'),('source_majors','code'),('offerings','id')]:
   a={x[pk]:x for x in before[key]};b={x[pk]:x for x in after[key]};result[key]={'added':len(b.keys()-a.keys()),'removed':len(a.keys()-b.keys()),'changed':sum(a[i]!=b[i] for i in a.keys()&b.keys())}
  return result
 def admin_post(self,user,path,data):
  self.require_owner(user)
  with self.lock,self.connection() as c:
   active,old=self.active()
   if path.endswith('draft'):
    payload=validate_catalog(data['catalog']);base=int(data['base_revision'])
    if base!=active:raise ValueError('当前目录已更新，请重新载入后再编辑')
    d={'base_revision':base,'catalog':payload,'note':str(data.get('note',''))[:500],'diff':self.diff(old,payload),'saved_at':datetime.now().astimezone().isoformat(timespec='microseconds')}
    c.execute("INSERT OR REPLACE INTO settings VALUES('catalog_draft',?)",(dump(d),));self.audit(c,user['id'],'catalog.draft',dump(d['diff']));return d
   if path.endswith('publish'):
    row=c.execute("SELECT value FROM settings WHERE key='catalog_draft'").fetchone()
    if not row:raise ValueError('请先保存并校验草稿')
    d=json.loads(row[0])
    if int(data['base_revision'])!=active or d['base_revision']!=active or str(data.get('saved_at',''))!=d['saved_at']:raise ValueError('目录或草稿已变化，请重新预览再发布')
    payload=validate_catalog(d['catalog']);note=d['note'] or '人工校验后发布'
   elif path.endswith('rollback'):
    if int(data['base_revision'])!=active:raise ValueError('当前版本已变化，请刷新版本历史')
    row=c.execute('SELECT * FROM catalog_versions WHERE id=?',(int(data['version_id']),)).fetchone()
    if not row:raise ValueError('目标版本不存在')
    payload=validate_catalog(json.loads(row['payload']));note='恢复历史版本 #'+str(row['id'])+'；学习记录保持不变'
   else:raise ValueError('资料管理操作不存在')
   cur=c.execute('INSERT INTO catalog_versions(label,payload,created_at,actor_id,note,base_id) VALUES(?,?,?,?,?,?)',(payload['version'],dump(payload),stamp(),user['id'],note,active))
   c.execute("UPDATE settings SET value=? WHERE key='catalog_active'",(str(cur.lastrowid),));c.execute("DELETE FROM settings WHERE key='catalog_draft'");self.audit(c,user['id'],'catalog.publish' if path.endswith('publish') else 'catalog.rollback',note)
   return {'ok':True,'revision':cur.lastrowid,'diff':self.diff(old,payload),'note':'新目录已发布；学生档案和计划保留原快照，由学生确认更新。'}

ROUTE_COLUMNS={'student_route':('id','payload','updated_at'),'student_route_history':('id','payload','created_at')}
def init_routes(con):
 con.executescript('''CREATE TABLE IF NOT EXISTS student_route(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL,updated_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS student_route_history(id INTEGER PRIMARY KEY,payload TEXT NOT NULL,created_at TEXT NOT NULL);''')
def route(con):
 row=con.execute('SELECT payload FROM student_route WHERE id=1').fetchone();return json.loads(row[0]) if row else None
def write_route(con,p):
 old=route(con)
 if old:con.execute('INSERT INTO student_route_history(payload,created_at) VALUES(?,?)',(dump(old),stamp()))
 con.execute('INSERT OR REPLACE INTO student_route VALUES(1,?,?)',(dump(p),stamp()))
def validate_saved_route(saved):
 if not isinstance(saved,dict):raise ValueError('备份档案须为对象')
 for key in ('province','offering_id','school_name','catalog_version','start_date','deadline','intensity'):
  if not isinstance(saved.get(key),str) or not 1<=len(saved[key])<=200:raise ValueError('备份档案字段不正确：'+key)
 o=saved.get('offering',{});src=saved.get('source_major',{})
 if not isinstance(o,dict) or not isinstance(src,dict) or not src.get('name') or not src.get('code') or not o.get('major_name'):raise ValueError('备份档案缺少专科/本科专业')
 if saved['offering_id']!=o.get('id') or not safe_url(o.get('source_url')) or not safe_url(o.get('eligibility',{}).get('source_url')):raise ValueError('备份档案项目ID或来源不一致')
 if not isinstance(saved.get('match'),dict) or not saved['match'].get('reason') or not isinstance(saved.get('catalog_revision'),int):raise ValueError('备份档案缺少版本及匹配状态')
 if not 2026<=int(saved.get('target_year',0))<=2035 or not 150<=int(saved.get('daily_minutes',0))<=480:raise ValueError('备份档案年份或时长不正确')
 if not 28<=(date.fromisoformat(saved['deadline'])-date.fromisoformat(saved['start_date'])).days+1<=730:raise ValueError('备份档案日期不正确')
 if o.get('learning_pack_id') not in ('','hubei-hbnu-cs'):raise ValueError('备份引用的学习包未接入')
 if o.get('learning_pack_id') and (saved['school_name']!='湖北师范大学' or o['major_name']!='计算机科学与技术' or o['school_id']!='hb-04' or o['id']!='hb-04-080901'):raise ValueError('备份的学习包与院校专业不一致')
 return saved
def validate_selection(platform,data):
 if data.get('candidate_type','ordinary')!='ordinary':raise ValueError('当前已接入普通考生路线，请核对对应身份的独立要求')
 revision,catalog=platform.active();source=next((x for x in catalog['source_majors'] if x['code']==data.get('source_code')),None)
 custom=str(data.get('source_name','')).strip()
 if source is None:
  if not 2<=len(custom)<=60:raise ValueError('请选择你的专科专业，或填写学信网所示专业旧名称')
  source={'code':'manual','name':custom,'category':'旧名称/手填·待核','group':''}
 offering=next((x for x in catalog['offerings'] if x['id']==data.get('offering_id')),None)
 if not offering:raise ValueError('请选择目录中已收录的学校本科专业项目')
 school=next(x for x in catalog['schools'] if x['id']==offering['school_id'])
 if school['province']!=data.get('province'):raise ValueError('省份与学校不一致，请重新联动选择')
 if int(data.get('catalog_revision',0))!=revision:raise ValueError('目录已有更新，请刷新核对后再保存')
 year=int(data.get('target_year',2027))
 if not 2026<=year<=2035:raise ValueError('目标年份请填2026至2035')
 m=match(offering,source,year)
 if m['state']!='matched':raise ValueError('该专科专业没有明确的允许报考依据，此项目仅供查阅资料，不列为可选目标')
 if catalog.get('selection_policy')=='positive_evidence_only' and not offering.get('evidence',{}).get('selection_ready'):raise ValueError('此项目的对应要求或专业课资料尚未配齐，补齐核对后再选择；资料入口仍可查阅')
 if not data.get('acknowledged'):raise ValueError('请确认已区分参考年度匹配与学校正式审核')
 start=date.fromisoformat(str(data.get('start_date','2026-10-25')));end=date.fromisoformat(str(data.get('deadline','2027-04-16')))
 if not 28<=(end-start).days+1<=730:raise ValueError('学习周期请设为28至730天')
 intensity=str(data.get('intensity','standard'));minutes={'light':180,'standard':270,'intensive':360}.get(intensity,int(data.get('daily_minutes',270)))
 if intensity not in ('light','standard','intensive','custom') or not 150<=minutes<=480:raise ValueError('学习强度请设为150至480分钟')
 return {'province':school['province'],'source_major':source,'offering_id':offering['id'],'target_year':year,'candidate_type':'ordinary','catalog_revision':revision,'catalog_version':catalog['version'],'school_name':school['name'],'offering':offering,'match':m,'start_date':start.isoformat(),'deadline':end.isoformat(),'intensity':intensity,'daily_minutes':minutes,'acknowledged_at':stamp()}

def generic_plan(con,p):
 """An explicitly provisional English + syllabus preparation schedule, not a fake subject pack."""
 start=date.fromisoformat(p['start_date']);end=date.fromisoformat(p['deadline']);subjects=p['offering']['exam_subjects'];pro=[x['name'] for x in subjects if x['name'] not in ('英语','大学英语')]
 def subject(name,icon):
  row=con.execute('SELECT id FROM subjects WHERE name=?',(name,)).fetchone()
  if row:return row[0]
  return con.execute('INSERT INTO subjects(name,icon,color,exam_date,created_at) VALUES(?,?,?,?,?)',(name,icon,'#81a79b','',stamp())).lastrowid
 english=subject('大学英语','Aa');professional=subject('报考资料与考纲整理','▤');count=0
 for d in range((end-start).days+1):
  day=(start+timedelta(days=d)).isoformat();budget=round(p['daily_minutes']*(.7 if d%7==6 else 1)/5)*5;e=round(budget*.35/5)*5
  detail='词汇主动回忆、语法输出、阅读简答/翻译/写作轮换；按1/3/7天复测。当前是通用英语训练任务，不是目标学校押题。'
  tasks=[(english,'大学英语｜'+['词汇与语法输出','阅读简答与复述','翻译与改写','短文写作','混合训练','查漏补缺','本周复盘'][d%7],detail,e,'practice')]
  topic='、'.join(pro) or '学校专业课科目（尚待补全）'
  tasks.append((professional,'专业课准备｜'+('核对考纲与课程目录' if d<3 else '按自有课程学习并交付'), '目标：'+p['school_name']+' · '+p['offering']['major_name']+'。科目：'+topic+'。本路线尚未接入专属章节题库：先在学校原文核对科目/教材/章节，再导入自己的课程，创建具体章任务。交付：一页概念复述、两道独立练习与一份错误分析；章节与题量由本人课程落实。此任务是过渡模板，不表示已配齐专业课学习包。',budget-e,'practice'))
  for sid,title,detail,mins,kind in tasks:
   con.execute('INSERT INTO tasks(subject_id,due_date,title,detail,minutes,kind,status,source,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(sid,day,title,detail,mins,kind,'todo','route-v4:'+p['offering_id'],stamp()));count+=1
 return count
