const node=(tag,text='')=>Object.assign(document.createElement(tag),{textContent:text});
function field(box,label,value,type='textarea'){
 const wrap=node('label',label),input=node(type==='textarea'?'textarea':'input');
 if(type!=='textarea')input.type=type;
 input.value=value;wrap.append(input);box.append(wrap);return input;
}
function sourceLink(label,url){
 const a=node('a',label);try{const u=new URL(url);if(['https:','http:'].includes(u.protocol))a.href=u.href;}catch{}
 a.target='_blank';a.rel='noopener noreferrer';return a;
}
async function request(url,body){
 const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const value=await r.json();if(!r.ok)throw Error(typeof value.detail==='string'?value.detail:'Check the scene decisions, source excerpts and clip intervals.');return value;
}
export function reviewPlan(box,job,plan,openJob){
 box.append(node('strong','Scene review · Kokoro af_heart · '+(plan.voice_profile || 'steady')),node('p',plan.promise),node('p',plan.verification));
 for(const issue of plan.attention || [])box.append(node('p',issue));
 for(const item of plan.skipped_library || [])box.append(node('p','Library entry '+item.file+' skipped: '+item.reason));
 const title=field(box,'Truthful title',plan.title,'text');
 const error=node('p');error.setAttribute('role','status');
 const edits=[];
 let complete=Boolean(plan.preparation) && plan.runtime_seconds>=20 && plan.runtime_seconds<=75;
 for(const [index,scene] of plan.scenes.entries()){
  const section=node('section');section.className='passage-editor';section.append(node('h3','Scene '+(index+1)));
  const narration=field(section,'Narration',scene.narration);
  const subject=field(section,'Visual subject',scene.visual.subject,'text');
  const action=field(section,'Visible action',scene.visual.action,'text');
  const purpose=field(section,'Why this shot belongs here',scene.visual.purpose);
  const query=field(section,'Footage search terms',scene.visual.search_query || scene.visual.subject,'text');
  const prepared=plan.preparation?.[index];
  for(const issue of prepared?.attention || [])section.append(node('p',issue));
  if(prepared?.speech){
   const audio=node('audio');audio.controls=true;audio.preload='none';audio.src='/api/content-plans/'+job+'/media/'+index+'/-1';
   audio.setAttribute('aria-label','Scene '+(index+1)+' Kokoro narration');section.append(audio,node('p',prepared.speech.seconds.toFixed(2)+' seconds · '+(prepared.speech.reused?'reused narration':'measured narration')));
  }else complete=false;
  const choices=[];
  for(const [candidate,asset] of (prepared?.candidates || []).entries()){
   const details=node('details');details.append(node('summary','Candidate '+(candidate+1)+' · '+asset.description));
   const video=node('video');video.controls=true;video.preload='none';video.src='/api/content-plans/'+job+'/media/'+index+'/'+candidate;
   details.append(video,node('p',asset.credit+' · '+asset.license),sourceLink('Source and permission evidence ↗',asset.source),node('p','Inspect the actual action. A keyword match is not visual verification.'));
   section.append(details);
  }
  const slots=node('div');section.append(slots);
  function addShot(){
   const row=node('div'),select=node('select');select.setAttribute('aria-label','Scene '+(index+1)+' footage candidate');
   for(const [i,a] of prepared.candidates.entries())select.add(new Option('Candidate '+(i+1)+' · '+a.description,i));
   row.append(select);
   const initial=prepared.candidates[0];
   const start=field(row,'Clip start (seconds)',initial.start,'number');start.step='.1';
   const end=field(row,'Clip end (seconds)',Math.min(initial.end,initial.start+(prepared.speech?.seconds || 7)+1),'number');end.step='.1';
   select.onchange=()=>{const a=prepared.candidates[Number(select.value)];start.value=a.start;end.value=Math.min(a.end,a.start+(prepared.speech?.seconds || 7)+1);};
   const framing=node('select');framing.setAttribute('aria-label','Scene '+(index+1)+' framing');framing.add(new Option('Preserve the whole subject','contain'));framing.add(new Option('Vertical center crop','focus'));row.append(framing);
   const item={select,start,end,framing};choices.push(item);
   const remove=node('button','Remove shot');remove.onclick=()=>{choices.splice(choices.indexOf(item),1);row.remove();};row.append(remove);slots.append(row);
  }
  if(prepared?.candidates.length){addShot();const add=node('button','Add another shot within this passage');add.onclick=()=>{if(choices.length<4)addShot();};section.append(add);}else complete=false;
  const url=field(section,'Source supporting this explanation (URL)','','url');
  const excerpt=field(section,'Supporting passage or factual notes (required for preview)','','textarea');
  edits.push({scene,narration,subject,action,purpose,query,url,excerpt,choices});box.append(section);
 }
 const prepare=node('button','Save edits and find footage');prepare.onclick=async()=>{
  prepare.disabled=true;try{
   const body={topic:plan.topic,title:title.value,promise:plan.promise,payoff:plan.payoff,
    scenes:edits.map(e=>({narration:e.narration.value,visual:{subject:e.subject.value,action:e.action.value,purpose:e.purpose.value,search_query:e.query.value}}))};
   await openJob(await request('/api/content-plans/'+job+'/prepare',body));
  }catch(e){error.textContent=e.message;}finally{prepare.disabled=false;}
 };box.append(prepare);
 const checks=[];
 for(const text of ['I checked the claims against the sources above.','I inspected the footage and it supports each passage without implying an unrelated event.']){
  const label=node('label',text),check=node('input');check.type='checkbox';label.append(check);box.append(label);checks.push(check);
 }
 let changed=false;
 for(const input of [title,...edits.flatMap(e=>[e.narration,e.subject,e.action,e.purpose,e.query])])input.oninput=()=>{changed=true;produce.disabled=true;error.textContent='Save these edits and find footage again before approving. Unchanged narration is reused.';};
 const produce=node('button','Build reviewed private preview');produce.className='primary';produce.disabled=true;
 for(const c of checks)c.onchange=()=>produce.disabled=!complete || changed || !checks.every(c=>c.checked);
 if(!complete)box.append(node('p','Preview is unavailable until each scene has narration and suitable footage. Narrow the scene, revise its visual brief or add licensed video to the local library, then prepare again.'));
 produce.onclick=async()=>{
  produce.disabled=true;try{
   const body={plan_hash:plan.plan_hash,facts_reviewed:checks[0].checked,footage_reviewed:checks[1].checked,
    evidence:edits.map((e,scene)=>({scene,url:e.url.value,supporting_excerpt:e.excerpt.value})),
    shots:edits.map(e=>e.choices.map(c=>({candidate:Number(c.select.value),start:Number(c.start.value),end:Number(c.end.value),treatment:c.framing.value})))};
   await openJob(await request('/api/content-plans/'+job+'/produce',body));
  }catch(e){error.textContent=e.message;produce.disabled=false;}
 };box.append(produce,error);
}
