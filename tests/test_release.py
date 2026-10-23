from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from release_check import candidates, issues, index_issues, license_status


class ReleaseBoundary(unittest.TestCase):
    def test_license_requires_complete_official_text(self):
        with tempfile.TemporaryDirectory(prefix='studyforge-license-') as temp:
            root = Path(temp)
            self.assertEqual(license_status(root), 'pending')
            (root/'LICENSE').write_text('', encoding='utf-8')
            self.assertEqual(license_status(root), 'invalid')
            canonical = (Path(__file__).resolve().parents[1]/'LICENSE').read_bytes()
            (root/'LICENSE').write_bytes(canonical)
            self.assertEqual(license_status(root), 'Apache-2.0')
            (root/'LICENSE').write_bytes(canonical.replace(b'\n', b'\r\n'))
            self.assertEqual(license_status(root), 'Apache-2.0')
            (root/'LICENSE').write_bytes(canonical[:200])
            self.assertEqual(license_status(root), 'invalid')

    def test_secrets_and_paths_without_leaking_values(self):
        with tempfile.TemporaryDirectory(prefix='studyforge-scan-') as temp:
            root = Path(temp)
            path = root/'example.txt'
            for content in ('sk-'+'a'*30, 'ghp_'+'b'*30,
                            'C:'+chr(92)+'Users'+chr(92)+'synthetic'+chr(92)+'data',
                            '/home/'+'synthetic'+'/data'):
                path.write_text(content, encoding='utf-8')
                self.assertTrue(issues(root, ['example.txt']))
            path.write_text('https://zsb.jhun.edu.cn/home/new/detail/id/253.html', encoding='utf-8')
            self.assertEqual(issues(root, ['example.txt']), [])

    @unittest.skipUnless(shutil.which('git'), 'git needed for tracked-file boundary test')
    def test_ignored_file_already_tracked_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='studyforge-git-') as temp:
            root = Path(temp)
            subprocess.run(['git', 'init', '-q'], cwd=temp, check=True)
            (root/'.gitignore').write_text('*.sqlite3\n', encoding='utf-8')
            (root/'private.sqlite3').write_bytes(b'synthetic fixture, not a real database')
            subprocess.run(['git', 'add', '-f', 'private.sqlite3'], cwd=temp, check=True)
            names = candidates(root)
            self.assertIn('private.sqlite3', names)
            self.assertTrue(any('private/generated file' in x for x in issues(root, names)))
            (root/'stage.txt').write_text('sk-'+'z'*30, encoding='utf-8')
            subprocess.run(['git', 'add', 'stage.txt'], cwd=temp, check=True)
            (root/'stage.txt').write_text('clean working tree', encoding='utf-8')
            self.assertTrue(any('staged credential' in x for x in index_issues(root)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
