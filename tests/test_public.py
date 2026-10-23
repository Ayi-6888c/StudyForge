import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from support import Client, Server, ROOT


class CodeExecutionGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='studyforge-gate-')
        cls.env = patch.dict(os.environ, {'STUDYFORGE_DATA_DIR': cls.temp.name})
        cls.env.start()
        sys.path.insert(0, str(ROOT/'app'))
        cls.app = importlib.import_module('app')

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.temp.cleanup()

    def test_default_never_invokes_compiler(self):
        for value in ('', '0', 'true', 'yes'):
            with patch.dict(os.environ, {'STUDYFORGE_ENABLE_CODE_EXECUTION': value}), \
                 patch.object(self.app, 'get_compiler') as compiler, \
                 patch.object(self.app.subprocess, 'run') as run:
                result = self.app.offline_review('int main(void){return 0;}', 'c', [])
                self.assertEqual(result['verdict'], '静态检查完成')
                self.assertIn('未编译或执行样例', result['feedback'])
                compiler.assert_not_called()
                run.assert_not_called()

    def test_opt_in_and_static_diagnostics(self):
        with patch.dict(os.environ, {'STUDYFORGE_ENABLE_CODE_EXECUTION': '1'}), \
             patch.object(self.app, 'get_compiler', return_value=None) as compiler:
            result = self.app.offline_review('gets(x);{', 'c', [])
            compiler.assert_called_once()
            self.assertIn('花括号', result['feedback'])
            self.assertIn('gets', result['feedback'])
            self.assertNotIn('默认不运行', result['feedback'])


class PublicHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = Server().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.server.__exit__(None, None, None)

    def test_accounts_routes_and_empty_start(self):
        anon = Client(self.server.url)
        self.assertEqual(anon.call('/api/bootstrap')[0], 401)
        self.assertEqual(anon.call('/api/bootstrap', headers={'Host':'outside.invalid'})[0], 403)
        owner = Client(self.server.url)
        owner.ok('/api/auth/state')
        claimed = owner.ok('/api/auth/claim', {'username':'demo_owner','password':'Test-only-2026','display_name':'演示维护者'})
        self.assertEqual(claimed['user']['role'], 'owner')
        boot = owner.ok('/api/bootstrap')
        self.assertEqual(boot['tasks'], [])
        self.assertEqual(boot['subjects'], [])
        self.assertFalse(boot['compiler'])
        self.assertFalse(boot['code_execution_enabled'])
        self.assertIsNone(owner.ok('/api/student')['route'])
        student = Client(self.server.url)
        registered = student.ok('/api/auth/register', {'username':'demo_student','password':'Test-only-2026','display_name':'演示学生'})
        self.assertEqual(registered['user']['role'], 'student')
        self.assertEqual(student.call('/api/admin/catalog')[0], 403)
        self.assertEqual(student.call('/api/data/full-backup')[0], 403)
        self.assertEqual(student.call('/api/bootstrap', headers={'X-StudyForge-User':'99999'})[0], 409)
        self.assertEqual(student.call('/api/auth/profile', {}, {'Origin':'https://outside.invalid'})[0], 403)
        cat = student.ok('/api/catalog?source=510203&year=2027')
        selection = dict(province='hubei', source_code='510203', offering_id='hb-04-040106',
                         catalog_revision=cat['revision'], target_year=2027, start_date='2026-10-25',
                         deadline='2026-11-22', intensity='standard', daily_minutes=270,
                         acknowledged=True, generate_plan=True)
        self.assertEqual(student.call('/api/student/route', selection)[0], 400)
        selection['offering_id'] = 'hb-04-080901'
        student.ok('/api/student/route', selection)
        self.assertEqual(student.ok('/api/student')['route']['offering']['id'], 'hb-04-080901')
        self.assertGreater(len(student.ok('/api/bootstrap')['tasks']), 0)
        self.assertEqual(owner.ok('/api/bootstrap')['tasks'], [])
        self.assertIsNone(owner.ok('/api/student')['route'])
        self.assertEqual(len(student.ok('/api/companion/news')['items']), 5)
        student.ok('/api/auth/logout', {})
        self.assertEqual(student.call('/api/bootstrap')[0], 401)


if __name__ == '__main__':
    unittest.main(verbosity=2)
