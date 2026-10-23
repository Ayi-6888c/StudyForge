"""Dependency-free, isolated checks. No network, real model calls or notifications."""
import os
from pathlib import Path
import py_compile
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1',
               STUDYFORGE_ENABLE_CODE_EXECUTION='0')
    env.pop('OPENAI_API_KEY', None)
    with tempfile.TemporaryDirectory(prefix='studyforge-syntax-') as tmp:
        files = sorted(p for folder in ('app', 'tests', 'scripts') for p in (ROOT/folder).glob('*.py'))
        for index, path in enumerate(files):
            py_compile.compile(str(path), cfile=str(Path(tmp)/('%d.pyc' % index)), doraise=True)
    print('SYNTAX PASS: %d Python files' % len(files), flush=True)
    commands = [[sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py']]
    commands += [[sys.executable, 'tests/regression_%s.py' % name]
                 for name in ('exam', 'learning', 'companion', 'catalog')]
    for command in commands:
        print('RUN: ' + ' '.join(command[1:]), flush=True)
        result = subprocess.run(command, cwd=str(ROOT), env=env)
        if result.returncode:
            return result.returncode
    print('CHECKS PASS: syntax, isolated HTTP/accounts, code gate, exam, learning, companion, full catalog matrix', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
