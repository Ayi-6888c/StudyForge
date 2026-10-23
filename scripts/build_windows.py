"""Manual portable build. Never copies local databases, model files or credentials."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if os.name != 'nt':
        print('Windows build requires a Windows host')
        return 1
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
               '--windowed', '--name', 'StudyForge', '--icon', str(ROOT/'app'/'studyforge.ico'),
               '--distpath', str(ROOT/'dist'),
               '--workpath', str(ROOT/'build'/'work'), '--specpath', str(ROOT/'build'),
               '--hidden-import', 'win32api', '--hidden-import', 'win32con',
               '--hidden-import', 'win32gui', '--hidden-import', 'win32com.client',
               '--hidden-import', 'win32com.shell.shell', '--hidden-import', 'win32com.propsys.propsys',
               '--hidden-import', 'win32timezone']
    for source in sorted((ROOT/'app').iterdir()):
        if source.suffix in ('.html', '.css', '.js', '.json', '.ico', '.png', '.ps1'):
            command.extend(['--add-data', str(source)+os.pathsep+'.'])
    command.append(str(ROOT/'app'/'app.py'))
    return subprocess.run(command, cwd=str(ROOT)).returncode


if __name__ == '__main__':
    sys.exit(main())
