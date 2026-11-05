import {decisions} from './workers.js?v=narration1';
const byId = id => document.getElementById(id);
const node = (tag,text='',className='') => Object.assign(document.createElement(tag),{textContent:text,className});
const link = (text,url) => Object.assign(node('a',text),{href:url});
const names = {queued:'Waiting',running:'In production',ready:'Ready to review',planned:'Saved draft',configured:'Cloud deployment',failed:'Needs attention',cancelled:'Stopped'};
const phases = ['Sources','Scripts','Voice','Materials','Covers','Assembly','Review'];
const phaseFor = stage => {
  if(/Private preview/.test(stage))return 6;
  if(/Planning release|Compiling/.test(stage))return 5;
  if(/covers/.test(stage))return 4;
  if(/materials/.test(stage))return 3;
  if(/narration/.test(stage))return 2;
  if(/scripts/.test(stage))return 1;
  return 0;
};
let timer, generation=0, filter='all', rows=[], queuePaused=false, loading=false;
async function request(url,method='GET',body){
  const r=await fetch(url,{method,headers:body?{'Content-Type':'application/json'}:undefined,
    body:body?JSON.stringify(body):undefined});
  const value=await r.json();
  if(!r.ok)throw Error(typeof value.detail==='string'?value.detail:'This request could not be completed.');
  return value;
}
function message(text){byId('desk-message').textContent=text;}
function date(value){return value?new Date(value).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'}):'Earlier run';}
function applyFilter(){
  const query=byId('job-search').value.trim().toLowerCase();
  let visible=0;
  for(const row of rows){
    const box=byId('jobs').querySelector('[data-job="'+row.id+'"]');
    const match=filter==='all' || (filter==='active' && ['queued','running'].includes(row.status)) ||
      (filter==='ready' && ['ready','planned'].includes(row.status)) || (filter==='attention' && ['failed','cancelled'].includes(row.status) && !row.retry_id);
    box.hidden=!match || !(row.title+' '+row.format).toLowerCase().includes(query);
    if(!box.hidden)visible++;
  }
  byId('job-empty').hidden=visible>0;
  byId('job-empty').textContent=rows.length?'No episodes match this view.':'Your queue is clear. Choose a niche in Discover to produce your first preview.';
}
function controls(job){
  const bar=node('div','','episode-actions');
  if(job.retry_id){bar.append(node('span','A later attempt exists. See the newer episode above.'));return bar;}
  let action;
  if(['failed','cancelled'].includes(job.status))action='retry';
  if(['queued','running'].includes(job.status))action='cancel';
  if(!action)return bar;
  const button=node('button',action==='retry'?'Retry saved sources':job.status==='queued'?'Remove from queue':'Stop after current step');
  button.disabled=Boolean(job.cancel_requested && action==='cancel');
  if(button.disabled)button.textContent='Stop requested…';
  button.onclick=async()=>{
    button.disabled=true;
    try{
      await request('/api/productions/'+job.id+'/'+action,'POST');
      message(action==='retry'?'A new attempt was queued. Your previous attempt stays in the history.':'Stop saved. A running operation may need time to finish.');
      await refresh();
    }catch(error){message(error.message);button.disabled=false;}
  };
  bar.append(button);return bar;
}
function history(job){
  const detail=node('details','','episode-history');
  detail.append(node('summary','Activity & timing'));
  const body=node('div');detail.append(body);
  detail.addEventListener('toggle',async()=>{
    if(!detail.open)return;
    body.textContent='Loading activity…';
    try{
      const events=await request('/api/productions/'+job.id+'/history');
      const list=node('ol');
      for(const item of events){
        const entry=node('li');entry.append(node('time',date(item.at)),node('span',item.stage));list.append(entry);
      }
      body.replaceChildren(list);
      if(!events.length)body.append(node('p','This earlier preview predates activity tracking.'));
      body.append(node('p',job.runtime_seconds==null?'Runtime was not recorded.':'Worker time · '+job.runtime_seconds.toFixed(1)+' seconds'));
      body.append(node('p',job.paid_api_usd==null?'API spend was not recorded for this attempt.':'Paid API spend · $'+job.paid_api_usd.toFixed(2)+' · excludes your device and electricity.'));
    }catch(error){body.textContent=error.message;}
  });return detail;
}
function episode(job){
  const box=node('article','','episode');
  box.dataset.job=job.id;
  box.dataset.signature=JSON.stringify([job.status,job.stage,job.error,job.cancel_requested,job.retry_id,job.finished_at]);
  const header=node('div','','episode-header');
  const title=node('div');title.append(node('small',job.format+' / ATTEMPT '+(job.attempt||1)),node('h3',job.title));
  header.append(title,node('span',names[job.status]||job.status,'status-pill state-'+job.status));
  const main=node('div','','episode-main');
  const content=node('div','','episode-content');
  content.append(node('p',date(job.created_at),'episode-date'));
  if(job.status==='planned'){
    content.append(node('h4','Topic plan ready'),node('p','Review narration, sources and footage before preview production.'),link('Continue scene review','/?plan='+job.id+'#discover'));
  }else if(job.status==='ready'){
    const base='/api/productions/'+job.id+'/';
    const video=Object.assign(node('video'),{controls:true,preload:'none',src:base+'short.mp4'});
    if(job.has_report)video.poster=base+'cover.jpg';
    video.setAttribute('aria-label','Preview '+job.title);
    main.append(video);
    content.append(node('h4','Your private preview is ready.'),node('p','Watch the edit, inspect the source and cover choices, then review the exact upload copy.'));
    const links=node('div','','episode-actions');
    const download=link('Download MP4',base+'short.mp4');download.download='factory-short.mp4';
    links.append(download,link('Title & description',base+'metadata.txt'));content.append(links);
    if(job.has_report)content.append(decisions(job));
  }else{
    const stage=node('p',job.cancel_requested && job.status==='running'?'Stop requested. Finishing the current operation.':job.error || job.stage || names[job.status],'current-stage');
    content.append(stage);
    if(['queued','running'].includes(job.status)){
      const rail=node('ol','','stage-rail');
      const active=phaseFor(job.stage||'');
      phases.forEach((name,index)=>{
        const step=node('li',name,index<active?'done':index===active && job.status==='running'?'current':'');
        if(step.className==='current')step.setAttribute('aria-current','step');rail.append(step);
      });content.append(rail);
      content.append(node('p',job.status==='queued'?'Starts when a worker is available and the queue is resumed.':'The factory records each completed stage. You can leave this page open or return later.','muted'));
    }
    content.append(controls(job));
  }
  content.append(history(job));main.append(content);box.append(header,main);
  const release=node('p','','release-receipt');release.dataset.receipt='';box.append(release);
  return box;
}
function metrics(state){
  const values=[['Waiting',state.counts.queued||0],['In production',state.counts.running||0],['Ready to review',state.counts.ready||0],
    ['Needs attention',state.attention_count||0]];
  byId('desk-metrics').replaceChildren(...values.map(([name,value])=>{
    const tile=node('div');tile.append(node('strong',String(value)),node('span',name));return tile;
  }));
  queuePaused=state.paused;
  byId('queue-state').textContent=state.paused?'Queue paused':'Queue active';
  byId('queue-state').className='status-pill '+(state.paused?'state-queued':'state-ready');
  byId('queue-toggle').textContent=state.paused?'Resume queue':'Pause queue';byId('queue-toggle').disabled=false;
}
async function refresh(){
  const seq=generation;
  if(loading)return;
  loading=true;
  try{
    const [list,state,daily]=await Promise.all([request('/api/productions'),request('/api/production-desk'),request('/api/daily-preview')]);
    if(seq!==generation)return;
    rows=list;metrics(state);
    byId('daily-state').textContent=daily.niche?'Daily previews enabled · '+daily.niche:'Daily previews off';
    byId('daily-stop').hidden=!daily.niche;
    const container=byId('jobs');
    for(const [index,job] of list.entries()){
      let box=container.querySelector('[data-job="'+job.id+'"]');
      const signature=JSON.stringify([job.status,job.stage,job.error,job.cancel_requested,job.retry_id,job.finished_at]);
      if(box?.dataset.signature!==signature){
        const next=episode(job);
        if(box)box.replaceWith(next);else container.insertBefore(next,container.children[index]||null);
        box=next;
      }
      box.querySelector('[data-receipt]').textContent=job.release_state?'YouTube release · '+job.release_state.replaceAll('_',' '):'';
    }
    applyFilter();
  }catch(error){if(seq===generation)message(error.message+' Refresh to try again.');}
  finally{loading=false;}
}
async function services(){
  const button=byId('services-refresh');button.disabled=true;
  try{
    const data=await request('/api/factory-readiness');
    const items=[['Encoder',data.renderer.available?'Available':'Unavailable',data.renderer.detail],
      ['Story writer',data.writer.available?'Local model installed':'Built-in story fallback',data.writer.detail],
      ['Footage checker',data.vision.available?'Local model installed':'Unavailable',data.vision.detail],
      ['Media search',data.commons.enabled?'Enabled':'Disabled',data.commons.detail],
      ['Cleared library',data.library.entries+' catalog entries',data.library.error||data.library.detail],
      ['YouTube',data.youtube.channel?'Saved connection':'Not connected',data.youtube.detail],
      ['Voiceover',data.narration.available?'Kokoro ready':'Narration unavailable',data.narration.detail],['Analytics','Not connected',data.analytics.detail]];
    byId('service-grid').replaceChildren(...items.map(([name,state,detail])=>{
      const card=node('article');card.append(node('small',name),node('h3',state),node('p',detail));return card;
    }));
    byId('readiness-summary').textContent='Local rendering · '+(data.youtube.channel?'saved channel':'preview mode');
  }catch(error){message(error.message);}finally{button.disabled=false;}
}
export function stopDesk(){clearTimeout(timer);generation++;}
export async function jobs(){
  clearTimeout(timer);
  await refresh();
  if(location.hash==='#control' && !byId('control').hidden)timer=setTimeout(jobs,2200);
}
byId('queue-toggle').onclick=async()=>{
  byId('queue-toggle').disabled=true;
  try{await request('/api/production-desk','PUT',{paused:!queuePaused});message(queuePaused?'Queue resumed.':'Queue paused. The current operation can finish.');await refresh();}
  catch(error){message(error.message);}finally{byId('queue-toggle').disabled=false;}
};
byId('daily-stop').onclick=async()=>{
  try{await request('/api/daily-preview?key=','POST');message('Daily previews stopped. Existing jobs remain in the queue.');await refresh();}
  catch(error){message(error.message);}
};
byId('desk-refresh').onclick=()=>{message('');jobs();};
byId('services-refresh').onclick=services;
byId('readiness').addEventListener('toggle',()=>{if(byId('readiness').open)services();});
byId('job-search').oninput=applyFilter;
for(const button of byId('job-filters').querySelectorAll('button'))button.onclick=()=>{
  filter=button.dataset.filter;
  for(const item of byId('job-filters').querySelectorAll('button'))item.setAttribute('aria-pressed',String(item===button));
  applyFilter();
};

async function voicePreference(){
  try{
    const data=await request('/api/production-preferences');
    byId('voice-mode').value=data.narration;byId('voice-mode').disabled=false;
    byId('voice-status').textContent='Saved for new analytics jobs. Topic explainers require Kokoro. Existing previews and retries stay unchanged.';
  }catch(error){byId('voice-status').textContent=error.message;}
}
byId('voice-mode').onchange=async()=>{
  const input=byId('voice-mode');input.disabled=true;
  try{
    await request('/api/production-preferences','PUT',{narration:input.value});
    byId('voice-status').textContent=input.value==='required'?'New analytics jobs stop if speech is unavailable.':'Saved for analytics jobs. Topic explainers always require Kokoro.';
  }catch(error){byId('voice-status').textContent=error.message;}finally{input.disabled=false;}
};
voicePreference();
