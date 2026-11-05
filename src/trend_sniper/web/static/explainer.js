const $=id=>document.getElementById(id);
const node=(tag,text='',cls='')=>Object.assign(document.createElement(tag),{textContent:text,className:cls});
const link=(text,url)=>Object.assign(node('a',text),{href:url});
let data,activeJob,timer;
async function api(url,method='GET',body){
 const r=await fetch(url,{method,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});
 const value=await r.json();if(!r.ok)throw Error(typeof value.detail==='string'?value.detail:'Invalid edit. Check narration, references and shot intervals.');return value;
}
function message(text){$('explainer-status').textContent=text;}
function field(label,value,tag='textarea'){
 const box=node('label',label);const input=node(tag);input.value=value;box.append(input);return [box,input];
}
function project(item){
 const box=node('article','','explainer-project');
 box.append(node('small','SOURCED EXPLAINER / REVISION '+item.revision),node('h2',item.brief.title),node('p',item.brief.angle),node('p','Promise · '+item.brief.promise),node('p','Payoff · '+item.brief.payoff));
 const details=node('details');details.append(node('summary','Inspect or revise narration and shot decisions'));
 const title=field('Truthful title',item.brief.title,'input');details.append(title[0]);
 const edits=[];
 for(const passage of item.brief.passages){
  const section=node('section','','passage-editor');section.append(node('h3',passage.id));
  const spoken=field('Narration',passage.narration);section.append(spoken[0]);
  const pause=field('Pause after passage (seconds)',passage.pause_after,'input');pause[1].type='number';pause[1].min='.1';pause[1].max='.8';pause[1].step='.05';section.append(pause[0]);
  const shots=[];
  for(const shot of passage.shots){
   const row=node('details');row.append(node('summary',shot.subject));
   const asset=node('select');for(const value of ['Moving_Water_in_Space-8K','Fluids_on_the_Space_Station','original-orbit'])asset.add(new Option(value,value));asset.value=shot.asset;
   const label=node('label','Replace with cleared source');label.append(asset);row.append(label);
   const framing=node('select');for(const value of ['focus','contain'])framing.add(new Option(value==='focus'?'Prominent vertical crop':'Preserve entire widescreen image',value));framing.value=shot.treatment==='orbit'?'focus':shot.treatment;const framingLabel=node('label','Framing');framingLabel.append(framing);row.append(framingLabel);
   const purpose=field('Why this shot belongs here',shot.purpose);row.append(purpose[0],node('p','Action · '+shot.action));
   const start=field('Source in (seconds)',shot.start,'input'),end=field('Source out (seconds)',shot.end,'input');
   for(const control of [start,end]){control[1].type='number';control[1].step='.1';row.append(control[0]);}
   const focus=field('Horizontal subject focus (0.2–0.8)',shot.focus_x??.5,'input'),crop=field('Retained source height (0.5–1)',shot.crop_height??1,'input');for(const item of [focus,crop]){item[1].type='number';item[1].step='.01';row.append(item[0]);}
   shots.push({shot,asset,framing,focus:focus[1],crop:crop[1],purpose:purpose[1],start:start[1],end:end[1]});section.append(row);
  }
  edits.push({passage,spoken:spoken[1],pause:pause[1],shots});details.append(section);
 }
 const pronunciation=field('Pronunciation replacements (one original = spoken form per line)',Object.entries(item.brief.pronunciations).map(([a,b])=>a+' = '+b).join('\n'));details.append(pronunciation[0]);
 const save=node('button','Save a new revision');details.append(save);
 save.onclick=async()=>{
  save.disabled=true;
  try{
   const brief={...item.brief,title:title[1].value,pronunciations:Object.fromEntries(pronunciation[1].value.split('\n').filter(x=>x.includes('=')).map(x=>x.split('=').map(x=>x.trim()))),
    passages:edits.map(x=>({...x.passage,narration:x.spoken.value,pause_after:Number(x.pause.value),shots:x.shots.map(y=>({...y.shot,focus_x:Number(y.focus.value),crop_height:Number(y.crop.value),asset:y.asset.value,purpose:y.purpose.value,start:Number(y.start.value),end:Number(y.end.value),treatment:y.asset.value==='original-orbit'?'orbit':y.framing.value}))}))};
   await api('/api/explainer-briefs/'+item.id,'PUT',{expected_revision:item.revision,brief});message('Revision saved. Unchanged speech and footage are reused by content hash.');await load();
  }catch(e){message(e.message);}finally{save.disabled=false;}
 };
 const focus=node('button','Use prominent vertical framing');focus.onclick=async()=>{
  try{const brief=structuredClone(item.brief);for(const p of brief.passages)for(const shot of p.shots)if(shot.asset!=='original-orbit')shot.treatment='focus';
   await api('/api/explainer-briefs/'+item.id,'PUT',{expected_revision:item.revision,brief});message('New framing revision saved. Research and narration are reused.');await load();
  }catch(e){message(e.message);}};
 const produce=node('button','Produce private preview','primary');produce.onclick=async()=>{
  produce.disabled=true;try{const job=await api('/api/explainer-briefs/'+item.id+'/produce','POST');activeJob=job.id;localStorage.setItem('explainerJob',activeJob);await watch();}catch(e){message(e.message);}finally{produce.disabled=false;}
 };
 box.append(details,focus,produce);
 for(const run of data.runs.filter(r=>r.project===item.id)){
  const open=node('button','Open revision '+run.revision+' · '+run.voice);open.onclick=()=>{activeJob=run.job;localStorage.setItem('explainerJob',activeJob);watch();};box.append(open);
 }
 return box;
}
async function load(){
 try{
  data=await api('/api/explainer-studio');$('explainer-scope').textContent=data.scope;
  $('auditions').replaceChildren();
  for(const [id,profile] of Object.entries(data.profiles)){
   const box=node('article');box.append(node('h3',profile.label));
   const state=data.auditions.find(a=>a.id===id);
   if(state?.state==='ready'){const audio=node('audio');audio.controls=true;audio.preload='metadata';audio.src='/api/explainer-auditions/'+id;audio.setAttribute('aria-label',profile.label+' audition');box.append(audio);}
   else box.append(node('p',state?.error || state?.state || 'Generate a short audition to listen.'));
   const choose=node('button',id===data.selected_voice?'Selected delivery':'Use this delivery');choose.disabled=id===data.selected_voice;
   choose.onclick=async()=>{try{await api('/api/explainer-voice','PUT',{voice:id});await load();}catch(e){message(e.message);}};box.append(choose);$('auditions').append(box);
  }
  $('explainer-projects').replaceChildren(...data.projects.map(project));
  if(data.auditions.some(x=>['queued','running'].includes(x.state)))setTimeout(load,1800);
 }catch(e){message(e.message);}
}
async function watch(){
 clearTimeout(timer);if(!activeJob)return;
 const box=$('explainer-review');box.hidden=false;
 try{
  const state=await api('/api/explainer-review/'+activeJob);
  if(state.state!=='ready'){
   const jobs=await api('/api/productions'),job=jobs.find(x=>x.id===activeJob);
   box.replaceChildren(node('h2',state.state==='failed'?'Production needs attention':'Production in progress'),node('p',state.error || job?.stage || state.state));
   if(state.state==='failed'){
    box.append(node('p','Revise the passage or select another inspected clip above. Unavailable material is not replaced by slides.'));
    const retry=node('button','Retry saved inputs');retry.onclick=async()=>{try{const result=await api('/api/productions/'+activeJob+'/retry','POST');activeJob=result.id;localStorage.setItem('explainerJob',activeJob);watch();}catch(e){message(e.message);}};box.append(retry);
   }
   if(['queued','running'].includes(state.state))timer=setTimeout(watch,1500);return;
  }
  const base='/api/productions/'+activeJob+'/',r=state.report;
  const video=node('video');video.controls=true;video.preload='metadata';video.src=base+'short.mp4';
  const poster=node('img');poster.src=base+'cover.jpg';poster.alt=r.brief.title;
  box.replaceChildren(node('small','FINISHED PRIVATE PREVIEW / NOT PUBLISHED'),node('h2',r.brief.title),video,node('p','Paid APIs · $0 · '+r.technical.duration_seconds.toFixed(1)+' seconds · 720 × 1280 at 24fps'),link('Download MP4',base+'short.mp4'));
  const packaging=node('details');packaging.append(node('summary','Title, thumbnail and upload copy'),poster,link('Open title and description',base+'metadata.txt'));box.append(packaging);
  const issues=node('section');issues.append(node('h3','Editorial review'));
  for(const issue of r.attention)issues.append(node('p',issue.scene+' · '+issue.reason));
  if(r.attention.some(x=>x.scene==='mechanism')){
   const replace=node('button','Save alternate view for the mechanism');replace.onclick=async()=>{
    try{const state=await api('/api/explainer-studio'),run=state.runs.find(x=>x.job===activeJob),item=state.projects.find(x=>x.id===run?.project);if(!item)throw Error('Project link unavailable; reopen the current brief.');const brief=structuredClone(item.brief);
     brief.passages.find(p=>p.id==='mechanism').shots=[{asset:'Fluids_on_the_Space_Station',start:50,end:58,subject:'Attached water globule on the space station',action:'The water stays together as the globule moves',purpose:'Show cohesion without the occluding hand; illustrative of the force, not a molecular recording',treatment:'focus',focus_x:.5,crop_height:1}];
     await api('/api/explainer-briefs/'+item.id,'PUT',{expected_revision:item.revision,brief});message('Replacement saved as a new revision. Produce it when ready; the current preview is retained.');await load();
    }catch(e){message(e.message);}};issues.append(replace);
  }
  box.append(issues);
  const timeline=node('details');timeline.append(node('summary','Scenes, sources, selected footage and reusable speech'));
  for(const passage of r.brief.passages){
   timeline.append(node('h3',passage.id),node('p',passage.narration));
   for(const shot of r.shots.filter(s=>s.passage===passage.id))timeline.append(node('p',shot.timeline_start.toFixed(2)+'s · '+shot.subject+' · '+shot.duration.toFixed(2)+'s'),node('p','Purpose · '+shot.purpose));
  }
  for(const source of r.sources)timeline.append(link('Subject source ↗',source.url));
  for(const asset of r.assets)timeline.append(node('p',asset.credit+' · '+asset.license+' · SHA-256 '+asset.sha256),link('Original footage and metadata ↗',asset.source));
  timeline.append(link('Full quality and provenance report',base+'review.json'),link('Caption file',base+'captions.srt'));box.append(timeline);
  const label=node('label','I watched the finished preview and reviewed the factual and footage decisions. ');const check=node('input');check.type='checkbox';label.append(check);
  const approve=node('button',state.approved?'Private review recorded':'Record private editorial approval');approve.disabled=true;
  check.onchange=()=>approve.disabled=!check.checked || state.approved;
  approve.onclick=async()=>{try{await api('/api/explainer-review/'+activeJob,'POST',{manifest_hash:state.manifest_hash,watched:check.checked});approve.textContent='Private review recorded';approve.disabled=true;}catch(e){message(e.message);}};
  box.append(label,approve,node('p','Publishing is disabled for this pilot. Approval here records your editorial review only.'));
 }catch(e){message(e.message);}
}
$('explainer-intake').onsubmit=async e=>{e.preventDefault();const button=$('explainer-create');button.disabled=true;
 try{await api('/api/explainer-briefs','POST',{topic:$('explainer-topic').value});message('Original sourced brief prepared. Inspect or revise it, then produce your preview.');await load();}catch(e){message(e.message);}finally{button.disabled=false;}};
$('make-auditions').onclick=async()=>{try{await api('/api/explainer-auditions','POST');await load();}catch(e){message(e.message);}};
activeJob=new URLSearchParams(location.search).get('review') || localStorage.getItem('explainerJob');load();if(activeJob)watch();
