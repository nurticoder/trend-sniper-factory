// All user/source strings are inserted as text, including release errors.
const node=(tag,text)=>Object.assign(document.createElement(tag),{textContent:text});
const anchor=(text,url)=>Object.assign(node('a',text),{href:url});
function image(url,alt){return Object.assign(document.createElement('img'),{src:url,alt,loading:'lazy'});}
async function json(url,options){
  const r=await fetch(url,options);
  const data=await r.json();
  if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Invalid release details');
  return data;
}
function field(label,input){
  const el=node('label',label+' ');
  el.append(input);return el;
}
function choice(options){
  const input=document.createElement('select');
  input.required=true;
  input.add(new Option('Choose…',''));
  for(const [value,label] of options)input.add(new Option(label,value));
  return input;
}
function reviewForm(job,info,release,meta){
  const form=node('form','');
  form.className='release-form';
  const audience=choice([['made_for_kids','Made for kids'],['not_made_for_kids','Not made for kids']]);
  const synthetic=choice([['yes','Disclosure applies'],['no','Disclosure does not apply']]);
  const timestamp=Object.assign(document.createElement('input'),{type:'datetime-local',required:true});
  const suggested=new Date(release.proposed_at);
  timestamp.value=new Date(suggested-suggested.getTimezoneOffset()*60000).toISOString().slice(0,16);
  const checkbox=Object.assign(document.createElement('input'),{type:'checkbox',required:true});
  const submit=node('button','Schedule on YouTube');
  const status=node('p','');
  form.append(node('h3','Schedule reviewed video'),node('p',info.channel.name+' · '+info.channel.id),
    node('pre',meta),field('Audience',audience),field('Altered or synthetic media',synthetic),
    field('Publish in your browser timezone ('+Intl.DateTimeFormat().resolvedOptions().timeZone+')',timestamp),
    field('I watched this preview and checked the claims, rights and upload copy.',checkbox),submit,status);
  form.onsubmit=async event=>{
    event.preventDefault();submit.disabled=true;
    try{
      await json('/api/releases/'+job.id,{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({manifest_hash:info.manifest_hash,channel_id:info.channel.id,
          publish_at:new Date(timestamp.value).toISOString(),audience:audience.value,
          synthetic:synthetic.value==='yes',reviewed:checkbox.checked})});
      status.textContent='Release queued. Reopen this panel to see the remote receipt.';
    }catch(error){status.textContent=error.message;submit.disabled=false;}
  };
  return form;
}

function storyboard(script,report){
  const section=node('details','');section.className='storyboard';
  section.append(node('summary','Selected edit · '+script.scenes.reduce((n,shot)=>n+shot.seconds,0)+' seconds'));
  const list=node('ol','');let at=0;
  for(const [index,shot] of script.scenes.entries()){
    const row=node('li','');const material=report.materials.scenes[index];
    row.append(node('small',at+'–'+(at+shot.seconds)+'s / '+shot.heading),node('strong',shot.value),node('p',shot.caption));
    row.append(node('p','Sound · '+(material?.effect?.description || material?.cue || 'Original score')));
    if(shot.source){
      try{
        const url=new URL(shot.source);
        if(url.protocol==='https:' || url.protocol==='http:'){
          const source=anchor('Open source evidence ↗',url.href);source.target='_blank';source.rel='noopener noreferrer';row.append(source);
        }
      }catch{/* An invalid reference remains excluded from navigation. */}
    }
    list.append(row);at+=shot.seconds;
  }
  section.append(list);return section;
}
function draftComparison(pool){
  const box=node('details','');box.className='draft-comparison';
  box.append(node('summary','Compare leading script candidates'));
  const list=node('ol','');
  const candidates=[...pool.drafts].filter(d=>d.assessment?.eligible!==false)
    .sort((a,b)=>(b.assessment?.score || 0)-(a.assessment?.score || 0)).slice(0,5);
  if(!candidates.some(d=>d.id===pool.winner)){
    const winner=pool.drafts.find(d=>d.id===pool.winner);if(winner)candidates.unshift(winner);
  }
  for(const draft of candidates){
    const row=node('li','');row.append(node('strong','#'+draft.id+(draft.id===pool.winner?' · Selected':'')+
      (draft.assessment?.score!=null?' · '+draft.assessment.score+'/100':'')),
      node('p',draft.scenes.map(s=>s.value).join(' → ')));
    const criteria=Object.entries(draft.assessment?.criteria || {}).map(([name,value])=>name.replaceAll('_',' ')+': '+value).join(' · ');
    if(criteria)row.append(node('small',criteria));list.append(row);
  }
  box.append(node('p','Editorial scores compare these drafts. They are not predictions of views or retention.'),list);
  return box;
}
export function decisions(job){
  const box=node('details','');
  box.className='worker-report';
  box.append(node('summary','Workers, covers & release plan'));
  const body=node('div','');box.append(body);
  let request=0;
  box.addEventListener('toggle',async()=>{
    const seq=++request;
    if(!box.open)return;
    const base='/api/productions/'+job.id+'/';
    body.textContent='Loading this run…';
    try{
      const [report,info,script,pool]=await Promise.all([json(base+'production-report.json'),json('/api/releases/'+job.id),json(base+'script.json'),json(base+'script-options.json')]);
      if(seq!==request)return;
      const a=report.script_assessment;
      const sceneList=node('ol','');
      for(const shot of report.materials.scenes)sceneList.append(node('li',
        (shot.visual?shot.visual.description+' · '+shot.visual.license:shot.visual_fallback)+' / '+shot.cue+' / '+shot.seconds+'s'));
      body.replaceChildren(node('h3','Script selection'),node('p',report.script_count+' complete cuts · selected #'+report.winning_script+
        (a.score!=null?' · editorial score '+a.score+'/100':'')),node('p',report.writer),
        anchor('Inspect all drafts and scores',base+'script-options.json'),
        draftComparison(pool),storyboard(script,report),
        node('h3','Scene materials'),sceneList,
        node('p','Music · '+(report.materials.music?.description || report.materials.music_fallback)),
        node('p',report.rejected_assets.length+' library entries rejected · '+report.online_search.reduce((n,s)=>n+(s.eligible_files||0),0)+' eligible files found online'),anchor('Open research packet',base+'observation.json'),
        node('h3','Cover selection'),node('p','Selected #'+report.covers.winner.number+' of '+report.covers.candidates.length+
          ' · '+report.covers.winner.concept+' · '+report.covers.winner.font_px+' px headline'),
        image(base+'cover-options.jpg','Twelve generated cover options in reading order'),
        anchor('Download selected cover',base+'cover.jpg'),node('h3','Release window'),
        node('p',report.release.proposed_at+' · '+report.release.timezone),node('p',report.release.reason),
        anchor('Inspect complete run report',base+'production-report.json'));
      if(info.state!=='awaiting_review')body.append(node('p','Release status · '+info.state+(info.error?' · '+info.error:'')));
      if(info.video_id)body.append(anchor('Open video on YouTube','https://www.youtube.com/watch?v='+encodeURIComponent(info.video_id)));
      if(!info.channel)body.append(node('p','Local preview. Connect the owner channel to enable reviewed scheduling.'));
      else if(['awaiting_review','preflight_failed'].includes(info.state)){
        const copy=await fetch(base+'metadata.txt');
        if(!copy.ok)throw Error('Upload copy unavailable');
        const meta=await copy.text();
        if(seq===request)body.append(reviewForm(job,info,report.release,meta));
      }
    }catch(error){if(seq===request)body.textContent=error.message;}
  });
  return box;
}
