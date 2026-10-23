# -*- coding: utf-8 -*-
"""StudyForge: local, multi-subject study desk. Python 3.8+, standard library only."""
import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import webbrowser
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
if __name__ == '__main__' and any(x in sys.argv for x in ('--desktop-reminder','--desktop-reminder-remove','--desktop-open')):
    from desktop_notifications import cli
    sys.exit(cli())
from desktop_notifications import DesktopReminder
from desktop_window import open_window
from exam_engine import ExamEngine, EXTRA_COLUMNS
from learning_tools import library as learning_library, post as learning_post
from student_platform import StudentPlatform, ROUTE_COLUMNS, init_routes, route, write_route, validate_selection, validate_saved_route, generic_plan
from companion import Companion
from customer_workspace import WORKSPACE_COLUMNS, WorkspaceConflict, init_workspace, workspace_get, workspace_post, validate_item, snapshot_database, snapshot_list, statistics, full_backup

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
ASSETS_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
DATA_DIR = Path(os.environ.get("STUDYFORGE_DATA_DIR", str(APP_DIR / "data")))
DB_PATH = DATA_DIR / "studyforge.sqlite3"
DESKTOP = DesktopReminder(DATA_DIR,ASSETS_DIR,APP_DIR,[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,str(APP_DIR/'app.py')])
MAX_BODY = 20_000_000
EXAMS = ExamEngine(ASSETS_DIR)
PLATFORM = StudentPlatform(DATA_DIR, ASSETS_DIR)
COMPANION = Companion(DATA_DIR, ASSETS_DIR, PLATFORM, DESKTOP)
REQUEST_DB = ContextVar('student_database', default=None)


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(REQUEST_DB.get() or DB_PATH), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    init_workspace(con)
    return con


@contextmanager
def connection():
    con = db()
    try:
        with con:
            yield con
    finally:
        con.close()


