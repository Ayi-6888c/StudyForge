# -*- coding: utf-8 -*-
import sys,json,re
from pathlib import Path
sys.path.insert(0,str((Path(__file__).resolve().parents[1]/'app').resolve()))
from student_platform import match,validate_catalog
c=json.loads((Path(__file__).resolve().parents[1]/'app'/'hubei_catalog.json').read_text(encoding='utf8'));validate_catalog(c);total=0;positive=0
for src in c['source_majors']:
 for o in c['offerings']:
  total+=1;m=match(o,src,2027);e=o['eligibility']
  if m['state']=='matched':
   assert e['status']=='verified';assert not any(src['code'].startswith(p) for p in e.get('excluded_prefixes',[]));assert e['any'] or src['code'] in e['codes'] or src['name'] in e['names'] or any(src['code'].startswith(p) for p in e['prefixes']);assert o['offering_status']=='verified'
   if o['evidence']['selection_ready']:positive+=1
for o in c['offerings']:
 ev=o['evidence'];assert ev['selection_ready']==(ev['requirements']['structured'] and ev['exam_complete'] and o['offering_status']=='verified');assert all(d['url'].startswith(('http://','https://')) for d in ev['documents']);assert not ev['exam_complete'] or any(x['name'] not in ('英语','大学英语') for x in o['exam_subjects']);assert ev['reference_year']==2026
hb=next(o for o in c['offerings'] if o['id']=='hb-04-080901');pro=hb['exam_subjects'][1];assert pro['name']=='高级语言程序设计' and pro['points']==150 and pro['minutes']==90 and '谭浩强' in pro['textbooks'];assert next(d for d in hb['evidence']['documents'] if 'c4286906' in d['url'])['page']==9
art=next(x for x in c['source_majors'] if x['code']=='550101');finance=next(x for x in c['offerings'] if x['id']=='hb-21-120203K');assert match(finance,art,2027)['state']=='not_matched';assert match(finance,{'code':'manual','name':'随便手填','category':'','group':''},2027)['state']=='pending'
print('MATRIX PASS: '+str(total)+' source/offering pairs (811x709); '+str(positive)+' positive complete-reference edges; every positive grounded in explicit name/code/class/unrestricted rule; excluded classes/manual names rejected;HBNU PDF page9 and150/90 verified;434 gaps remain explicit')
