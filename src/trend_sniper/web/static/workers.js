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
      const [report,info]=await Promise.all([json(base+'production-report.json'),json('/api/releases/'+job.id)]);
      if(seq!==request)return;
      const a=report.script_assessment;
      const sceneList=node('ol','');
      for(const shot of report.materials.scenes)sceneList.append(node('li',
        (shot.visual?shot.visual.description+' · '+shot.visual.license:shot.visual_fallback)+' / '+shot.cue+' / '+shot.seconds+'s'));
      body.replaceChildren(node('h3','Script selection'),node('p',report.script_count+' complete cuts · selected #'+report.winning_script+
        (a.score!=null?' · editorial score '+a.score+'/100':'')),node('p',report.writer),
        anchor('Inspect all drafts and scores',base+'script-options.json'),
        node('h3','Scene materials'),sceneList,anchor('Open research packet',base+'observation.json'),
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