def init_db(seed=True):
    with connection() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS subjects(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, icon TEXT NOT NULL DEFAULT '◇',
          color TEXT NOT NULL DEFAULT '#77e1db', exam_date TEXT DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(
          id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
          due_date TEXT NOT NULL, title TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
          minutes INTEGER NOT NULL DEFAULT 45, kind TEXT NOT NULL DEFAULT 'practice',
          status TEXT NOT NULL DEFAULT 'todo', source TEXT NOT NULL DEFAULT 'custom',
          created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date,subject_id);
        CREATE TABLE IF NOT EXISTS submissions(
          id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
          content TEXT NOT NULL, language TEXT NOT NULL DEFAULT 'text',
          tests_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reviews(
          id INTEGER PRIMARY KEY, submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
          mode TEXT NOT NULL, verdict TEXT NOT NULL, feedback TEXT NOT NULL,
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS focus_sessions(
          id INTEGER PRIMARY KEY, task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
          day TEXT NOT NULL, minutes INTEGER NOT NULL, ended_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_focus_day ON focus_sessions(day);
        CREATE TABLE IF NOT EXISTS journals(
          day TEXT PRIMARY KEY, mood TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL);
        """)
        EXAMS.init(con)
        init_routes(con)
        if not seed:
            return
        if con.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]:
            return
        stamp = now()
        con.execute("INSERT INTO subjects(name,icon,color,exam_date,created_at) VALUES(?,?,?,?,?)",
                    ("C 语言", "</>", "#6cf2c2", "", stamp))
        c_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO subjects(name,icon,color,exam_date,created_at) VALUES(?,?,?,?,?)",
                    ("大学英语", "Aa", "#9f8cff", "", stamp))
        e_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        EXAMS.apply_plan(con, EXAMS.default_profile())


def owner_route(con):
    if route(con):
        return
    revision, catalog = PLATFORM.active()
    target = next(x for x in catalog['offerings'] if x.get('learning_pack_id') == 'hubei-hbnu-cs')
    p = EXAMS.profile(con)
    selected = validate_selection(PLATFORM,dict(province='hubei',source_code='510203',offering_id=target['id'],catalog_revision=revision,acknowledged=True,**{k:p[k] for k in ('target_year','start_date','deadline','intensity','daily_minutes')}))
    write_route(con,selected)


def rows(con, sql, args=()):
    return [dict(row) for row in con.execute(sql, args).fetchall()]


def valid_date(value):
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


@lru_cache(maxsize=1)
def get_compiler():
    requested = os.environ.get("CC", "")
    if requested:
        return shutil.which(requested)
    found = next((shutil.which(x) for x in ("gcc", "clang", "cc", "cl") if shutil.which(x)), None)
    if found:
        return found
    if os.name == 'nt':
        root = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio'
        choices = sorted(root.glob('*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe'), reverse=True)
        if choices:
            return str(choices[0])
    return None


@lru_cache(maxsize=2)
def msvc_environment(compiler):
    env = dict(os.environ)
    p = Path(compiler)
    try:
        vcvars = p.parents[6] / 'Auxiliary' / 'Build' / 'vcvars64.bat'
    except IndexError:
        return env
    if vcvars.exists():
        result = subprocess.run('call "' + str(vcvars) + '" >nul && set', shell=True, capture_output=True, text=True, encoding='mbcs', errors='replace', timeout=30)
        if result.returncode:
            raise OSError('MSVC 环境初始化失败：' + result.stderr[-1000:])
        for line in result.stdout.splitlines():
            if '=' in line and not line.startswith('='):
                k,v = line.split('=',1); env[k] = v
    return env


def normalize_output(s):
    return "\n".join(x.rstrip() for x in s.replace("\r\n", "\n").strip().split("\n"))


def code_execution_enabled():
    """Public source defaults to static review; execution is an explicit opt-in."""
    return os.environ.get("STUDYFORGE_ENABLE_CODE_EXECUTION") == "1"


def offline_review(code, language, tests):
    if language.lower() not in ("c", "c11", "c99"):
        return {"verdict": "已记录", "feedback": "这份作业已保存。离线自动检查目前针对 C 代码；其他学科可使用 AI 审阅或在聊天中提交。"}
    tips = []
    if not re.search(r"\bmain\s*\(", code):
        tips.append("未发现 main 函数；若是完整程序，请补上入口。")
    if code.count("{") != code.count("}"):
        tips.append("花括号数量不匹配，检查代码块是否闭合。")
    if re.search(r"\bgets\s*\(", code):
        tips.append("发现 gets；请改用有长度限制的输入方式。")
    if re.search(r"\bscanf\s*\(\s*\"[^\"]*%[diuf]\"\s*,\s*[a-zA-Z_]\w*\s*\)", code):
        tips.append("scanf 的数值变量参数可能缺少 &；请核对地址传参。")
    if not code_execution_enabled():
        tips.append("公开源码版默认不运行代码，本次仅做静态检查，未编译或执行样例。仅在个人电脑确认代码可信、配置编译器后，可设置 STUDYFORGE_ENABLE_CODE_EXECUTION=1 开启；这不是沙箱。")
        return {"verdict": "静态检查完成", "feedback": "\n".join(tips)}
    compiler = get_compiler()
    if not compiler:
        tips.append("本机未检测到 GCC/Clang/MSVC；本次仅做静态检查，编译与样例运行待配置编译器后执行。可设置 CC 环境变量。")
        return {"verdict": "静态检查完成", "feedback": "\n".join(tips or ["未发现上述常见静态问题；这不等于代码已经通过编译。"])}
    with tempfile.TemporaryDirectory(prefix="studyforge-") as tmp:
        src = Path(tmp) / "main.c"
        exe = Path(tmp) / ("main.exe" if os.name == "nt" else "main")
        src.write_text(code, encoding="utf-8")
        try:
            is_msvc = Path(compiler).name.lower() in ('cl.exe','cl')
            command = [compiler, '/nologo','/TC','/std:c11','/W4','/utf-8','/D_CRT_SECURE_NO_WARNINGS',str(src),'/Fe:'+str(exe)] if is_msvc else [compiler, "-std=c11", "-Wall", "-Wextra", str(src), "-o", str(exe)]
            build = subprocess.run(command, cwd=tmp, env=msvc_environment(compiler) if is_msvc else None,
                                   capture_output=True, text=True, encoding='mbcs' if is_msvc else None, timeout=30, errors="replace")
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"verdict": "编译未完成", "feedback": str(exc)}
        if build.returncode:
            return {"verdict": "编译失败", "feedback": "编译器信息：\n" + (build.stderr or build.stdout)[-6000:] + ("\n" + "\n".join(tips) if tips else "")}
        feedback = ["C11 编译通过。"]
        messages = build.stderr + ('\n' + build.stdout if is_msvc else '')
        if messages.strip():
            feedback.append("编译器信息：\n" + messages[-3000:])
        passed = 0
        for i, case in enumerate(tests[:5], 1):
            try:
                run = subprocess.run([str(exe)], input=str(case.get("input", "")), capture_output=True,
                                     text=True, timeout=3, errors="replace", cwd=tmp)
                good = run.returncode == 0 and normalize_output(run.stdout) == normalize_output(str(case.get("expected", "")))
                passed += int(good)
                feedback.append("样例 %d：%s；期望=%r，实际=%r%s" %
                                (i, "通过" if good else "不通过", case.get("expected", ""), run.stdout[:500],
                                 "；退出码=%d" % run.returncode if run.returncode else ""))
            except subprocess.TimeoutExpired:
                feedback.append("样例 %d：运行超过 3 秒，检查死循环。" % i)
        feedback.extend(tips)
        verdict = "样例通过 %d/%d" % (passed, min(len(tests), 5)) if tests else "编译通过，待添加测试样例"
        return {"verdict": verdict, "feedback": "\n".join(feedback)}


def ai_review(provider, model, subject, task, content, tests, offline):
    if not re.match(r"^[\w.:-]{2,100}$", model or ""):
        raise ValueError("模型名称格式不正确")
    prompt = ("请用中文批改学习作业。先指出已验证的事实，再指出可能的问题；不要编造运行结果。"
              "按‘结论、正确性、边界/测试、代码或表达规范、修改建议、下一步练习’组织回答。"
              "若不是代码作业，按该学科内容评价。\n"
              "学科：%s\n任务：%s\n提交内容：\n%s\n测试样例：%s\n离线检查：%s" %
              (subject, task, content[:20000], json.dumps(tests, ensure_ascii=False), offline))
    if provider == "ollama":
        req = urllib.request.Request("http://127.0.0.1:11434/api/generate",
              json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8"),
              {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as res:
            return json.load(res).get("response", "").strip()
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise ValueError("未设置 OPENAI_API_KEY 环境变量")
        req = urllib.request.Request("https://api.openai.com/v1/responses",
              json.dumps({"model": model, "input": prompt, "store": False}).encode("utf-8"),
              {"Content-Type": "application/json", "Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=90) as res:
            data = json.load(res)
        return "\n".join(part.get("text", "") for item in data.get("output", [])
                         if item.get("type") == "message" for part in item.get("content", [])
                         if part.get("type") == "output_text").strip()
    raise ValueError("仅支持 Ollama 或 OpenAI")


class Handler(BaseHTTPRequestHandler):
    server_version = "StudyForge/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("STUDYFORGE_DEBUG"):
            super().log_message(fmt, *args)

    def send_json(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if getattr(self, 'session_cookie', ''):
            self.send_header('Set-Cookie', self.session_cookie)
            self.session_cookie = ''
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def body(self):
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise ValueError("请求须为 application/json")
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > MAX_BODY:
            raise ValueError("提交内容过大")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError('请求内容须为JSON对象')
        return value

    def do_GET(self):
        path=urlparse(self.path).path
        if not self.valid_host():return
        try:
            if path=='/api/auth/state':
                user=PLATFORM.session(self,allow_guest=True)
                self.send_json({'user':PLATFORM.public_user(user) if user else None})
                return
            if path=='/api/catalog':
                q=parse_qs(urlparse(self.path).query)
                self.send_json(PLATFORM.catalog(q.get('source',[''])[0],int(q.get('year',['2027'])[0])))
                return
            if not path.startswith('/api/'):
                self._do_GET();return
            user=PLATFORM.session(self)
            if not user:self.send_json({'error':'请先登录本地学习账号'},401);return
            if self.headers.get('X-StudyForge-User') not in (None,'',str(user['id'])):
                self.send_json({'error':'另一个窗口已切换账号，请刷新当前页面再操作'},409);return
            self.user=user
            token=REQUEST_DB.set(PLATFORM.database_path(user))
            try:
                if path.startswith('/api/companion/'):
                    self.send_json(COMPANION.get(user,path));return
                if path=='/api/learning/library':
                    with connection() as con:self.send_json(learning_library(con,EXAMS))
                    return
                if path=='/api/desktop-reminder':self.send_json(dict(DESKTOP.status(),editable=user['role']=='owner'));return
                if path=='/api/account':self.send_json(PLATFORM.account_get(self,user));return
                if path=='/api/data/snapshots':self.send_json({'items':snapshot_list(PLATFORM.database_path(user))});return
                if path=='/api/data/full-backup':
                    PLATFORM.require_owner(user)
                    with PLATFORM.lock:payload=full_backup(DATA_DIR)
                    self.send_response(200);self.send_header('Content-Type','application/zip');self.send_header('Content-Disposition','attachment; filename="StudyForge-all-data.zip"');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload);return
                if path in ('/api/workspace','/api/statistics'):
                    with connection() as con:self.send_json(workspace_get(con,parse_qs(urlparse(self.path).query).get('key',[''])[0]) if path=='/api/workspace' else statistics(con))
                    return
                if path=='/api/admin/catalog':self.send_json(PLATFORM.admin_get(user));return
                if path=='/api/student':
                    with connection() as con:
                        selected=route(con)
                        if selected and selected['offering'].get('learning_pack_id'):
                            p=EXAMS.profile(con)
                            selected=dict(selected,**{k:p[k] for k in ('target_year','start_date','deadline','intensity','daily_minutes')})
                        active=PLATFORM.active()[0]
                        self.send_json({'user':PLATFORM.public_user(user),'route':selected,'active_revision':active,'update_available':bool(selected and selected['catalog_revision']!=active),'history':[dict(x) for x in con.execute('SELECT id,payload,created_at FROM student_route_history ORDER BY id DESC LIMIT 10')]})
                    return
                self._do_GET()
            finally:REQUEST_DB.reset(token)
        except PermissionError as exc:self.send_json({'error':str(exc)},403)
        except (ValueError,KeyError,TypeError,sqlite3.Error) as exc:self.send_json({'error':str(exc)},400)

    def valid_host(self):
        host=self.headers.get('Host','').split(':')[0].lower()
        if host not in ('127.0.0.1','localhost'):
            self.send_json({'error':'主机名不匹配'},403);return False
        return True

    def do_POST(self):
        if not self.valid_host():return
        origin=self.headers.get('Origin','')
        if origin and origin!='http://'+self.headers.get('Host',''):
            self.send_json({'error':'来源不匹配'},403);return
        path=urlparse(self.path).path
        try:
            user=PLATFORM.session(self)
            if path.startswith('/api/auth/'):
                if path in ('/api/auth/profile','/api/auth/password','/api/auth/recovery-code','/api/auth/logout-others','/api/auth/logout') and user and self.headers.get('X-StudyForge-User') not in (None,'',str(user['id'])):
                    self.send_json({'error':'另一个窗口已切换账号，请刷新再操作'},409);return
                result=PLATFORM.auth(self,path,self.body(),user)
                if result.get('new_student'):
                    newuser={'id':result['user']['id']}
                    with PLATFORM.lock:
                        token=REQUEST_DB.set(PLATFORM.database_path(newuser))
                        try:init_db(seed=False)
                        finally:REQUEST_DB.reset(token)
                self.send_json(result,result.pop('status',200));return
            if not user:self.send_json({'error':'请先登录本地学习账号'},401);return
            if self.headers.get('X-StudyForge-User') not in (None,'',str(user['id'])):
                self.send_json({'error':'另一个窗口已切换账号，请刷新当前页面再操作'},409);return
            self.user=user
            if path=='/api/quit':PLATFORM.require_owner(user)
            token=REQUEST_DB.set(PLATFORM.database_path(user))
            try:
                if path.startswith('/api/companion/'):
                    try:self.send_json(COMPANION.post(user,path,self.body()))
                    except (ValueError,OSError,urllib.error.URLError,TimeoutError) as exc:self.send_json({'error':str(exc)},400)
                    return
                if path in ('/api/desktop-reminder','/api/desktop-reminder/test'):
                    PLATFORM.require_owner(user)
                    try:self.send_json(DESKTOP.run(test=True) if path.endswith('/test') else DESKTOP.configure(self.body()));return
                    except Exception as exc:raise ValueError(str(exc))
                if path.startswith('/api/learning/'):
                    with connection() as con:self.send_json(learning_post(con,EXAMS,path,self.body()))
                    return
                if path=='/api/data/snapshot':self.send_json(snapshot_database(PLATFORM.database_path(user)));return
                if path in ('/api/workspace','/api/workspace/delete'):
                    with connection() as con:self.send_json(workspace_post(con,self.body(),path.endswith('delete')))
                    return
                if path.startswith('/api/admin/'):
                    self.send_json(PLATFORM.admin_post(user,path,self.body()));return
                if path in ('/api/student/preview','/api/student/route'):
                    data=self.body();selection=validate_selection(PLATFORM,data)
                    with connection() as con:
                        old=route(con)
                        if path.endswith('preview'):
                            protected=con.execute("SELECT COUNT(*) FROM tasks WHERE status<>'todo' OR id IN (SELECT task_id FROM submissions) OR id IN (SELECT task_id FROM focus_sessions WHERE task_id IS NOT NULL) OR EXISTS(SELECT 1 FROM workspace_items WHERE key='draft:'||tasks.id)").fetchone()[0]
                            self.send_json({'selection':selection,'plan_kind':'dedicated' if selection['offering'].get('learning_pack_id') else 'provisional','protected_tasks':protected,'days':(date.fromisoformat(selection['deadline'])-date.fromisoformat(selection['start_date'])).days+1,'note':'已有进度、自建任务、作业、专注记录保留；仅按你的确认替换范围内系统未开始任务。'});return
                        inserted=0
                        changed=bool(old and old['offering_id']!=selection['offering_id'])
                        if changed:
                            archived=rows(con,"SELECT * FROM tasks WHERE status='todo' AND (source LIKE 'exam-v3:%' OR source LIKE 'route-v4:%') AND id NOT IN (SELECT task_id FROM submissions) AND id NOT IN (SELECT task_id FROM focus_sessions WHERE task_id IS NOT NULL) AND NOT EXISTS(SELECT 1 FROM workspace_items WHERE key='draft:'||tasks.id)")
                            old['archived_unstarted_tasks']=archived
                            con.execute('UPDATE student_route SET payload=? WHERE id=1',(json.dumps(old,ensure_ascii=False),))
                            for t in archived:con.execute('DELETE FROM tasks WHERE id=?',(t['id'],))
                            con.execute("UPDATE exam_plan_runs SET status='retired-route' WHERE status='active'")
                        if data.get('generate_plan'):
                            if selection['offering'].get('learning_pack_id'):
                                profile=EXAMS.profile(con);profile.update({k:selection[k] for k in ('target_year','start_date','deadline','intensity','daily_minutes')})
                                profile['pack_id']=selection['offering']['learning_pack_id'];result=EXAMS.apply_plan(con,EXAMS.validate_profile(profile));inserted=result['inserted']
                            else:
                                con.execute("DELETE FROM tasks WHERE due_date BETWEEN ? AND ? AND status='todo' AND source LIKE 'route-v4:%' AND id NOT IN (SELECT task_id FROM submissions) AND id NOT IN (SELECT task_id FROM focus_sessions WHERE task_id IS NOT NULL) AND NOT EXISTS(SELECT 1 FROM workspace_items WHERE key='draft:'||tasks.id)",(selection['start_date'],selection['deadline']))
                                inserted=generic_plan(con,selection)
                        if selection['offering'].get('learning_pack_id'):
                            profile=EXAMS.profile(con);profile.update({k:selection[k] for k in ('target_year','start_date','deadline','intensity','daily_minutes')});EXAMS.save_profile(con,EXAMS.validate_profile(profile))
                        write_route(con,selection)
                    self.send_json({'ok':True,'route':selection,'inserted':inserted});return
                self._do_POST()
            finally:REQUEST_DB.reset(token)
        except WorkspaceConflict as exc:self.send_json({'error':str(exc),'conflict':True},409)
        except PermissionError as exc:self.send_json({'error':str(exc)},403)
        except (ValueError,KeyError,TypeError,OverflowError,sqlite3.Error) as exc:self.send_json({'error':str(exc)},400)

    def _do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/app.css", "/app.js", "/exam.css", "/exam.js", "/catalog.css", "/catalog.js", "/customer.js", "/customer.css", "/learning.js", "/learning.css", "/desktop.js", "/companion.js", "/companion.css"):
            name = "index.html" if u.path == "/" else u.path[1:]
            raw = (ASSETS_DIR / name).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ('text/html' if name.endswith('.html') else 'text/css' if name.endswith('.css') else 'text/javascript') + "; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        with connection() as con:
            if u.path.startswith('/api/exam/'):
                try:
                    selected=route(con)
                    if not selected or not selected['offering'].get('learning_pack_id'):
                        if u.path=='/api/exam/dashboard':
                            self.send_json({'ready':False,'route':selected,'note':'当前路线尚未接入专属题库与章节规划；请到院校专业库查看资料进度。'})
                        else:
                            self.send_json({'error':'当前路线尚未接入这一学科练习包'},400)
                        return
                    self.send_json(EXAMS.get(con,u.path,parse_qs(u.query)))
                except (ValueError, KeyError, TypeError) as exc:
                    self.send_json({'error': str(exc)},400)
                return
            if u.path == "/api/bootstrap":
                subjects = rows(con, "SELECT * FROM subjects ORDER BY id")
                tasks = rows(con, "SELECT t.*,s.name subject_name,s.color subject_color,s.icon subject_icon FROM tasks t JOIN subjects s ON s.id=t.subject_id ORDER BY due_date,id")
                reviews = rows(con, "SELECT r.*,u.task_id FROM reviews r JOIN submissions u ON u.id=r.submission_id ORDER BY r.id DESC LIMIT 8")
                focus = rows(con, "SELECT * FROM focus_sessions ORDER BY day,id")
                journals = rows(con, "SELECT * FROM journals ORDER BY day")
                self.send_json({"subjects": subjects, "tasks": tasks, "reviews": reviews,
                                "focus_sessions": focus, "journals": journals,
                                "compiler": code_execution_enabled() and bool(get_compiler()),
                                "code_execution_enabled": code_execution_enabled(),
                                "openai": bool(os.environ.get("OPENAI_API_KEY")),
                                "today": date.today().isoformat()})
                return
            if u.path == "/api/submissions":
                task_id = int(parse_qs(u.query).get("task_id", ["0"])[0])
                submissions = rows(con, "SELECT * FROM submissions WHERE task_id=? ORDER BY id DESC", (task_id,))
                for sub in submissions:
                    sub["reviews"] = rows(con, "SELECT * FROM reviews WHERE submission_id=? ORDER BY id DESC", (sub["id"],))
                self.send_json({"submissions": submissions})
                return
            if u.path == "/api/export":
                self.send_json({name: rows(con, "SELECT * FROM " + name) for name in
                                ("subjects", "tasks", "submissions", "reviews", "focus_sessions", "journals") + tuple(EXTRA_COLUMNS) + tuple(ROUTE_COLUMNS) + tuple(WORKSPACE_COLUMNS)})
                return
        self.send_json({"error": "未找到"}, 404)

    def _do_POST(self):
        origin = self.headers.get("Origin", "")
        if origin and origin != "http://%s" % self.headers.get("Host", ""):
            self.send_json({"error": "来源不匹配"}, 403)
            return
        try:
            data = self.body()
            path = urlparse(self.path).path
            with connection() as con:
                if path.startswith('/api/exam/'):
                    selected=route(con)
                    if not selected or not selected['offering'].get('learning_pack_id'):
                        raise ValueError('当前路线尚未接入这一学科练习包')
                    self.send_json(EXAMS.post(con,path,data,offline_review,ai_review))
                    return
                if path == "/api/subjects":
                    name = str(data.get("name", "")).strip()[:40]
                    if not name:
                        raise ValueError("请输入学科名称")
                    con.execute("INSERT INTO subjects(name,icon,color,exam_date,created_at) VALUES(?,?,?,?,?)",
                                (name, str(data.get("icon", "◇"))[:4], str(data.get("color", "#77e1db"))[:20],
                                 str(data.get("exam_date", ""))[:10], now()))
                    self.send_json({"ok": True, "id": con.execute("SELECT last_insert_rowid()").fetchone()[0]})
                    return
                if path == "/api/tasks":
                    if not valid_date(data.get("due_date")):
                        raise ValueError("日期格式不正确")
                    title = str(data.get("title", "")).strip()[:140]
                    if not title:
                        raise ValueError("请输入任务名称")
                    sid = int(data["subject_id"])
                    if not con.execute("SELECT 1 FROM subjects WHERE id=?", (sid,)).fetchone():
                        raise ValueError("学科不存在")
                    kind = str(data.get("kind", "practice"))
                    if kind not in ("practice", "video", "memorize", "mock", "review"):
                        raise ValueError("任务方式不正确")
                    con.execute("INSERT INTO tasks(subject_id,due_date,title,detail,minutes,kind,status,source,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                                (sid, data["due_date"], title, str(data.get("detail", ""))[:2000],
                                 max(5, min(600, int(data.get("minutes", 45)))), kind, "todo", "custom", now()))
                    self.send_json({"ok": True, "id": con.execute("SELECT last_insert_rowid()").fetchone()[0]})
                    return
                if path == "/api/task-status":
                    status = data.get("status")
                    if status not in ("todo", "doing", "done"):
                        raise ValueError("状态不正确")
                    con.execute("UPDATE tasks SET status=? WHERE id=?", (status, int(data["task_id"])))
                    self.send_json({"ok": True})
                    return
                if path == "/api/focus":
                    day = str(data.get("day", ""))
                    minutes = int(data.get("minutes", 0))
                    task_id = data.get("task_id") or None
                    if not valid_date(day) or not (1 <= minutes <= 240):
                        raise ValueError("专注日期或时长不正确")
                    if task_id is not None and not con.execute("SELECT 1 FROM tasks WHERE id=?", (int(task_id),)).fetchone():
                        raise ValueError("关联任务不存在")
                    con.execute("INSERT INTO focus_sessions(task_id,day,minutes,ended_at) VALUES(?,?,?,?)",
                                (int(task_id) if task_id is not None else None, day, minutes, now()))
                    self.send_json({"ok": True, "id": con.execute("SELECT last_insert_rowid()").fetchone()[0]})
                    return
                if path == "/api/journal":
                    day = str(data.get("day", ""))
                    mood = str(data.get("mood", ""))
                    note = str(data.get("note", "")).strip()[:1000]
                    if not valid_date(day) or mood not in ("顺利", "平常", "有点累"):
                        raise ValueError("日期或状态不正确")
                    con.execute("INSERT INTO journals(day,mood,note,updated_at) VALUES(?,?,?,?) "
                                "ON CONFLICT(day) DO UPDATE SET mood=excluded.mood,note=excluded.note,updated_at=excluded.updated_at",
                                (day, mood, note, now()))
                    self.send_json({"ok": True})
                    return
                if path == "/api/submissions":
                    task_id = int(data["task_id"])
                    content = str(data.get("content", ""))
                    if not content.strip() or len(content) > 40000:
                        raise ValueError("作业内容须为 1–40000 字")
                    tests = data.get("tests", [])
                    if not isinstance(tests, list) or len(tests) > 5:
                        raise ValueError("最多 5 组测试")
                    con.execute("INSERT INTO submissions(task_id,content,language,tests_json,created_at) VALUES(?,?,?,?,?)",
                                (task_id, content, str(data.get("language", "text"))[:20], json.dumps(tests, ensure_ascii=False), now()))
                    con.execute("UPDATE tasks SET status='doing' WHERE id=? AND status='todo'", (task_id,))
                    self.send_json({"ok": True, "id": con.execute("SELECT last_insert_rowid()").fetchone()[0]})
                    return
                if path in ("/api/review/offline", "/api/review/ai"):
                    sub = con.execute("SELECT u.*,t.title,s.name subject_name FROM submissions u JOIN tasks t ON t.id=u.task_id JOIN subjects s ON s.id=t.subject_id WHERE u.id=?", (int(data["submission_id"]),)).fetchone()
                    if not sub:
                        raise ValueError("作业不存在")
                    tests = json.loads(sub["tests_json"])
                    offline = offline_review(sub["content"], sub["language"], tests)
                    if path.endswith("offline"):
                        mode, verdict, feedback = "offline", offline["verdict"], offline["feedback"]
                    else:
                        mode = str(data.get("provider", "ollama"))
                        verdict = "AI 审阅完成"
                        feedback = ai_review(mode, str(data.get("model", "")), sub["subject_name"], sub["title"], sub["content"], tests, offline["feedback"])
                        if not feedback:
                            raise ValueError("AI 未返回文字反馈")
                    con.execute("INSERT INTO reviews(submission_id,mode,verdict,feedback,created_at) VALUES(?,?,?,?,?)",
                                (sub["id"], mode, verdict, feedback, now()))
                    self.send_json({"verdict": verdict, "feedback": feedback, "mode": mode})
                    return
                if path == "/api/import":
                    tables = ("subjects", "tasks", "submissions", "reviews", "focus_sessions", "journals") + tuple(EXTRA_COLUMNS) + tuple(ROUTE_COLUMNS) + tuple(WORKSPACE_COLUMNS)
                    columns = {
                        "subjects": ("id", "name", "icon", "color", "exam_date", "created_at"),
                        "tasks": ("id", "subject_id", "due_date", "title", "detail", "minutes", "kind", "status", "source", "created_at"),
                        "submissions": ("id", "task_id", "content", "language", "tests_json", "created_at"),
                        "reviews": ("id", "submission_id", "mode", "verdict", "feedback", "created_at"),
                        "focus_sessions": ("id", "task_id", "day", "minutes", "ended_at"),
                        "journals": ("day", "mood", "note", "updated_at"),
                    }
                    columns.update(EXTRA_COLUMNS)
                    columns.update(ROUTE_COLUMNS)
                    columns.update(WORKSPACE_COLUMNS)
                    if not isinstance(data, dict) or any(not isinstance(data.get(t), list) for t in tables[:4]):
                        raise ValueError("备份格式不正确")
                    for t in tables[4:]:
                        data.setdefault(t, [])
                        if not isinstance(data[t], list):
                            raise ValueError("备份格式不正确")
                    if any(len(data[t]) > 100000 for t in tables):
                        raise ValueError("备份记录过多")
                    for row in data['exam_profile']:
                        EXAMS.validate_profile(json.loads(row['payload']))
                    for row in data['student_route']:
                        validate_saved_route(json.loads(row['payload']))
                    for row in data['workspace_items']:
                        validate_item(row['key'],json.loads(row['payload']))
                        if not isinstance(row['revision'],int) or row['revision']<1:raise ValueError('工作区备份版本不正确')
                    if not data['student_route'] and data['exam_profile']:
                        # Legacy C/English backups belong to the original HBNU pack.
                        revision,catalog=PLATFORM.active()
                        target=next(x for x in catalog['offerings'] if x.get('learning_pack_id')=='hubei-hbnu-cs')
                        legacy=EXAMS.validate_profile(json.loads(data['exam_profile'][0]['payload']))
                        selection=validate_selection(PLATFORM,dict(province='hubei',source_code='510203',offering_id=target['id'],catalog_revision=revision,acknowledged=True,**{k:legacy[k] for k in ('target_year','start_date','deadline','intensity','daily_minutes')}))
                        data['student_route']=[{'id':1,'payload':json.dumps(selection,ensure_ascii=False),'updated_at':now()}]
                    snapshot_database(REQUEST_DB.get() or DB_PATH,'before-import')
                    for t in reversed(tables):
                        con.execute("DELETE FROM " + t)
                    for t in tables:
                        col = columns[t]
                        sql = "INSERT INTO %s(%s) VALUES(%s)" % (t, ",".join(col), ",".join("?" for _ in col))
                        for row in data[t]:
                            if not isinstance(row, dict):
                                raise ValueError("备份行格式不正确")
                            con.execute(sql, tuple(row[c] for c in col))
                    self.send_json({"ok": True, "counts": {t: len(data[t]) for t in tables}})
                    return
            if path == "/api/quit":
                self.send_json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self.send_json({"error": "未找到"}, 404)
        except (ValueError, KeyError, TypeError, OverflowError, sqlite3.Error, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, 400)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    # Existing personal installations retain their original route. A fresh
    # portable copy starts blank instead of assigning every customer HBNU/C.
    with PLATFORM.connection() as central:
        saved=central.execute("SELECT value FROM settings WHERE key='owner_bootstrap_mode'").fetchone()
        if saved:
            legacy=saved[0]=='legacy'
        else:
            legacy=False
            if DB_PATH.exists():
                existing=sqlite3.connect(str(DB_PATH))
                try:
                    if existing.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='subjects'").fetchone():legacy=bool(existing.execute('SELECT COUNT(*) FROM subjects').fetchone()[0])
                finally:existing.close()
            central.execute("INSERT INTO settings VALUES('owner_bootstrap_mode',?)",('legacy' if legacy else 'empty',))
    init_db(seed=legacy)
    if legacy:
        with connection() as con:owner_route(con)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = "http://127.0.0.1:%d/" % server.server_port
    info=DATA_DIR/"desktop-server.json"
    info.write_text(json.dumps({"url":url,"pid":os.getpid()}),encoding="utf8")
    print("StudyForge running at " + url, flush=True)
    if not args.no_browser:
        threading.Timer(0.5, lambda: open_window(url)).start()
    COMPANION.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        COMPANION.stop.set()
        server.server_close()
        try:
            if json.loads(info.read_text(encoding="utf8")).get("pid")==os.getpid():info.unlink()
        except (OSError,ValueError):pass


if __name__ == "__main__":
    main()
