"""Check actual publish candidates, including already tracked ignored files."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APACHE_2_SHA256 = 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30'
ROOT_FILES = {'.editorconfig', '.env.example', '.gitattributes', '.gitignore', 'VERSION', 'LICENSE', 'NOTICE',
              'README.md', 'README.en.md', 'README.zh-CN.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'SECURITY.md',
              'THIRD_PARTY_NOTICES.md', 'requirements.txt', 'requirements-build.txt',
              'requirements-ui.txt', 'requirements-windows.txt'}
BANNED_PARTS = {'data', 'backups', 'work', 'outputs', 'build', 'dist', 'artifacts', '.release',
                'release-evidence', '.venv', 'venv', '__pycache__', 'node_modules', '.git'}
BANNED_SUFFIXES = {'.sqlite', '.sqlite3', '.db', '.exe', '.dll', '.pyd', '.pyc', '.pyo', '.zip',
                   '.log', '.tmp', '.pem', '.key', '.p12', '.pfx', '.spec'}
SECRET_PATTERNS = [
    re.compile(r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}'),
    re.compile(r'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'(?i)[A-Z]:[\\/]Users[\\/][^\\/\s"\x27]+'),
    re.compile(r'(?<![A-Za-z0-9.])/(?:Users|home)/[A-Za-z0-9_.-]+/'),
]


def license_status(root=ROOT):
    path = root/'LICENSE'
    if not path.is_file():
        return 'pending'
    digest = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    return 'Apache-2.0' if digest == APACHE_2_SHA256 else 'invalid'


def candidates(root=ROOT):
    if (root/'.git').exists():
        result = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                                cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return sorted(set(x.decode('utf-8') for x in result.stdout.split(b'\0') if x))
    # Before git init, never enumerate data, build products or arbitrary root files.
    files = [p.name for p in root.iterdir() if p.is_file() and p.name in ROOT_FILES]
    for directory in ('app', 'docs', 'scripts', 'tests', '.github'):
        if (root/directory).exists():
            files += [p.relative_to(root).as_posix() for p in (root/directory).rglob('*')
                      if p.is_file() and not any(x.lower() in BANNED_PARTS for x in p.relative_to(root).parts)]
    return sorted(set(files))


def issues(root, names):
    errors = []
    for name in names:
        path = root/name
        parts = Path(name).parts
        if (path.is_symlink() or not path.is_file() or '..' in parts or Path(name).is_absolute()
                or '\n' in name or '\r' in name):
            errors.append('%s: missing, unsafe path or symlink' % name)
            continue
        if (any(x.lower() in BANNED_PARTS or x.lower().startswith('backup-') for x in parts)
                or path.suffix.lower() in BANNED_SUFFIXES or '.sqlite3-' in name or '.db-' in name
                or (path.name.startswith('.env') and path.name != '.env.example')
                or path.name.lower() in ('auth.json', 'credentials.json')):
            errors.append('%s: private/generated file in publish candidates' % name)
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            if path.suffix.lower() not in ('.png', '.ico'):
                errors.append('%s: unexpected binary asset' % name)
            continue
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            errors.append('%s: credential/private-path pattern; inspect locally' % name)
        if path.suffix == '.md':
            for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', content):
                if target.startswith(('https://', 'http://', '#', 'mailto:')):
                    continue
                link = target.split('#')[0]
                resolved = (path.parent/link).resolve()
                try:
                    resolved.relative_to(root.resolve())
                    inside = True
                except ValueError:
                    inside = False
                if not inside or not resolved.exists():
                    errors.append('%s: broken/escaping documentation link %s' % (name, target))
        if name.startswith('.github/workflows/'):
            if 'pull_request_target' in content or 'contents: read' not in content:
                errors.append('%s: workflow permission/event mismatch' % name)
            for action in re.findall(r'uses:\s*([^\s#]+)', content):
                if not re.fullmatch(r'[^@]+@[a-f0-9]{40}', action):
                    errors.append('%s: action not pinned to a full commit' % name)
    return errors


def index_issues(root=ROOT):
    """A scrubbed working tree must not hide a credential still staged in Git."""
    if not (root/'.git').exists():
        return []
    names = subprocess.run(['git', 'ls-files', '-z'], cwd=str(root), check=True,
                           stdout=subprocess.PIPE).stdout.split(b'\0')
    names = [name for name in names if name and b'\n' not in name and b'\r' not in name]
    batch = subprocess.run(['git', 'cat-file', '--batch'], cwd=str(root), check=True,
                           input=b''.join(b':'+name+b'\n' for name in names), stdout=subprocess.PIPE).stdout
    cursor, errors = 0, []
    for name in names:
        end = batch.index(b'\n', cursor)
        header = batch[cursor:end].split()
        if len(header) != 3 or header[1] != b'blob':
            errors.append('Git index: unreadable staged entry')
            break
        size = int(header[2])
        content = batch[end+1:end+1+size]
        cursor = end+size+2
        if name == b'LICENSE' and hashlib.sha256(content.replace(b'\r\n', b'\n')).hexdigest() != APACHE_2_SHA256:
            errors.append('LICENSE: staged text does not match canonical Apache-2.0')
        try:
            content = content.decode('utf-8')
        except UnicodeDecodeError:
            continue
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            errors.append(name.decode('utf-8')+': staged credential/private-path pattern; inspect locally')
    return errors


def check(allow_pending=False, quiet=False):
    names = candidates()
    errors = issues(ROOT, names) + index_issues()
    license_state = license_status()
    if license_state == 'invalid':
        errors.append('LICENSE: expected complete canonical Apache-2.0 text')
    if license_state == 'Apache-2.0':
        for name in ('LICENSE', 'NOTICE'):
            if name not in names:
                errors.append(name+': required in actual publish candidates')
        if not (ROOT/'NOTICE').is_file() or not (ROOT/'NOTICE').read_text(encoding='utf-8').strip():
            errors.append('NOTICE: project attribution missing or empty')
    for name in ('README.md', 'README.en.md', 'CONTRIBUTING.md', 'SECURITY.md',
                 'docs/CONTENT_SOURCES.md', 'app/app.py', '.github/workflows/ci.yml'):
        if name not in names:
            errors.append('required file missing from candidates: '+name)
    for name in names:
        if name.endswith('.json'):
            try:
                json.loads((ROOT/name).read_text(encoding='utf-8'))
            except (ValueError, OSError):
                errors.append(name+': invalid JSON')
    if errors:
        print('RELEASE CHECK FAILED:\n'+'\n'.join(errors))
        return 1
    if license_state == 'pending':
        print('LICENSE PENDING: maintainer choice required; no open-source grant implied')
        if not allow_pending:
            return 2
    if not quiet:
        if license_state == 'Apache-2.0':
            print('LICENSE PASS: Apache-2.0 canonical text and NOTICE included')
        print('RELEASE TECHNICAL PASS: %d candidate files; no banned files, detected credential/private-path patterns or broken links' % len(names))
        print('NOTE: pattern scanning supplements, not replaces, review of the actual publish file list')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-pending-license', action='store_true', help='technical preview only, not licensed release approval')
    sys.exit(check(parser.parse_args().allow_pending_license))
