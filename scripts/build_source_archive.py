"""Produce a source-only archive from the same reviewed Git candidate list."""
import argparse
import hashlib
from pathlib import Path
import sys
import zipfile

from release_check import ROOT, candidates, check


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-pending-license', action='store_true', help='explicitly build an unlicensed review preview')
    args = parser.parse_args()
    status = check(args.allow_pending_license)
    if status:
        return status
    version = (ROOT/'VERSION').read_text(encoding='utf-8').strip()
    preview = '-unlicensed-preview' if not (ROOT/'LICENSE').exists() else ''
    out = ROOT/'dist'
    out.mkdir(exist_ok=True)
    archive = out/('StudyForge-'+version+preview+'-source.zip')
    names = candidates()
    with zipfile.ZipFile(str(archive), 'w', compression=zipfile.ZIP_DEFLATED) as target:
        for name in names:
            entry = zipfile.ZipInfo('StudyForge/'+name, (2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            target.writestr(entry, (ROOT/name).read_bytes())
    with zipfile.ZipFile(str(archive)) as target:
        if target.testzip() is not None or len(target.infolist()) != len(names):
            raise RuntimeError('source archive CRC/count mismatch')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out/'SHA256SUMS.txt').write_text(digest+'  '+archive.name+'\n', encoding='ascii')
    print('SOURCE ARCHIVE PASS: %d files; CRC verified; SHA256 %s' % (len(names), digest))
    print(str(archive))
    return 0


if __name__ == '__main__':
    sys.exit(main())
