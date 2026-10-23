/* Admissions catalog and local student identities. APIs keep public facts separate from private study data. */
window.platformState={user:null,student:null,catalog:null,page:1,mode:'programs',authMode:'login',draft:null};
window.sfStorage={key:k=>'sf-user-'+(platformState.user?.id||'anonymous')+':'+k,getItem:k=>localStorage.getItem(sfStorage.key(k)),setItem:(k,v)=>localStorage.setItem(sfStorage.key(k),v),removeItem:k=>localStorage.removeItem(sfStorage.key(k))};
const catEsc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// Small, keyboard-accessible search pickers. The directory is data, not the student's homepage.
const routePickers={};
function compactKey(s){return String(s||'').toLowerCase().replace(/[\s·（）()]/g,'')}
function searchAliases(s){return s+(s.includes('湖北师范大学')&&!s.includes('文理')?' 湖师大 湖北师大':'')+(s.includes('计算机科学与技术')?' 计科 计算机':'')}
function installRoutePicker(id,placeholder,options){
 const field=document.getElementById(id),direct=field.tagName==='INPUT';field.removeAttribute('list');
 const label=field.closest('label'),labelText=label.firstChild.textContent.trim();
 const wrap=document.createElement('div');wrap.className='route-picker'+(direct?'':' route-select');field.parentNode.insertBefore(wrap,field);wrap.appendChild(field);
 const input=direct?field:document.createElement('input');if(!direct){field.hidden=true;input.id=id+'Search';wrap.appendChild(input)}
 input.type='text';input.placeholder=placeholder;input.autocomplete='off';input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-expanded','false');input.setAttribute('aria-label',labelText);
 const list=document.createElement('div');list.className='route-suggestions';list.id=id+'Suggestions';list.setAttribute('role','listbox');list.setAttribute('aria-label',labelText+'选项');list.hidden=true;input.setAttribute('aria-controls',list.id);wrap.appendChild(list);
 const help=label.querySelector('small');if(help){if(!help.id)help.id=id+'Help';input.setAttribute('aria-describedby',help.id)}
 let found=[],active=-1,toggle=null;
 const close=()=>{list.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');if(toggle)toggle.setAttribute('aria-expanded','false');active=-1};
 function note(text,cls=''){const p=document.createElement('p');p.className=cls;p.textContent=text;list.appendChild(p)}
 function draw(){
  if(field.disabled){close();return}Object.values(routePickers).forEach(p=>{if(p.input!==input)p.close()});
  // A committed label is a selection, not a new search. Reopening shows the entire relevant list.
  const query=compactKey(!direct&&input.value===input.dataset.committed?'':input.value),all=options();
  list.replaceChildren();active=-1;found=query?all.filter(x=>compactKey(x.search||x.label).includes(query)):direct?[]:all;
  const total=found.length;if(direct)found=found.slice(0,40);
  if(id==='routeSchool'){
   const target=document.getElementById('routeTarget').value,source=catalogSource();
   if(!target)note('先选择目标本科专业，这里就会列出对应学校。');
   else{note(target+' · '+new Set(found.map(o=>o.label)).size+' 所已核实参考学校','picker-context');if(!source)note('尚未选择词典内的专科专业；以下对应范围仍待核对。');else note('仅列出专业范围明确允许、专业课已整理的2026项目。')}
  }else if(!direct)note(query?'找到 '+total+' 个选项':'直接点选，也可以输入关键词筛选','picker-context');
  if(direct&&!query)note(placeholder+'；输入名称或专业代码即可。');
  else if(!found.length&&!(id==='routeSchool'&&!document.getElementById('routeTarget').value))note(id==='routeTarget'&&!catalogSource()?'先选择你当前的专科专业，再列出已核实的本科方向。':!query?'暂无资料齐备的明确候选；这不等于没有学校可报。可浏览学校原文与资料缺口。':'没有找到对应选项，试试更短的名称或清空关键词。');
  let previousGroup=null;
  for(const [i,o]of found.entries()){
   if(o.group&&o.group!==previousGroup){const heading=document.createElement('div');heading.className='picker-group';heading.setAttribute('role','presentation');heading.textContent=o.group+' · '+found.filter(x=>x.group===o.group).length;list.appendChild(heading);previousGroup=o.group}
   const selected=field.value===o.value,button=document.createElement('button');button.type='button';button.tabIndex=-1;button.id=id+'Option'+i;button.dataset.value=o.value;button.setAttribute('role','option');button.setAttribute('aria-disabled',String(!!o.disabled));button.setAttribute('aria-selected',String(selected));button.className='route-suggestion'+(o.disabled?' unavailable':'')+(selected?' committed':'');button.innerHTML=`<b>${catEsc(o.label)}${selected?'<span class="picker-check" aria-hidden="true">✓</span>':''}</b>${o.detail?`<small>${catEsc(o.detail)}</small>`:''}`;button.onmousedown=e=>e.preventDefault();button.onclick=()=>choose(i);button.onpointermove=()=>{if(!o.disabled)highlight(i)};list.appendChild(button)
  }
  if(direct&&total>found.length)note('共 '+total+' 个结果，显示前 '+found.length+' 个；继续输入可缩小范围。');
  if(id==='routeSchool'&&found.length)note('2026资料仅供参考；2027要求公布后需重新核对。','picker-reference');
  list.hidden=false;input.setAttribute('aria-expanded','true');if(toggle)toggle.setAttribute('aria-expanded','true');
 }
 function highlight(i,scroll=false){active=i;list.querySelectorAll('[role=option]').forEach((b,j)=>b.classList.toggle('selected',i===j));input.setAttribute('aria-activedescendant',id+'Option'+i);if(scroll){const option=document.getElementById(id+'Option'+i);if(option.offsetTop<list.scrollTop)list.scrollTop=option.offsetTop;else if(option.offsetTop+option.offsetHeight>list.scrollTop+list.clientHeight)list.scrollTop=option.offsetTop+option.offsetHeight-list.clientHeight}}
 function choose(i){const o=found[i];if(!o||o.disabled)return;field.value=o.value;input.value=o.label;input.dataset.committed=o.label;close();field.dispatchEvent(new Event('change',{bubbles:true}));input.focus()}
 if(!direct){toggle=document.createElement('button');toggle.type='button';toggle.className='picker-toggle';toggle.tabIndex=-1;toggle.setAttribute('aria-label','展开'+labelText);toggle.setAttribute('aria-controls',list.id);toggle.setAttribute('aria-expanded','false');toggle.innerHTML='<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg>';toggle.onmousedown=e=>e.preventDefault();toggle.onclick=()=>{if(!list.hidden)close();else{input.focus();draw()}};wrap.appendChild(toggle)}
 input.addEventListener('input',()=>{if(!direct){field.value='';if(id==='routeProvince'){document.getElementById('routeTarget').value='';routePickers.routeTarget?.sync()}if(id==='routeProvince'||id==='routeTarget'){document.getElementById('routeSchool').value='';fillSchools()}document.getElementById('routeAcknowledge').checked=false;renderRouteSummary()}draw()});
 input.addEventListener('focus',draw);input.addEventListener('click',()=>{if(list.hidden)draw()});input.addEventListener('keydown',e=>{if(e.key==='Escape'){close();return}if(e.key==='ArrowDown'||e.key==='ArrowUp'||e.key==='Home'||e.key==='End'){
  if((e.key==='Home'||e.key==='End')&&list.hidden)return;e.preventDefault();if(list.hidden)draw();const available=found.map((o,i)=>o.disabled?-1:i).filter(i=>i>=0);if(!available.length)return;const step=e.key==='ArrowDown'?1:-1,pos=available.indexOf(active);highlight(e.key==='Home'?available[0]:e.key==='End'?available[available.length-1]:available[pos<0?(step>0?0:available.length-1):(pos+step+available.length)%available.length],true);
 }else if(e.key==='Enter'&&!list.hidden){e.preventDefault();if(active>=0)choose(active);else{const available=found.map((o,i)=>o.disabled?-1:i).filter(i=>i>=0);if(available.length===1)choose(available[0])}}});
 input.addEventListener('blur',()=>setTimeout(()=>{if(document.activeElement!==input)close()},120));document.addEventListener('pointerdown',e=>{if(!wrap.contains(e.target))close()});
 routePickers[id]={sync(){if(!direct){const o=options().find(x=>x.value===field.value);input.value=o?.label||'';input.dataset.committed=input.value}input.disabled=field.disabled;if(toggle)toggle.disabled=field.disabled;close()},input,close,open:draw};
 return routePickers[id];
}
function syncRoutePickers(){Object.values(routePickers).forEach(p=>p.sync())}
function installRoutePickers(){
 installRoutePicker('routeProvince','点击选择省份',()=>[...document.getElementById('routeProvince').options].filter(o=>o.value).map(o=>({value:o.value,label:o.textContent,disabled:o.disabled,detail:o.disabled?'资料后续接入':'按省份匹配招生资料'})));
 installRoutePicker('routeCandidate','点击选择考生身份',()=>[...document.getElementById('routeCandidate').options].map(o=>({value:o.value,label:o.textContent,disabled:o.disabled,detail:o.disabled?'对应资格规则与学习路线待单独接入':'按普通考生项目核对，资格以当年学校审核为准'})));
 installRoutePicker('routeSource','输入你现在就读的专科专业',()=>platformState.catalog.source_majors.map(o=>({value:o.code+' · '+o.name,label:o.code+' · '+o.name,search:o.code+' '+o.name,detail:o.group+' / '+o.category})));
 installRoutePicker('routeTarget','点击选择本科专业，也可输入筛选',()=>[...document.getElementById('routeTarget').options].filter(o=>o.value).map(o=>({value:o.value,label:o.value,search:searchAliases(o.textContent),group:o.dataset.group,detail:o.textContent.split(' · ').slice(1).join(' · ')})));
 installRoutePicker('routeSchool','点击查看对应学校，也可输入筛选',()=>[...document.getElementById('routeSchool').options].filter(o=>o.value).map(o=>{const x=platformState.catalog.offerings.find(x=>x.id===o.value);return {value:o.value,label:x.school_name,search:searchAliases(o.textContent),disabled:o.disabled,group:x.eligibility.any?'学校明确不限专业':'学校明确专业对应',detail:x.exam_subjects.map(s=>s.name).join(' + ')}}));
 syncRoutePickers();
}
async function platformApi(path,body){const opts={headers:{'X-StudyForge-User':String(platformState.user?.id||'')}};if(body!==undefined){opts.method='POST';opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body)}const r=await fetch(path,opts),x=await r.json();if(!r.ok||x.error)throw Error(x.error||'本次操作未完成');return x}
window.platformBootstrap=async()=>{
 const x=await platformApi('/api/auth/state');platformState.user=x.user;
 document.getElementById('accountButton').onclick=()=>showAccount();
 if(!x.user||!x.user.claimed||new URLSearchParams(location.search).has('login')){showAccount(x.user&&!x.user.claimed?'claim':'login');return false}
 if(x.user.id===1&&!localStorage.getItem('sf-v4-owner-storage-migrated')){for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);if(k&&(k.startsWith('exam-draft-')||['sf-provider','sf-model','sg-focus-timer'].includes(k))&&sfStorage.getItem(k)===null)sfStorage.setItem(k,localStorage.getItem(k))}localStorage.setItem('sf-v4-owner-storage-migrated','yes')}
 document.getElementById('accountButton').textContent='◌ '+x.user.display_name;
 document.querySelector('[data-view="content-admin"]').hidden=x.user.role!=='owner';
 await loadStudent();const initialRoute=platformState.student.route;await loadCatalog(initialRoute?.source_major.code==='manual'?'':initialRoute?.source_major.code||'',initialRoute?.target_year||2027);bindCatalog();
 if(!platformState.student.route)setTimeout(()=>navigate('catalog'),50);
 return true;
};
async function loadStudent(){platformState.student=await platformApi('/api/student')}
let catalogRequest=0;
async function loadCatalog(source='',year=2027){const request=++catalogRequest,c=await platformApi('/api/catalog?'+new URLSearchParams({source,year}));if(request===catalogRequest)platformState.catalog=c;return platformState.catalog}
function catalogSource(){const val=document.getElementById('routeSource').value.trim();return platformState.catalog.source_majors.find(x=>val===x.code+' · '+x.name||val===x.name||val===x.code)||null}
function catalogRun(fn){return async()=>{try{await fn()}catch(e){document.getElementById('routeResult').className='route-result error';document.getElementById('routeResult').textContent=e.message;toast(e.message)}}}
function routeOptions(){
 const c=platformState.catalog,p=platformState.student.route;
 document.getElementById('routeProvince').innerHTML=c.provinces.map(x=>`<option value="${catEsc(x.id)}">${catEsc(x.name)}</option>`).join('')+'<option disabled>其他省份 · 后续接入</option>';
 document.getElementById('sourceMajors').innerHTML=c.source_majors.map(x=>`<option value="${catEsc(x.code+' · '+x.name)}">${catEsc(x.group+' / '+x.category)}</option>`).join('');
 document.getElementById('routeProvince').value=p?.province||'hubei';document.getElementById('routeSource').value=p?(p.source_major.code==='manual'?p.source_major.name:p.source_major.code+' · '+p.source_major.name):'';
 document.getElementById('routeCandidate').value=p?.candidate_type||'ordinary';
 document.getElementById('routeYear').value=p?.target_year||2027;
 document.getElementById('routeStart').value=p?.start_date||'2026-10-25';document.getElementById('routeDeadline').value=p?.deadline||'2027-04-16';
 document.getElementById('routeIntensity').value=p?.intensity||'standard';document.getElementById('routeMinutes').value=p?.daily_minutes||270;updateRouteMinutes();
 document.getElementById('routeGenerate').checked=!p;document.getElementById('routeAcknowledge').checked=false;
 document.getElementById('routeAlternatives').checked=!!p&&routePriorityInfo(platformState.catalog.offerings.find(o=>o.id===p.offering_id)||p.offering).rank>0;fillTargets(p?.offering.major_name);fillSchools(p?.offering_id);renderRouteSummary();
 syncRoutePickers();document.getElementById('routeForm').hidden=!!p;
}
function routeSelectable(o){return !!o&&o.match.state==='matched'&&(platformState.catalog.selection_policy!=='positive_evidence_only'||o.evidence?.selection_ready===true)}
function routePriorityInfo(o){
 const source=catalogSource(),profile=platformState.catalog?.study_direction_guidance?.[source?.code],any=!!o?.eligibility?.any;
 if(profile){const index=profile.preferred_majors.indexOf(o.major_name);if(index>=0)return {rank:0,order:index,group:'本专业衔接方向 · 优先',detail:'教学衔接方向优先；可选资格仍以学校对应表为准',profile};return {rank:any?2:1,order:999,group:any?'不限专业 · 跨专业备选':'学校明确接收的其他方向',detail:any?'学校明确不限专业；不作为本专业优先推荐':'学校对应表明确接收当前专科，但不在已整理的本专业衔接举例中',profile}}
 return {rank:any?2:0,order:999,group:any?'不限专业 · 跨专业备选':'学校明确专业对应 · 优先',detail:any?'学校明确不限专业；其他条件仍看学校原文':'按学校对当前专科的明确对应条件优先；教学衔接资料尚未单独接入',profile:null};
}
function fillTargets(value=''){
 const c=platformState.catalog,province=document.getElementById('routeProvince').value,include=document.getElementById('routeAlternatives').checked;
 const items=c.offerings.filter(o=>o.province===province&&routeSelectable(o)),groups=new Map();
 for(const o of items){const info=routePriorityInfo(o),old=groups.get(o.major_name);if(!old)groups.set(o.major_name,{name:o.major_name,count:1,info});else{old.count++;if(info.rank<old.info.rank)old.info=info}}
 const majors=[...groups.values()].sort((a,b)=>a.info.rank-b.info.rank||a.info.order-b.info.order||a.name.localeCompare(b.name,'zh-CN')),primary=majors.filter(x=>x.info.rank===0),others=majors.length-primary.length;
 const visible=majors.filter(x=>include||x.info.rank===0||x.name===value);
 document.getElementById('routeTarget').innerHTML='<option value="">先选本专业相关本科方向</option>'+visible.map(x=>`<option value="${catEsc(x.name)}" data-group="${catEsc(x.info.group)}">${catEsc(x.name)} · ${x.count}个院校项目 · ${catEsc(x.info.group)}</option>`).join('');
 document.getElementById('routeTarget').value=groups.has(value)?value:'';routePickers.routeTarget?.sync();
 document.getElementById('routeDirectionStatus').textContent=catalogSource()?`优先方向 ${primary.length} 个${others?' · 另有 '+others+' 个其他允许方向，按需展开':''}`:'选择专科后，先显示本专业相关方向';
}
function fillSchools(id=''){
 const major=document.getElementById('routeTarget').value,province=document.getElementById('routeProvince').value,items=platformState.catalog.offerings.filter(o=>o.major_name===major&&o.province===province&&routeSelectable(o));
 const rank={matched:0,pending:1,not_matched:2,withdrawn:3};items.sort((a,b)=>Number(a.eligibility.any)-Number(b.eligibility.any)||rank[a.match.state]-rank[b.match.state]||a.school_name.localeCompare(b.school_name,'zh-CN'));
 document.getElementById('routeSchool').innerHTML='<option value="">再选择学校</option>'+items.map(o=>`<option value="${catEsc(o.id)}" >${catEsc(o.school_name)}${o.id.endsWith('-2')?' · 方向项目':''} · ${catEsc(o.match.label)}</option>`).join('');
 document.getElementById('routeSchool').value=items.some(x=>x.id===id)?id:'';
 routePickers.routeSchool?.sync();
 document.getElementById('routeSchoolCount').textContent=major?`${new Set(items.map(o=>o.school_id)).size}所已核实参考学校；仅列专业范围明确允许且考试科目齐备的2026项目。`:'先选专科和本科专业，再点选学校；对应依据未核实的项目不混入候选。';
}
let sourceChangeSequence=0,lastSourceSelectionKey='';
async function sourceChanged(){
 const key=[document.getElementById('routeProvince').value,document.getElementById('routeSource').value.trim(),document.getElementById('routeYear').value].join('|');if(key===lastSourceSelectionKey)return;lastSourceSelectionKey=key;
 const sequence=++sourceChangeSequence,controls=['routeTarget','routeSchool','previewStudentRoute','saveStudentRoute'];controls.forEach(id=>document.getElementById(id).disabled=true);
 syncRoutePickers();renderRouteProgress();
 const source=catalogSource(),custom=document.getElementById('routeSource').value.trim();
 document.getElementById('sourceDescription').textContent=source?`${source.group} / ${source.category} · ${source.code}`:custom?'手填/旧名称：仅作档案记录，对应范围需人工核验。':'选你现在就读的专科专业，不是目标本科专业。';
 try{await loadCatalog(source?.code||'',Number(document.getElementById('routeYear').value)||2027)}catch(e){if(sequence===sourceChangeSequence){lastSourceSelectionKey='';controls.forEach(id=>document.getElementById(id).disabled=false);syncRoutePickers();toast(e.message)}return}
 if(sequence!==sourceChangeSequence)return;controls.forEach(id=>document.getElementById(id).disabled=false);
 document.getElementById('routeAlternatives').checked=false;fillTargets();fillSchools();syncRoutePickers();document.getElementById('routeAcknowledge').checked=false;document.getElementById('routeResult').textContent='';renderRouteSummary();if(window.quietCatalogChanged)quietCatalogChanged();
}
function selectedOffering(){return platformState.catalog.offerings.find(o=>o.id===document.getElementById('routeSchool').value)}
function renderRouteProgress(){
 const source=catalogSource(),target=document.getElementById('routeTarget').value,school=selectedOffering();
 const steps=[...document.querySelectorAll('#routeForm .route-steps span')],done=[!!source,!!target,!!school];
 steps.forEach((step,i)=>{step.classList.toggle('done',done[i]);step.classList.toggle('current',!done[i]&&(i===0||done[i-1]));if(!done[i]&&(i===0||done[i-1]))step.setAttribute('aria-current','step');else step.removeAttribute('aria-current')});
 const text=document.getElementById('routeNextStep');if(text)text.textContent=document.getElementById('routeTarget').disabled?'正在按专科专业更新对应范围…':!source?'先选择你现在就读的专科专业。':!target?'接下来，选择你想升入的本科专业。':!school?'本科专业已选好，点击目标学校即可查看对应列表。':'目标已选好；核对对应范围后，再预览或保存学习安排。';
}
function admissionsEvidenceHtml(o){
 const priority=routePriorityInfo(o),ev=o.evidence||{},req=ev.requirements||{},ready=routeSelectable(o),school=platformState.catalog.schools.find(s=>s.id===o.school_id),year=document.getElementById('routeYear').value;
 const docs=[...(ev.documents||[]),...(ev.school_documents||school?.documents||[])],unique=[...new Map(docs.map(x=>[x.url+'|'+(x.page||''),x])).values()];
 const subjects=o.exam_subjects||[],complete=ev.exam_complete??subjects.some(s=>!['大学英语','英语'].includes(s.name));
 return `<div class="admissions-evidence"><div class="evidence-heading"><span class="catalog-badge">${o.year}年资料</span><span class="catalog-badge ${ready?'ready':''}">${ready?'专科对应范围已明确':'仅查阅，不列入候选'}</span></div><h3>${catEsc(o.school_name)} · ${catEsc(o.major_name)}</h3><p class="evidence-year">${o.year}年招生资料列有此专业。<a href="${catEsc(ev.admission?.source_url||o.source_url)}${ev.admission?.page?'#page='+ev.admission.page:''}" target="_blank" rel="noopener">招生依据 ↗</a> ${year!==String(o.year)?`${catEsc(year)}年是否招生、报考条件与科目，尚未录入当年正式文件；以下不是当年报名结论。`:''}</p><dl class="evidence-facts"><div><dt>方向与推荐顺序</dt><dd>${catEsc(priority.group)}。${catEsc(priority.detail)}${priority.profile?` <a href="${catEsc(priority.profile.mirror_url||priority.profile.source_url)}#page=${priority.profile.page}" target="_blank" rel="noopener">衔接方向依据 ↗</a>`:''}</dd></div><div><dt>你的专业是否对口</dt><dd>${catEsc(o.match.reason)}${!ready?' 此项不作为已确认可选目标。':''}</dd></div><div><dt>具体对应条件</dt><dd>${catEsc(req.text||o.eligibility.note)} <a href="${catEsc(req.source_url||o.eligibility.source_url)}${req.page?'#page='+req.page:''}" target="_blank" rel="noopener">查看对应表${req.page?'第'+req.page+'页':''} ↗</a></dd></div><div><dt>需要考什么</dt><dd>${subjects.map(x=>`<div class="evidence-subject"><b>${catEsc(x.name)}</b><span>${[x.points?x.points+'分':'分值未提取',x.minutes?x.minutes+'分钟':'时长未提取',x.mode||''].filter(Boolean).map(catEsc).join(' · ')}</span>${x.textbooks?`<small>参考教材：${catEsc(x.textbooks)}</small>`:''}<a href="${catEsc(x.source_url)}" target="_blank" rel="noopener">科目依据 ↗</a></div>`).join('')}${!complete?'<p class="evidence-gap">专业课名称尚未提取；不是“只考英语”，不据此生成专业课计划。</p>':''}</dd></div><div><dt>普通考生基本要求</dt><dd><ul>${(ev.general_requirements||['查看省厅政策和学校招生简章中的招生对象、资格审核及录取条件。']).map(x=>`<li>${catEsc(x)}</li>`).join('')}</ul><a href="${catEsc(ev.general_source_url||platformState.catalog.provinces[0].source_url)}" target="_blank" rel="noopener">省厅政策原文 ↗</a></dd></div><div><dt>学习资料</dt><dd>${o.learning_pack_id?'本项目的章节计划、题库和作业检查已接入。':'招生资料不等于学习题库；本项目专属学习包尚未接入。'}</dd></div></dl>${ev.missing?.length?`<div class="evidence-gap"><b>具体资料缺口</b><ul>${ev.missing.map(x=>`<li>${catEsc(x)}</li>`).join('')}</ul></div>`:''}<details class="goal-checks"><summary>招生简章、对应表与考试大纲</summary><div class="evidence-docs">${unique.map(d=>`<a href="${catEsc(d.url)}${d.page?'#page='+encodeURIComponent(d.page):''}" target="_blank" rel="noopener">${catEsc(d.title)}${d.page?' · 第'+catEsc(d.page)+'页':''} ↗</a>`).join('')||`<a href="${catEsc(o.source_url)}" target="_blank" rel="noopener">学校项目原文 ↗</a>`}</div></details></div>`;
}
function showAdmissionsEvidence(id){
 const o=platformState.catalog.offerings.find(o=>o.id===id);if(!o)return;
 let dialog=document.getElementById('admissionsDialog');if(!dialog){dialog=document.createElement('dialog');dialog.id='admissionsDialog';dialog.className='admissions-dialog';dialog.setAttribute('aria-label','招生专业资料');document.body.appendChild(dialog)}
 dialog.innerHTML='<button class="evidence-close" aria-label="关闭招生资料">×</button>'+admissionsEvidenceHtml(o)+(routeSelectable(o)?'<button class="primary evidence-choose">选为我的参考学习目标</button>':'<p class="evidence-gap">此项只供查资料，不进入目标选择。</p>');dialog.querySelector('.evidence-close').onclick=()=>dialog.close();const choose=dialog.querySelector('.evidence-choose');if(choose)choose.onclick=()=>{dialog.close();if(routePriorityInfo(o).rank>0)document.getElementById('routeAlternatives').checked=true;quietChooseOffering(o.id)};dialog.showModal();
}
function renderRouteSummary(){
 renderRouteProgress();const o=selectedOffering(),box=document.getElementById('routeSummary');
 if(!o){const source=catalogSource(),all=platformState.catalog?.offerings||[],eligible=all.filter(routeSelectable);box.innerHTML=`<div class="route-eligibility-help"><b>${source?catEsc(source.name)+' → '+new Set(eligible.map(o=>o.major_name)).size+'个已核实本科方向':'专科专业 → 本科专业 → 招生学校'}</b><p>${source?'候选只来自明确对应范围与已提取科目的2026招生项目。未核实的项目不放进可选项，也不等于学校不招。':'先选当前专科专业，系统再列出有明确依据的本科方向与学校。'}</p><small>2027正式资料尚未录入；此处建立的是参考备考目标。</small></div>`;return}
 box.innerHTML=admissionsEvidenceHtml(o);document.getElementById('routeResult').textContent='';
}
function selectionPayload(){const s=catalogSource();return {province:document.getElementById('routeProvince').value,candidate_type:document.getElementById('routeCandidate').value,source_code:s?.code||'manual',source_name:s?.name||document.getElementById('routeSource').value.trim(),offering_id:document.getElementById('routeSchool').value,catalog_revision:platformState.catalog.revision,target_year:Number(document.getElementById('routeYear').value),start_date:document.getElementById('routeStart').value,deadline:document.getElementById('routeDeadline').value,intensity:document.getElementById('routeIntensity').value,daily_minutes:Number(document.getElementById('routeMinutes').value),acknowledged:document.getElementById('routeAcknowledge').checked,generate_plan:document.getElementById('routeGenerate').checked}}
function updateRouteMinutes(){const s=document.getElementById('routeIntensity').value,m={light:180,standard:270,intensive:360};document.getElementById('routeMinutes').disabled=s!=='custom';if(m[s])document.getElementById('routeMinutes').value=m[s]}
function renderCatalog(){
 const c=platformState.catalog,p=platformState.student.route,stats=c.coverage;
 document.getElementById('catalogCurrent').innerHTML=p?`<div class="catalog-current ${platformState.student.update_available?'catalog-update':''}"><span class="route-sprout">♧</span><div><small>我的学习目标 · ${p.target_year}</small><h3>${catEsc(p.source_major.name)} → ${catEsc(p.school_name)} · ${catEsc(p.offering.major_name)}</h3><p>档案保留目录 #${p.catalog_revision} 快照。${platformState.student.update_available?'目录已有新版本；请重新核对再确认更新。':'修改的是本软件的备考目标，不代替官方志愿填报。'}</p></div><button class="outline" id="editStudentRoute">修改目标</button><button class="primary" id="goMyStudy">开始学习 →</button></div>`:`<div class="catalog-current"><span class="route-sprout">✿</span><div><h3>先选对路，我们再一起安排每天。</h3><p>第1步：选择省份和你当前的专科专业。你的作业、计划和学习记录独立保存。</p></div></div>`;
 if(document.getElementById('editStudentRoute'))document.getElementById('editStudentRoute').onclick=()=>{document.getElementById('routeForm').hidden=false;document.getElementById('routeForm').scrollIntoView({behavior:'smooth'})};
 if(document.getElementById('goMyStudy'))document.getElementById('goMyStudy').onclick=()=>navigate('today');
 document.getElementById('catalogStats').innerHTML=[[stats.schools,'省厅参考院校'],[stats.offerings,'院校专业招生项目'],[stats.majors,'已收录本科专业名称'],[stats.learning_packs,'已接入专属学习包']].map(([n,l])=>`<div class="catalog-stat"><b>${n}</b><span>${l}</span></div>`).join('');
 document.getElementById('catalogCoverage').textContent=`${stats.listed_schools}/${stats.schools}所学校已列专业；${stats.structured_rules}/${stats.offerings}个项目已整理结构化对应范围。其余范围待核。专科词典${c.source_majors.length}项，来自${c.source_major_reference.title}。`;
 document.getElementById('catalogVersion').textContent=`目录 #${c.revision} · ${c.version} · 核对 ${c.checked_at}`;
 routeOptions();
}
function renderCatalogResults(){
 const c=platformState.catalog;if(!c)return;const q=document.getElementById('catalogSearch').value.trim().toLowerCase(),filter=document.getElementById('catalogMatch').value,province=document.getElementById('routeProvince').value||'hubei';
 let items=c.offerings.filter(o=>o.province===province&&(!q||(o.school_name+o.major_name+o.major_code).toLowerCase().includes(q))&&(filter==='all'||o.match.state===filter));
 const rank={matched:0,pending:1,not_matched:2,withdrawn:3};items.sort((a,b)=>rank[a.match.state]-rank[b.match.state]||routePriorityInfo(a).rank-routePriorityInfo(b).rank||routePriorityInfo(a).order-routePriorityInfo(b).order||Number(a.eligibility.any)-Number(b.eligibility.any)||a.school_name.localeCompare(b.school_name,'zh-CN'));
 document.getElementById('catalogResultsLabel').textContent=`找到 ${items.length}个院校专业项目 · 按当前专科专业核对2026参考范围，非2027审核结果`;
 const results=document.getElementById('catalogResults');const openedSchools=new Set([...results.querySelectorAll('.catalog-school[open]')].map(x=>x.dataset.schoolId));
 if(platformState.mode==='schools'){
  const schools=c.schools.filter(s=>s.province===province&&(filter==='all'||items.some(o=>o.school_id===s.id))&&(!q||s.name.toLowerCase().includes(q)||items.some(o=>o.school_id===s.id)));
  results.className='catalog-school-list';results.innerHTML=schools.map(s=>{const list=items.filter(o=>o.school_id===s.id);return `<details class="catalog-school" data-school-id="${catEsc(s.id)}" ${openedSchools.has(s.id)?'open':''}><summary>${catEsc(s.name)}<small>${list.length} 个本科项目 · 展开查看</small></summary><div class="school-major-chips">${list.map(o=>`<button data-select-offering="${catEsc(o.id)}" >${catEsc(o.major_name)}<small>${routeSelectable(o)?'对应范围与科目已整理':'查看条件与资料缺口'}</small></button>`).join('')||'<p class="catalog-source">此筛选无项目，或该校专业目录待补；请查看学校原文。</p>'}</div><p class="catalog-source"><a href="${catEsc(s.source_url)}" target="_blank" rel="noopener">学校官方资料 ↗</a></p></details>`}).join('');document.getElementById('catalogMore').hidden=true;
 }else{
  const limit=platformState.page*20;results.className='offering-grid';results.innerHTML=items.slice(0,limit).map(o=>`<article class="offering-card"><div class="offering-head"><span class="offering-school">${catEsc(o.school_name)}</span><span class="catalog-badge ${o.match.state}">${catEsc(o.match.label)}</span></div><h3>${catEsc(o.major_name)}</h3><p>${o.year}年参考项目 · ${catEsc(o.major_code||'专业代码待补')} · 普通考生</p><div class="offering-course-tags">${o.exam_subjects.length?o.exam_subjects.map(x=>`<span>${catEsc(x.name)}</span>`).join(''):'<span>专业课信息待整理</span>'}</div><p>${catEsc(o.match.reason)}</p><details><summary>核对对应范围与来源</summary><p>${catEsc(o.eligibility.note)}</p><div class="catalog-source"><a href="${catEsc(o.eligibility.source_url)}" target="_blank" rel="noopener">对应范围原文 ↗</a> · <a href="${catEsc(o.source_url)}" target="_blank" rel="noopener">招生项目原文 ↗</a></div></details><div class="offering-footer"><span class="catalog-badge ${o.learning_pack_id?'ready':''}">${o.learning_pack_id?'专属学习包已接入':'学习包待补'}</span><button class="outline" data-select-offering="${catEsc(o.id)}" >查看招生资料 →</button></div></article>`).join('')||'<div class="catalog-empty">暂未找到对应项目。试试学校名或本科专业名；也可以切换“全部范围状态”查看待核项目。</div>';
  document.getElementById('catalogMore').hidden=items.length<=limit;document.getElementById('catalogMoreCount').textContent=`已显示 ${Math.min(limit,items.length)} / ${items.length}`;
 }
 document.querySelectorAll('[data-select-offering]').forEach(b=>b.onclick=()=>showAdmissionsEvidence(b.dataset.selectOffering));
}
function bindCatalog(){
 document.getElementById('routeSource').onchange=catalogRun(sourceChanged);document.getElementById('routeProvince').onchange=catalogRun(sourceChanged);document.getElementById('routeYear').onchange=catalogRun(sourceChanged);
 document.getElementById('routeAlternatives').onchange=()=>{const target=document.getElementById('routeTarget').value;fillTargets(target);renderRouteSummary()};
 document.getElementById('routeTarget').onchange=()=>{fillSchools();renderRouteSummary()};document.getElementById('routeSchool').onchange=()=>{document.getElementById('routeAcknowledge').checked=false;renderRouteSummary()};
 document.getElementById('routeIntensity').onchange=updateRouteMinutes;
 document.getElementById('previewStudentRoute').onclick=catalogRun(async()=>{const x=await platformApi('/api/student/preview',selectionPayload());document.getElementById('routeResult').className='route-result';document.getElementById('routeResult').textContent=`${x.days}天 · ${x.plan_kind==='dedicated'?'当前项目的章节学习计划':'资料待补：通用英语＋课程自建过渡计划'} · 已有${x.protected_tasks}项进度任务受保留。${x.note}`});
 document.getElementById('saveStudentRoute').onclick=catalogRun(async()=>{const p=selectionPayload();await platformApi('/api/student/preview',p);if(!confirm(p.generate_plan?'确认保存目标并生成新计划？已完成、自建任务与作业保留。':'确认保存目标？更换路线会移除原路线未开始的系统任务，已完成、自建任务与作业保留。'))return;await platformApi('/api/student/route',p);location.href='/?v=4&view=catalog'});
 document.getElementById('catalogSearch').oninput=document.getElementById('catalogMatch').onchange=()=>{platformState.page=1;renderCatalogResults()};
 document.getElementById('catalogViewMode').onchange=e=>{platformState.mode=e.target.value;renderCatalogResults()};document.getElementById('catalogLoadMore').onclick=()=>{platformState.page++;renderCatalogResults()};
 document.getElementById('exportCatalog').onclick=()=>downloadJson(platformState.catalog,'湖北普通专升本目录.json');
 renderCatalog();installRoutePickers();
}
function downloadJson(obj,name){const a=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(obj,null,2)],{type:'application/json'}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500)}
window.renderCatalogView=async view=>{if(view==='content-admin')try{await renderAdmin()}catch(e){toast(e.message)}};
function showAccount(mode){
 const root=document.getElementById('accountOverlay'),u=platformState.user;root.hidden=false;platformState.authMode=mode||(u?'account':'login');
 const tab=platformState.authMode;
 if(tab==='account'&&u){root.innerHTML=`<div class="auth-panel" role="dialog" aria-modal="true" aria-label="学习账号"><button class="account-close" id="closeAccount" aria-label="关闭">×</button><span class="auth-flower">✿</span><h2>${catEsc(u.display_name)}</h2><div class="auth-info">${u.claimed?'本地账号：'+catEsc(u.username):'原来的学习记录已保留在这个个人空间。'}<br>${u.role==='owner'?'本机资料管理员':'独立学生空间'} · 数据保存在此电脑</div><p>每位学生独立保存目标、计划、作业、错题和模考记录。本机注册不是省考试报名，也尚未开通云端同步。</p>${!u.claimed?'<button class="primary" id="claimAccount">保留现有记录，设置我的账号</button>':''}<button class="outline" id="loginOtherAccount">登录另一个学习账号</button><button class="outline" id="otherAccount">注册另一个学生空间</button><button class="outline" id="logoutAccount">退出 / 切换账号</button></div>`;
  document.getElementById('closeAccount').onclick=()=>root.hidden=true;if(document.getElementById('claimAccount'))document.getElementById('claimAccount').onclick=()=>showAccount('claim');document.getElementById('otherAccount').onclick=()=>showAccount('register');document.getElementById('loginOtherAccount').onclick=()=>showAccount('login');document.getElementById('logoutAccount').onclick=async()=>{if(!confirm('切换账号？已保存的作业和进度保留，本次未保存输入请先保存。'))return;await platformApi('/api/auth/logout',{});location.href='/?v=4&login=1'};return;
 }
 root.innerHTML=`<form class="auth-panel" id="authForm" role="dialog" aria-modal="true" aria-label="登录或注册">${u?'<button type="button" class="account-close" id="closeAccount" aria-label="关闭">×</button>':''}<span class="auth-flower">✿</span><h2>${tab==='claim'?'把这个学习空间留给你':tab==='register'?'从你的升本目标开始':'欢迎回到学习的小天地'}</h2><p>${tab==='claim'?'设置账号会保留当前全部学习记录，并作为本机资料管理员。':'每位学生都有自己的省份、专业、目标学校和学习记录。'}</p><div class="auth-tabs"><button type="button" data-auth-tab="login" class="${tab==='login'?'active':''}">登录</button><button type="button" data-auth-tab="register" class="${tab==='register'?'active':''}">注册新学生</button>${u&&!u.claimed?`<button type="button" data-auth-tab="claim" class="${tab==='claim'?'active':''}">保留当前空间</button>`:''}</div>${tab!=='login'?'<label>怎样称呼你<input name="display_name" maxlength="30" required autocomplete="nickname" placeholder="例如：认真学习的小林"></label>':''}<label>学习账号<input name="username" minlength="3" maxlength="32" required pattern="[A-Za-z0-9_\-]{3,32}" autocomplete="username" placeholder="3—32位英文、数字或下划线"></label><label>密码<input name="password" type="password" minlength="8" maxlength="128" required autocomplete="${tab==='login'?'current-password':'new-password'}" placeholder="至少8位"></label><button class="primary" id="authSubmit">${tab==='login'?'登录学习空间':tab==='claim'?'设置账号，保留我的记录':'注册，下一步选择升本目标'} →</button><div class="auth-error" id="authError" role="alert"></div><small class="catalog-source">单机多账号测试版 · 不采集身份证、学信网密码或省报名账号。</small></form>`;
 if(document.getElementById('closeAccount'))document.getElementById('closeAccount').onclick=()=>root.hidden=true;
 root.querySelectorAll('[data-auth-tab]').forEach(b=>b.onclick=()=>showAccount(b.dataset.authTab));
 document.getElementById('authForm').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target),button=document.getElementById('authSubmit');button.disabled=true;try{await platformApi('/api/auth/'+tab,Object.fromEntries(f));location.href='/?v=4'+(tab==='register'?'&view=catalog':'')}catch(err){document.getElementById('authError').textContent=err.message;button.disabled=false}};
 root.querySelector('input')?.focus();
}
async function renderAdmin(){
 if(platformState.user?.role!=='owner')return;const info=await platformApi('/api/admin/catalog');platformState.admin=info;
 const c=platformState.catalog;document.getElementById('adminStatus').textContent=`当前发布 #${info.active} · 草稿不会影响学生正在使用的资料；发布也不会静默重排学生计划。`;
 document.getElementById('adminHistory').innerHTML=info.versions.map(v=>`<div class="admin-history"><b>#${v.id} ${catEsc(v.label)}</b>${v.id===info.active?' <span class="catalog-badge matched">当前</span>':`<button class="outline" data-restore-catalog="${v.id}">恢复此版本</button>`}<br>${catEsc(v.created_at)}<br>${catEsc(v.note)}</div>`).join('');
 document.getElementById('adminAudit').innerHTML=info.audit.map(x=>`<div class="admin-history">${catEsc(x.created_at)} · ${catEsc(x.action)}<br>${catEsc(x.detail.slice(0,300))}</div>`).join('')||'<p class="catalog-source">还没有人工资料变更。</p>';
 const editable=info.draft?.catalog||info.catalog;document.getElementById('adminJson').value=JSON.stringify(editable,null,2);document.getElementById('adminNote').value=info.draft?.note||'';
 document.getElementById('adminOffering').innerHTML=c.offerings.map(o=>`<option value="${catEsc(o.id)}">${catEsc(o.school_name+' · '+o.major_name)}</option>`).join('');
 fillAdminOffering();showDraft(info.draft);
 document.getElementById('adminOffering').onchange=fillAdminOffering;
 document.getElementById('adminApplyRow').onclick=catalogRun(async()=>{const payload=JSON.parse(document.getElementById('adminJson').value),o=payload.offerings.find(x=>x.id===document.getElementById('adminOffering').value);if(!o)throw Error('草稿中找不到这个招生项目');const name=document.getElementById('adminMajorName').value.trim();if(!name)throw Error('请填写本科专业名称');o.major_name=name;o.eligibility=JSON.parse(document.getElementById('adminRule').value);o.exam_subjects=JSON.parse(document.getElementById('adminSubjects').value);o.source_url=document.getElementById('adminSource').value.trim();o.checked_at=document.getElementById('adminChecked').value;o.offering_status=document.getElementById('adminOfferingStatus').value;document.getElementById('adminJson').value=JSON.stringify(payload,null,2);toast('已写入编辑区；保存校验草稿后才可发布')});
 document.getElementById('adminSaveDraft').onclick=catalogRun(async()=>{const catalog=JSON.parse(document.getElementById('adminJson').value),r=await platformApi('/api/admin/catalog/draft',{catalog,base_revision:info.active,note:document.getElementById('adminNote').value});showDraft(r);toast('草稿已校验保存，尚未发布')});
 document.getElementById('adminPublish').onclick=catalogRun(async()=>{const d=platformState.draft;if(!d)throw Error('先保存并校验草稿');if(!confirm('确认发布预览中的这版目录？学生旧计划保持不变。'))return;await platformApi('/api/admin/catalog/publish',{base_revision:info.active,saved_at:d.saved_at});await loadCatalog(catalogSource()?.code||'');await loadStudent();renderCatalog();await renderAdmin();toast('已发布；学生确认前仍保留旧资料快照')});
 document.getElementById('adminDownload').onclick=()=>downloadJson(JSON.parse(document.getElementById('adminJson').value),'拾光-湖北目录草稿.json');document.getElementById('adminUpload').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;if(f.size>8000000)throw Error('目录文件请小于8MB');const data=JSON.parse(await f.text());document.getElementById('adminJson').value=JSON.stringify(data,null,2);showDraft(null);toast('已载入编辑区；请保存校验和预览后再发布')}catch(err){toast(err.message)}};
 document.querySelectorAll('[data-restore-catalog]').forEach(b=>b.onclick=catalogRun(async()=>{if(!confirm('恢复这个历史目录版本？学生学习数据保持不变。'))return;await platformApi('/api/admin/catalog/rollback',{version_id:Number(b.dataset.restoreCatalog),base_revision:info.active});await loadCatalog();await loadStudent();renderCatalog();await renderAdmin();toast('历史目录已恢复，并留下新的发布记录')}));
}
function fillAdminOffering(){let c;try{c=JSON.parse(document.getElementById('adminJson').value)}catch{return}const o=c.offerings.find(x=>x.id===document.getElementById('adminOffering').value);if(!o)return;document.getElementById('adminMajorName').value=o.major_name;document.getElementById('adminRule').value=JSON.stringify(o.eligibility,null,2);document.getElementById('adminSubjects').value=JSON.stringify(o.exam_subjects,null,2);document.getElementById('adminSource').value=o.source_url;document.getElementById('adminChecked').value=o.checked_at;document.getElementById('adminOfferingStatus').value=o.offering_status}
function showDraft(d){platformState.draft=d;document.getElementById('adminPublish').disabled=!d;document.getElementById('adminDiff').innerHTML=d?`<b>草稿校验通过 · 基于 #${d.base_revision}</b><br>${Object.entries(d.diff).map(([k,x])=>`${({provinces:'省份',schools:'学校',source_majors:'专科专业',offerings:'院校专业项目'})[k]}：新增${x.added}，移除${x.removed}，修改${x.changed}`).join('<br>')}<br>下一步：确认改动和官方来源，再点击发布。`:'尚无已校验草稿。修改只发生在编辑区。'}
