/* Exam-specific product layer. All answers are saved explicitly; drafts stay local. */
const exam={data:null,intensity:'standard',preview:null,questions:[],selected:null,attempt:null,started:0,session:null,paperIndex:0,paperTimer:null,saveTimer:null,submitting:false};
const kindName={fill:'填空',trace:'写运行结果',complete:'程序补全',debug:'程序改错',program:'编程',reading:'阅读简答',translation:'翻译',writing:'写作'};
const difficultyName={1:'基础',2:'提升',3:'综合'};
const englishModules=[{id:'grammar',title:'语法与词汇输出'},{id:'reading',title:'阅读简答'},{id:'translation',title:'翻译'},{id:'writing',title:'短文写作'}];
const examCurrentView=()=>document.querySelector('.view.active')?.id.replace('view-','');
const moduleName=id=>exam.data?.pack.modules.find(x=>x.id===id)?.title||englishModules.find(x=>x.id===id)?.title||id;
const runExam=fn=>async()=>{try{await fn()}catch(e){toast(e.message)}};
window.examReady=false;
window.refreshExam=async function(){
 exam.data=await api('/api/exam/dashboard');window.examReady=true;if(exam.data.ready===false){renderPendingPack();return}
 renderExamToday();renderExamPlanSummary();
 const v=examCurrentView();if(v==='exam-profile')renderExamProfile();if(v==='mistakes')await renderExamReviews();
};
window.renderExamView=function(view){
 if(!exam.data)return;if(exam.data.ready===false){renderPendingPack();return}
 if(view==='exam-profile')renderExamProfile();
 if(view==='practice'&&!exam.selected&&!exam.opening)loadQuestions().catch(e=>toast(e.message));
 if(view==='mistakes')renderExamReviews().catch(e=>toast(e.message));
 if(view==='mock'&&!exam.session)renderMockHome();
};
function renderExamToday(){
 if(!exam.data)return;const d=exam.data,p=d.profile;
 $('examTodayBar').innerHTML=`<div class="exam-today-context"><div><span class="context-dot"></span><b>${esc(d.pack.province)} · ${esc(d.pack.institution)}</b><span>${esc(platformState.student?.route?.source_major.name||d.pack.source_major)} → ${esc(d.pack.target_major)}</span></div><button class="text-link" data-go="exam-profile">${p.target_year}备考档案 · ${p.daily_minutes}分钟/天 ↗</button></div><div class="exam-today-actions"><button class="outline" id="todayPractice">开始专项练习 →</button><button class="ghost" data-go="mistakes">${d.stats.due} 道到期复习</button><span>原创训练 · 2027规则待公布</span></div>`;
 $('todayPractice').onclick=()=>openPractice('c',suggestModule());
}
function suggestModule(){
 const list=exam.data.mastery;return (list.find(m=>m.state!=='回忆达标·编程另评'&&m.prerequisites.every(id=>list.find(x=>x.id===id)?.correct_families>=2))||list[0]).id;
}
function renderExamPlanSummary(){
 if(!exam.data)return;const p=exam.data.profile;
 $('examPlanSummary').innerHTML=`<div class="exam-plan-banner"><div><b>不是每天看一个例子，而是一套学习闭环</b><p>概念 → 纸笔专项 → 独立编程 → 延迟复测；英语持续练习。当前净学习 ${p.daily_minutes} 分钟/天，每周留一天降量复盘。</p><small>${esc(p.start_date)} — ${esc(p.deadline)} · 个人计划截止日，不是官方考试日期</small></div><div><button class="outline" data-go="exam-profile">调整强度与日期</button>${exam.data.latest_plan?.status==='active'?'<button class="text-link" id="undoExamPlan">撤回最近一次未开始计划</button>':''}</div></div>`;
 if($('undoExamPlan'))$('undoExamPlan').onclick=runExam(async()=>{if(!confirm('撤回最近一次计划？已有作业或进度的版本会保留。'))return;const r=await api('/api/exam/plan-undo',{});await refresh();toast(`已恢复 ${r.restored_tasks} 项原计划`)});
}
function renderExamProfile(){
 const {pack,profile:p,stats}=exam.data;exam.intensity=p.intensity;exam.preview=null;
 $('examPolicy').innerHTML=`<div class="exam-policy"><div><span class="paper-badge">目标学校专属学习包</span><h2>${esc(platformState.student?.route?.source_major.name||pack.source_major)} → ${esc(pack.institution)} · ${esc(pack.target_major)}</h2><p>${esc(platformState.student?.route?.match.reason||pack.eligibility_note)}</p></div><div class="policy-status"><b>${p.target_year===pack.latest_official_year?'参考年度已核验':p.target_year+'年规则待公布'}</b><span>当前依据 ${pack.latest_official_year} 年官方资料</span><small>个人计划截止日 ≠ 官方考试日期</small></div></div>`;
 $('examPack').innerHTML=exam.data.packs.map(x=>`<option value="${esc(x.id)}">${esc(x.province)} / ${esc(x.institution)} / ${esc(x.target_major)}</option>`).join('');$('examPack').value=p.pack_id;
 $('examYear').value=p.target_year;$('examStart').value=p.start_date;$('examEnd').value=p.deadline;$('examLevel').value=p.base_level;$('examCourse').value=p.course_name;$('examMinutes').value=p.daily_minutes;
 setIntensity(p.intensity);$('planPreview').innerHTML='';
 $('examSources').innerHTML=pack.rules.map(x=>`<div class="exam-rule"><div><b>${esc(x.name)}</b><span>${esc(x.organizer)}</span></div><strong>${x.points}分 <small>/ ${x.minutes}分钟</small></strong></div>`).join('')+`<p class="policy-note">${esc(pack.question_rule)}</p><p class="exam-fine">参考教材：${esc(pack.textbook)}。具体章节权重未公布，不把软件的训练比例当作官方比例。</p><div class="source-links">${pack.sources.map(x=>`<a href="${esc(x.url)}" target="_blank" rel="noopener">↗ ${esc(x.title)}<small>${x.year}资料 · 核对于 ${x.checked_at}</small></a>`).join('')}</div><div class="content-provenance"><b>内容来源说清楚</b><p>${stats.items}道原创训练（${stats.families}个原型，另含参数变式）。未标为官方历年真题；院校专业目录与学习包分开维护；其他项目的内容配齐状态请查看“院校专业库”。</p></div>`;
 $('moduleMap').innerHTML=exam.data.mastery.map((m,i)=>`<article class="module-card"><div class="module-card-head"><span class="module-number">${String(i+1).padStart(2,'0')}</span><span class="module-state">${esc(m.state)}</span></div><h3>${esc(m.title)}</h3><p>${esc(m.concepts)}</p><div class="module-evidence"><span>不同原型回忆 ${m.correct_families}/${m.total_families}</span><span>${m.accuracy===null?'暂无证据':m.accuracy+'%匹配正确'}</span></div><div class="module-progress"><i style="width:${Math.min(100,m.correct_families/m.total_families*100)}%"></i></div><small>前置：${m.prerequisites.map(moduleName).join('、')||'从这里开始'} · 跨日正确 ${m.delayed} 个原型</small><details><summary>本章交付标准与视频映射</summary><p>${esc(m.exit_standard)}</p><label>你的课程对应章节<input id="video-${m.id}" maxlength="200" value="${esc(p.video_mappings[m.id]||'')}" placeholder="例如：第2章 第3—6节"></label><button class="text-link" data-save-video="${m.id}">保存章节对应</button></details><button class="outline" data-module-practice="${m.id}">练这一章 →</button></article>`).join('');
 const registration=document.createElement('div');registration.className='registration-checks';registration.innerHTML=`<h3>统招报考事项，别落下</h3><p>按2026流程列出的个人清单，2027日期待公布。勾选仅作个人记录，不代表官方审核已通过。</p>${(pack.registration_steps||[]).map((step,i)=>`<label><input type="checkbox" data-registration="${step.id}" ${p.registration_checks?.[step.id]?'checked':''}><span><small>0${i+1}</small>${esc(step.title)}</span></label>`).join('')}`;$('examSources').appendChild(registration);
 document.querySelectorAll('[data-registration]').forEach(b=>b.onchange=runExam(async()=>{const next={...exam.data.profile,registration_checks:{...exam.data.profile.registration_checks,[b.dataset.registration]:b.checked}};await api('/api/exam/profile',next);exam.data.profile=next;toast('个人报考清单已保存')}));
 document.querySelectorAll('[data-module-practice]').forEach(b=>b.onclick=()=>openPractice('c',b.dataset.modulePractice));
 document.querySelectorAll('[data-save-video]').forEach(b=>b.onclick=runExam(async()=>{const id=b.dataset.saveVideo;const p={...exam.data.profile,video_mappings:{...exam.data.profile.video_mappings,[id]:$('video-'+id).value}};await api('/api/exam/profile',p);exam.data.profile=p;toast('视频章节对应已保存；下次生成计划会使用它')}));
}
function setIntensity(value){exam.intensity=value;const minutes={light:180,standard:270,intensive:360};if(minutes[value])$('examMinutes').value=minutes[value];$('examMinutes').disabled=value!=='custom';document.querySelectorAll('[data-intensity]').forEach(b=>b.classList.toggle('active',b.dataset.intensity===value))}
function profileFromForm(){return {...exam.data.profile,pack_id:$('examPack').value,target_year:Number($('examYear').value),start_date:$('examStart').value,deadline:$('examEnd').value,base_level:$('examLevel').value,course_name:$('examCourse').value,intensity:exam.intensity,daily_minutes:Number($('examMinutes').value)}}
function renderPreview(x){
 exam.preview=x;$('planPreview').innerHTML=`<div class="plan-preview"><h3>先看清楚，再采用</h3><div class="preview-totals"><b>${x.days}天</b><b>${x.task_count}项可交付任务</b><b>约${Math.round(x.total_minutes/60)}小时净学习</b></div><div class="phase-timeline">${x.phases.map((a,i)=>`<div><span>0${i+1}</span><b>${esc(a.name)}</b><small>${a.start} — ${a.end}</small></div>`).join('')}</div><ul>${x.notes.map(t=>`<li>${esc(t)}</li>`).join('')}</ul><details open><summary>前7天怎样学？</summary>${x.first_days.map(day=>`<div class="preview-day"><b>${day.date} · ${esc(day.module_title)} ${day.weekly_review?'· 降量复盘':''}</b><span>${day.minutes}分钟</span>${day.tasks.map(t=>`<p><strong>${esc(t.title)} · ${t.minutes}分钟</strong>${esc(t.detail)}</p>`).join('')}</div>`).join('')}</details><p class="exam-fine">采用时只替换日期范围内的系统生成、未开始且无作业的任务。已完成、进行中、自建任务和作业全部保留。</p><button class="primary" id="applyExamPlan">采用这个计划</button></div>`;
 $('applyExamPlan').onclick=runExam(async()=>{if(!confirm('采用这个计划，并保留已有学习记录？'))return;const r=await api('/api/exam/plan-apply',x.profile);await refresh();navigate('plan');toast(`已安排 ${r.inserted} 项任务，原学习记录保留`)});
}
function resetModuleFilter(subject,value='all'){
 const modules=subject==='c'?exam.data.pack.modules:englishModules;$('practiceModule').innerHTML='<option value="all">全部知识点</option>'+modules.map(m=>`<option value="${m.id}">${esc(m.title)}</option>`).join('');$('practiceModule').value=value;
}
async function openPractice(subject='c',module='all',kind='all',qid=null){
 exam.opening=true;
 $('practiceSubject').value=subject;resetModuleFilter(subject,module);$('practiceKind').value=kind;
 try{navigate('practice');await loadQuestions(qid)}finally{exam.opening=false}
}
async function loadQuestions(qid=null){
 if(!$('practiceModule').options.length)resetModuleFilter($('practiceSubject').value,suggestModule());
 const params=new URLSearchParams({subject:$('practiceSubject').value,module:$('practiceModule').value,kind:$('practiceKind').value});
 const x=await api('/api/exam/questions?'+params);exam.questions=x.questions;
 $('questionStats').textContent=`${exam.data.stats.c_items}道C语言＋${exam.data.stats.english_items}道英语原创练习；合计${exam.data.stats.families}个原型。含参数变式，不冒充历年真题或押题。`;
 $('catalogCount').textContent=`${x.count}题 / ${x.families}原型`;
 $('questionCatalog').innerHTML=x.questions.map((q,i)=>`<button data-question="${q.id}" class="catalog-item"><span>${String(i+1).padStart(2,'0')}</span><div><b>${esc(q.prompt.split('\n')[0].slice(0,42))}</b><small>${esc(kindName[q.kind])} · ${difficultyName[q.difficulty]} ${q.id.includes('-V')?'· 参数变式':''}</small></div></button>`).join('')||'<p class="exam-fine">这个筛选下还没有题目，换一个题型试试。</p>';
 document.querySelectorAll('[data-question]').forEach(b=>b.onclick=()=>showQuestion(b.dataset.question));
 if(qid&&x.questions.some(q=>q.id===qid))showQuestion(qid);else if(x.questions.length)showQuestion(x.questions[0].id);else{$('questionSheet').innerHTML='<div class="question-empty">换个筛选条件，再开始练习。</div>';exam.selected=null}
}
function showQuestion(id,clear=false){
 const q=exam.questions.find(x=>x.id===id);if(!q)return;exam.selected=q;exam.attempt=null;exam.started=Date.now();
 if(clear)sfStorage.removeItem('exam-draft-'+id);
 document.querySelectorAll('[data-question]').forEach(b=>b.classList.toggle('active',b.dataset.question===id));
 $('questionSheet').innerHTML=`<div class="question-meta"><span class="paper-badge">原创 · 非真题</span><span>${esc(moduleName(q.module))} / ${esc(kindName[q.kind])} / ${difficultyName[q.difficulty]}</span></div><h2>${esc(kindName[q.kind])}练习</h2><div class="question-prompt">${esc(q.prompt)}</div>${q.code?`<pre class="paper-code">${esc(q.code)}</pre>`:''}${q.tests.length?`<details class="sample-tests"><summary>题目给定样例（${q.tests.length}组，非全部情况）</summary>${q.tests.map(t=>`<div><b>输入</b><pre>${esc(t.input||'（空）')}</pre><b>预期输出</b><pre>${esc(t.expected)}</pre></div>`).join('')}</details>`:''}<label class="answer-label">先写你的答案，再看解析<textarea id="practiceAnswer" class="practice-answer ${q.kind==='program'?'code-answer':''}" maxlength="40000" spellcheck="false" placeholder="${q.kind==='program'?'写完整代码或题目指定的函数，并说明思路。':'写下你的独立答案与推导。'}"></textarea></label><div class="draft-status" id="answerDraftStatus">草稿仅存于本浏览器；点击提交才会记入学习记录。</div><div class="exam-actions"><button class="primary" id="submitPractice">提交并查看解析</button><button class="outline" id="nextPractice">下一题 →</button></div><div id="practiceFeedback"></div><div class="source-note">${esc(q.source_note)} · ${q.id}</div>`;
 if(window.learningQuestion)window.learningQuestion(q);
 $('practiceAnswer').value=sfStorage.getItem('exam-draft-'+id)||'';
 $('practiceAnswer').oninput=()=>{exam.attempt=null;$('practiceFeedback').replaceChildren();sfStorage.setItem('exam-draft-'+id,$('practiceAnswer').value);$('answerDraftStatus').textContent='草稿已保存在此浏览器；尚未作为作业提交。'};
 $('practiceAnswer').onkeydown=e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')$('submitPractice').click()};
 $('submitPractice').onclick=runExam(async()=>{const button=$('submitPractice');button.disabled=true;try{const r=await api('/api/exam/answer',{question_id:q.id,answer:$('practiceAnswer').value,duration_seconds:Math.round((Date.now()-exam.started)/1000)});exam.attempt=r;renderQuestionFeedback(q,r);await window.refreshExam()}finally{if($('submitPractice'))$('submitPractice').disabled=false}});
 $('nextPractice').onclick=()=>{const i=exam.questions.findIndex(x=>x.id===id);if(i+1<exam.questions.length)showQuestion(exam.questions[i+1].id);else toast('这组题已经到最后一题，可以换知识点或复习错题')};
}
function renderQuestionFeedback(q,r){
 $('practiceFeedback').innerHTML=`<div class="question-feedback ${r.correct===0?'needs-work':''}"><div class="feedback-heading"><h3>${esc(r.verdict)}</h3><span>下次复习 ${r.next_review}</span></div><p>${esc(r.note)}</p><details open><summary>参考解法与评分点（不代表唯一解）</summary><pre class="paper-code">${esc(r.answer)}</pre><p>${esc(r.explanation)}</p>${r.rubric.length?`<ul>${r.rubric.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}</details><div class="exam-actions">${q.subject==='c'&&q.kind==='program'?'<button class="outline" id="checkPracticeCode">编译并运行给定样例</button>':''}<button class="outline" id="aiPractice">AI辅助复核我的答案</button><button class="text-link" id="retryPractice">遮住解析再做</button></div><pre id="extraPracticeFeedback" class="extra-feedback" hidden></pre><label>复盘原因<textarea id="practiceErrorNote" maxlength="1000" placeholder="例如：整数除法理解错了；循环边界少了一次；仍不理解指针指向哪里。"></textarea></label><div class="exam-actions"><button class="outline" id="understoodPractice">对照后理解了</button><button class="outline" id="unclearPractice">还没弄明白</button></div><small>自评与AI建议单独记录，不冒充客观正确率或官方分数。</small></div>`;
 const extra=async(path,body)=>{const box=$('extraPracticeFeedback');box.hidden=false;box.textContent='正在处理…';try{const x=await api(path,body);box.textContent=x.verdict+'\n'+x.feedback+(x.note?'\n'+x.note:'')}catch(e){box.textContent='本次未完成：'+e.message}};
 if($('checkPracticeCode'))$('checkPracticeCode').onclick=()=>extra('/api/exam/code-check',{attempt_id:r.attempt_id});
 $('aiPractice').onclick=()=>extra('/api/exam/ai-review',{attempt_id:r.attempt_id,provider:sfStorage.getItem('sf-provider')||'ollama',model:sfStorage.getItem('sf-model')||'qwen2.5-coder:7b'});
 $('retryPractice').onclick=()=>showQuestion(q.id,true);
 for(const [id,rating] of [['understoodPractice','understood'],['unclearPractice','unclear']])$(id).onclick=runExam(async()=>{await api('/api/exam/self-review',{attempt_id:r.attempt_id,rating,error_note:$('practiceErrorNote').value});toast('复盘已保存；记得到期再独立作答')});
}
async function renderExamReviews(){
 const x=await api('/api/exam/reviews');const today=todayShanghai();const due=x.items.filter(a=>a.due_date<=today);
 $('reviewQueue').innerHTML=`<div class="review-summary"><div><b>${due.length}</b><span>到期复习</span></div><div><b>${x.items.length}</b><span>已安排复习</span></div><p>正确后也会安排延迟复测；“做过”与“隔天还会”分开记录。未作答和自评不会提高掌握度。</p></div><div class="review-queue-list">${x.items.map(a=>`<article class="review-queue-item"><div><span class="paper-badge ${a.due_date<=today?'due-badge':''}">${a.due_date<=today?'今天可复习':a.due_date+'复习'}</span><h3>${esc(a.question.prompt.split('\n')[0].slice(0,85))}</h3><p>${esc(moduleName(a.question.module))} · ${kindName[a.question.kind]} · 匹配错误 ${a.errors} 次 · 跨日连续正确 ${a.streak} 次</p>${a.latest?.error_note?`<small>上次复盘：${esc(a.latest.error_note)}</small>`:''}</div><button class="outline" data-review-question="${a.question.id}">独立再做 →</button></article>`).join('')||'<div class="exam-card question-empty">先完成一道专项练习，这里会自动安排复习。<button class="outline" data-go="practice">去练习</button></div>'}</div>`;
 document.querySelectorAll('[data-review-question]').forEach(b=>b.onclick=()=>{const q=x.items.find(x=>x.question.id===b.dataset.reviewQuestion).question;openPractice(q.subject,q.module,'all',q.id)});
}
function renderMockHome(){
 const sessions=exam.data.sessions;
 $('mockArea').innerHTML=`<div class="mock-options"><article class="exam-card"><span class="mock-icon">◎</span><h2>基础诊断</h2><p>10题 / 20分钟。抽样检查知识缺口，不用一次小测预测录取。</p><button class="primary" data-start-mode="diagnostic" data-subject="c">开始C语言诊断</button></article><article class="exam-card"><span class="mock-icon">✎</span><h2>C语言闭卷模拟</h2><p>90分钟 / 150分。原创填空、结果分析、改错、补全与编程混合。</p><button class="outline" data-start-mode="mock" data-subject="c">开始C语言模拟</button></article><article class="exam-card"><span class="mock-icon">Aa</span><h2>大学英语模拟</h2><p>120分钟 / 100分。原创填空、阅读简答、翻译与写作，无选择题。</p><button class="outline" data-start-mode="mock" data-subject="english">开始英语模拟</button></article></div><div class="exam-card mock-explainer"><h3>计时、评分和记录怎样工作？</h3><p>答案会自动保存；刷新可继续同一份试卷。到时按已保存答案交卷。自动分仅来自可明确匹配的题目；代码、翻译、写作及等价解法需要复核，显示为“待复核分值”，不拼成虚假的总成绩。</p><p>当前依据2026时长与满分训练；各题型比例是软件自定义。2027资料公布后需更新路线包。</p></div><div class="section-head"><h2>我的诊断与模考记录</h2></div><div class="exam-card">${sessions.map(s=>`<button class="session-row" data-session="${s.id}"><span><b>${s.subject==='c'?'C语言':'大学英语'} · ${s.mode==='diagnostic'?'诊断':'模拟'}</b><small>${esc(s.started_at.slice(0,16).replace('T',' '))}</small></span><span>${s.status==='active'?'继续作答 →':'查看结果 →'}</span></button>`).join('')||'<p class="exam-fine">第一次诊断从这里开始，记录会保存在本机。</p>'}</div>`;
 document.querySelectorAll('[data-start-mode]').forEach(b=>b.onclick=runExam(async()=>{exam.session=await api('/api/exam/session-start',{mode:b.dataset.startMode,subject:b.dataset.subject});exam.paperIndex=0;renderSession()}));
 document.querySelectorAll('[data-session]').forEach(b=>b.onclick=runExam(async()=>{exam.session=await api('/api/exam/session?id='+b.dataset.session);exam.paperIndex=0;renderSession()}));
}
function renderSession(){
 clearInterval(exam.paperTimer);clearTimeout(exam.saveTimer);
 if(exam.session.status==='finished'){renderSessionResult();return}
 const s=exam.session;exam.serverOffset=new Date(s.server_now).getTime()-Date.now();
 $('mockArea').innerHTML=`<div class="paper-top"><div><span class="paper-badge">原创练习卷 · 非官方分值结构</span><h2>${s.subject==='c'?'C语言':'大学英语'}${s.mode==='diagnostic'?'诊断':'模拟'}</h2></div><div class="paper-countdown"><small>剩余时间</small><b id="paperClock"></b><span id="paperSaveStatus">答案自动保存</span></div><button class="primary" id="submitPaper">结束并交卷</button></div><div class="paper-layout"><div class="exam-card"><h3>答题卡</h3><div id="paperNumbers" class="paper-numbers"></div><p class="exam-fine">浅绿为已填答案，不表示正确。刷新后在记录里继续；交卷后才能查看参考解法。</p></div><div class="exam-card" id="paperQuestion"></div></div>`;
 $('submitPaper').onclick=runExam(async()=>{if(!confirm('确认交卷并查看结果？主观题仍需复核。'))return;await submitPaper()});
 renderPaperQuestion();tickPaper();exam.paperTimer=setInterval(tickPaper,1000);
}
function renderPaperQuestion(){
 const s=exam.session,q=s.questions[exam.paperIndex];
 $('paperNumbers').innerHTML=s.questions.map((x,i)=>`<button class="${i===exam.paperIndex?'active ':''}${s.answers[x.id]?.trim()?'answered':''}" data-paper-index="${i}">${i+1}</button>`).join('');
 document.querySelectorAll('[data-paper-index]').forEach(b=>b.onclick=runExam(async()=>{await savePaper();if(exam.session.status!=='active')return;exam.paperIndex=Number(b.dataset.paperIndex);renderPaperQuestion()}));
 $('paperQuestion').innerHTML=`<div class="question-meta"><span>第${exam.paperIndex+1}/${s.questions.length}题 · ${kindName[q.kind]}</span><b>${Number(q.points)||0}分</b></div><div class="question-prompt">${esc(q.prompt)}</div>${q.code?`<pre class="paper-code">${esc(q.code)}</pre>`:''}<label class="answer-label">独立作答<textarea id="paperAnswer" class="practice-answer ${q.kind==='program'?'code-answer':''}" maxlength="40000" spellcheck="false" placeholder="先按纸笔考试的方式推导，再输入答案。"></textarea></label><div class="exam-actions"><button class="outline" id="paperPrev" ${exam.paperIndex===0?'disabled':''}>← 上一题</button><button class="outline" id="paperNext" ${exam.paperIndex===s.questions.length-1?'disabled':''}>下一题 →</button><span class="exam-fine">本页不展示解析</span></div>`;
 $('paperAnswer').value=s.answers[q.id]||'';
 $('paperAnswer').oninput=()=>{s.answers[q.id]=$('paperAnswer').value;$('paperSaveStatus').textContent='正在保存…';clearTimeout(exam.saveTimer);exam.saveTimer=setTimeout(()=>savePaper().catch(e=>{$('paperSaveStatus').textContent='尚未保存，请重试';toast(e.message)}),600);document.querySelector(`[data-paper-index="${exam.paperIndex}"]`)?.classList.toggle('answered',!!s.answers[q.id].trim())};
 for(const [id,delta] of [['paperPrev',-1],['paperNext',1]])$(id).onclick=runExam(async()=>{await savePaper();if(exam.session.status!=='active')return;exam.paperIndex+=delta;renderPaperQuestion()});
}
async function savePaper(){
 clearTimeout(exam.saveTimer);const s=exam.session;if(!s||s.status!=='active')return;
 const r=await api('/api/exam/session-save',{id:s.id,answers:s.answers});
 if(r.status==='finished'){exam.session=r;renderSessionResult();return}
 if($('paperSaveStatus'))$('paperSaveStatus').textContent='已保存在本机 '+new Date().toLocaleTimeString('zh-CN');
}
function tickPaper(){const s=exam.session;if(!s||s.status!=='active')return;const remaining=Math.max(0,Math.floor((new Date(s.deadline).getTime()-Date.now()-(exam.serverOffset||0))/1000));if($('paperClock'))$('paperClock').textContent=clockText(remaining);if(!remaining&&!exam.submitting)submitPaper().catch(e=>toast(e.message))}
async function submitPaper(){
 if(exam.submitting)return;exam.submitting=true;clearTimeout(exam.saveTimer);
 try{exam.session=await api('/api/exam/session-submit',{id:exam.session.id,answers:exam.session.answers});await window.refreshExam();renderSessionResult()}finally{exam.submitting=false}
}
function renderSessionResult(){
 clearInterval(exam.paperTimer);const s=exam.session,r=s.result;
 $('mockArea').innerHTML=`<div class="exam-card mock-result"><span class="overline">不是看一个分数，而是找到下一步</span><h2>本次${s.mode==='diagnostic'?'诊断':'模拟'}已结束</h2><div class="result-numbers"><div><b>${Number(r.objective_earned)||0}<small>/${Number(r.objective_max)||0}</small></b><span>客观题参考匹配分</span></div><div><b>${Number(r.pending_points)||0}</b><span>分值待主观复核</span></div></div><p>${esc(r.note)}</p><div class="exam-actions"><button class="primary" id="resultToPractice">去补前置薄弱章</button><button class="outline" id="backMockHome">回到模考记录</button></div></div><div class="result-details">${r.items.map((x,i)=>`<details class="exam-card"><summary>第${i+1}题 · ${Number(x.points)||0}分 · ${esc(x.verdict)}</summary><div class="question-prompt">${esc(s.questions[i].prompt)}</div><h4>我的答案</h4><pre class="paper-code">${esc(s.answers[x.id]||'（未作答）')}</pre><h4>参考解法与复核要点</h4><pre class="paper-code">${esc(x.answer)}</pre><p>${esc(x.explanation)}</p><small>${x.correct===null?'需要对照思路、步骤和边界逐项复核；此部分没有计入自动分。':'按参考答案匹配；等价表达可另行复核。'}</small></details>`).join('')}</div>`;
 $('resultToPractice').onclick=()=>openPractice(s.subject,s.subject==='c'?suggestModule():'grammar');
 document.querySelectorAll('.result-details>details').forEach((detail,i)=>{const q=s.questions[i],button=document.createElement('button');button.className='outline result-correction';button.textContent='带着这道题去订正 / AI辅助复核 →';button.onclick=()=>{sfStorage.setItem('exam-draft-'+q.id,s.answers[q.id]||'');openPractice(q.subject,q.module,'all',q.id)};detail.appendChild(button)});
 $('backMockHome').onclick=()=>{exam.session=null;renderMockHome()};
}
function bindExam(){
 document.querySelectorAll('[data-intensity]').forEach(b=>b.onclick=()=>{setIntensity(b.dataset.intensity);exam.preview=null;$('planPreview').innerHTML=''});
 $('previewExamPlan').onclick=runExam(async()=>renderPreview(await api('/api/exam/plan-preview',profileFromForm())));
 $('saveExamProfile').onclick=runExam(async()=>{await api('/api/exam/profile',profileFromForm());await window.refreshExam();toast('升本档案已保存；当前任务未被重排')});
 for(const id of ['examPack','examYear','examStart','examEnd','examLevel','examCourse','examMinutes'])$(id).oninput=()=>{exam.preview=null;$('planPreview').innerHTML=''};
 $('practiceSubject').onchange=()=>{resetModuleFilter($('practiceSubject').value);$('practiceKind').value='all';loadQuestions().catch(e=>toast(e.message))};
 $('practiceModule').onchange=$('practiceKind').onchange=()=>loadQuestions().catch(e=>toast(e.message));
 $('weakestPractice').onclick=()=>openPractice('c',suggestModule());
 window.addEventListener('beforeunload',e=>{if(exam.session?.status==='active'){e.preventDefault();e.returnValue=''}});
}
bindExam();window.baseReady.then(ok=>{if(ok)return window.refreshExam().then(()=>{if(exam.data.ready!==false)resetModuleFilter('c',suggestModule())})}).catch(e=>toast('升本模块启动未完成：'+e.message));

function renderPendingPack(){
 const p=platformState.student?.route;const title=p?`${p.school_name} · ${p.offering.major_name}`:'先建立你的升本档案';
 $('examTodayBar').innerHTML=`<div class="exam-today-context"><b>${esc(title)}</b><button class="text-link" data-go="catalog">${p?'资料与学习目标 ↗':'选择省份、专科专业与学校 →'}</button></div>`;
 $('examPlanSummary').innerHTML=`<div class="exam-plan-banner"><div><b>${p?'当前使用资料待补的过渡任务':'你的专属计划，从选择目标开始'}</b><p>不把其他专业的C语言题库套用到你的考试。专业课科目、章纲与练习包按路线单独接入。</p></div><button class="outline" data-go="catalog">查看资料进度</button></div>`;
 for(const v of ['exam-profile','practice','mistakes','mock']){const section=$('view-'+v);section.classList.add('pending-pack');let box=section.querySelector('.route-placeholder');if(!box){box=document.createElement('div');box.className='route-placeholder';section.appendChild(box)}box.innerHTML=`<span class="overline">资料状态说清楚</span><h2>${esc(title)}</h2><p>${p?'这条路线已可建立独立档案、提交自建任务作业；专属章节题库与模考尚待接入。当前专业课信息可到院校专业库查看原文。':'先在院校专业库选择当前专科专业、目标本科专业和学校。'}</p><button class="outline" data-go="catalog">回到院校专业库 →</button>`}
}
