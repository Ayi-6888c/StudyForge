# -*- coding: utf-8 -*-
"""Launch the local UI in a normal standalone application window, no browser chrome."""
from pathlib import Path
import os,subprocess,webbrowser

def browser_candidates():
 roots=[Path(os.environ.get(k,'')) for k in ('ProgramFiles(x86)','ProgramFiles','LOCALAPPDATA') if os.environ.get(k)]
 return [r/p for p in ('Microsoft/Edge/Application/msedge.exe','Google/Chrome/Application/chrome.exe') for r in roots]

def open_window(url,spawn=None,exists=None,fallback=None):
 spawn=spawn or subprocess.Popen;exists=exists or Path.is_file;fallback=fallback or webbrowser.open
 for exe in browser_candidates():
  if exists(exe):
   spawn([str(exe),'--app='+url,'--new-window','--no-first-run'],creationflags=0x08000000 if os.name=='nt' else 0)
   return {'mode':'standalone-window','browser':str(exe),'url':url}
 fallback(url);return {'mode':'browser-window','url':url}
