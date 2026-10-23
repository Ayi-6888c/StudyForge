"""Start only isolated, disposable servers; never reuse a personal installation."""
import http.cookiejar
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class Server:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='studyforge-test-')
        self.log = tempfile.TemporaryFile()
        env = dict(os.environ, STUDYFORGE_DATA_DIR=self.tmp.name,
                   STUDYFORGE_ENABLE_CODE_EXECUTION='0', PYTHONDONTWRITEBYTECODE='1',
                   PYTHONIOENCODING='utf-8')
        env.pop('OPENAI_API_KEY', None)
        self.proc = subprocess.Popen([sys.executable, str(ROOT/'app'/'app.py'),
                                      '--no-browser', '--port', '0'], env=env,
                                     stdout=self.log, stderr=self.log)
        try:
            for _ in range(300):
                info = Path(self.tmp.name)/'desktop-server.json'
                if info.exists():
                    try:
                        self.url = json.loads(info.read_text(encoding='utf-8'))['url']
                        return self
                    except (ValueError, KeyError):
                        pass
                if self.proc.poll() is not None:
                    self.log.seek(0)
                    raise RuntimeError(self.log.read().decode('utf-8', errors='replace'))
                time.sleep(.1)
            raise RuntimeError('isolated server startup timeout')
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *unused):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.log.close()
        self.tmp.cleanup()


class Client:
    def __init__(self, url):
        self.url = url
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(self.cookies))

    def call(self, path, data=None, headers=None):
        hdr = {'Content-Type': 'application/json'}
        hdr.update(headers or {})
        req = urllib.request.Request(self.url+path.lstrip('/'),
                                     None if data is None else json.dumps(data).encode('utf-8'), hdr)
        try:
            res = self.opener.open(req, timeout=60)
        except urllib.error.HTTPError as exc:
            res = exc
        with res:
            raw = res.read()
            return res.status, json.loads(raw) if 'application/json' in res.headers.get('Content-Type', '') else raw

    def ok(self, path, data=None):
        status, result = self.call(path, data)
        assert status == 200, (path, status, result)
        return result
