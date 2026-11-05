const el=(tag,text)=>Object.assign(document.createElement(tag),{textContent:text});
const id=name=>document.getElementById(name);
let offset=0, busy=false;
async function api(url,options){
  const r=await fetch(url,options);
  const value=await r.json();
  if(!r.ok)throw Error(typeof value.detail==='string'?value.detail:'Could not load this request. Check the scene inputs and try again.');
  return value;
}
function references(card){
  const box=el('div','');
  for(const item of card.examples){
    const a=el('a',item.title+' ↗');
    a.href='https://www.youtube.com/watch?v='+item.video;
    a.target='_blank';a.rel='noopener noreferrer';box.append(a);
  }
  return box;
}
function chosen(c){
  if(!c)return;
  const box=id('selection');box.hidden=false;
  box.replaceChildren(el('small','SELECTED FOR PRODUCTION'),el('h2',c.name),
    el('p','Saved direction · '+c.category+' · '+c.channel),
    el('p',c.pitch || 'Choose a current production pick below.'),
    references(c));
  if(!c.format)return;
  const mode=document.createElement('select');mode.setAttribute('aria-label','Production format');mode.add(new Option('Original topic content','content'));mode.add(new Option('Explicit analytics report','analytics'));box.append(mode);
  const make=el('button','Produce video automatically →');make.className='primary';box.append(make);
  mode.onchange=()=>make.textContent=mode.value==='content'?'Produce video automatically →':'Produce analytics report →';
  const daily=el('button','Daily previews');daily.disabled=true;box.append(daily);
  let dailyKey=null;
  function updateDaily(key){
    dailyKey=key;
    daily.textContent=key?'Stop daily previews':'Enable daily previews for this niche';
    daily.title=key?'Active niche: '+key:'One new source set per day while the factory runs.';
  }
  api('/api/daily-preview').then(data=>{updateDaily(data.niche);daily.disabled=false;}).catch(e=>id('status').textContent=e.message);
  daily.onclick=async()=>{
    daily.disabled=true;
    try{const data=await api('/api/daily-preview?key='+encodeURIComponent(dailyKey?'':c.id),{method:'POST'});updateDaily(data.niche);}
    catch(e){id('status').textContent=e.message;}finally{daily.disabled=false;}
  };
  make.onclick=async()=>{
    make.disabled=true;
    try{
      const job=await api('/api/niche-production?key='+encodeURIComponent(c.id)+'&production_format='+mode.value,{method:'POST'});
      localStorage.setItem('activeProduction',job.id);
      await watch(job.id);
    }catch(e){id('status').textContent=e.message;}
    finally{make.disabled=false;}
  };
}
function card(c){
  const a=el('article','');a.className='niche';
  const img=document.createElement('img');img.loading='lazy';img.alt=c.examples[0].title;
  img.src='https://i.ytimg.com/vi/'+c.examples[0].video+'/hqdefault.jpg';
  const b=el('div','');b.className='bodycopy';
  const button=el('button','Choose niche →');button.className='primary';
  button.onclick=async()=>{
    button.disabled=true;
    try{chosen(await api('/api/niche-selection?key='+encodeURIComponent(c.id),{method:'POST'}));id('selection').scrollIntoView();}
    catch(e){id('status').textContent=e.message;}finally{button.disabled=false;}
  };
  const detail=el('details','');detail.append(el('summary','View video evidence ('+c.examples.length+')'),references(c));
  b.append(el('small',c.format.toUpperCase()+'　/　'+c.category.toUpperCase()),el('h2',c.name),
    el('p',c.pitch),el('strong',c.daily_gain!=null?c.daily_gain.toLocaleString()+' views/day since previous scan':c.pace===null?'View counts unavailable':c.pace.toLocaleString()+' views/day · lifetime pace'),
    el('p',c.count+' matching uploads · '+c.channel+' · observed '+c.observed.slice(0,10)),detail,button);
  a.append(img,b);return a;
}
async function page(){
  if(busy||offset===null)return;
  busy=true;id('format').disabled=true;id('category').disabled=true;id('more').disabled=true;
  try{
    const d=await api('/api/niches?offset='+offset+'&category='+encodeURIComponent(id('category').value)+'&format='+encodeURIComponent(id('format').value));
    if(id('category').options.length===1)for(const c of d.categories)id('category').add(new Option(c,c));
    id('stamp').textContent=d.total+' niches · Scan '+d.observed.slice(0,10)+' · '+d.sources+' feeds checked';
    id('cards').append(...d.cards.map(card));offset=d.next;
    id('more').hidden=offset===null;
    id('status').textContent=d.error?'Latest scan failed. Showing saved observations.':d.failed?d.failed+' feeds unavailable. Each card shows its observation date.':offset===null?'You’ve reached the end of this scan. New observations are checked daily while the factory runs.':'';
  }catch(e){id('status').textContent=e.message;}
  finally{busy=false;id('format').disabled=false;id('category').disabled=false;id('more').disabled=false;}
}
id('format').onchange=id('category').onchange=()=>{offset=0;id('cards').replaceChildren();id('more').hidden=false;page();};
id('more').onclick=page;
new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting))page();},{rootMargin:'180px'}).observe(id('more'));
api('/api/niche-selection').then(chosen).catch(e=>id('status').textContent=e.message);
page();

let jobTimer;
async function watch(key){
  clearTimeout(jobTimer);
  const box=id('output');
  const job=(await api('/api/productions')).find(item=>item.id===key);
  if(!job)return;
  if(job.retry_id){localStorage.setItem('activeProduction',job.retry_id);return watch(job.retry_id);}
  box.hidden=false;box.replaceChildren(el('small','PRODUCTION'),el('h2',job.title));
  if(job.status==='planned'){
    const plan=await api('/api/productions/'+key+'/content-plan.json');
    const {automaticPlan}=await import('./remote.js?v=remote1');
    automaticPlan(box,key,plan,async job=>{localStorage.setItem('activeProduction',job.id);await watch(job.id);});
  }else if(job.status==='configured'){box.append(el('p','Remote deployment submitted. Check Factory services for cloud startup status.'));
  }else if(job.status==='ready'){
    const video=document.createElement('video');video.controls=true;video.src='/api/productions/'+key+'/short.mp4';
    const link=el('a','Download MP4');link.href=video.src;link.download='factory-short.mp4';box.append(video,link);
    if(job.source_plan){const revise=el('a','Revise the scene plan');revise.href='/?plan='+job.source_plan+'#discover';box.append(revise);}
    if(job.has_review){const full=el('a','Open full editorial review →');full.href='/?review='+encodeURIComponent(key)+'#production';full.onclick=()=>{localStorage.setItem('explainerJob',key);};box.append(full);}
    if(job.has_report){
      video.poster='/api/productions/'+key+'/cover.jpg';
      const {decisions}=await import('./workers.js?v=narration1');box.append(decisions(job));
    }
  }else{
    box.append(el('p',job.error || (job.status==='running' && job.stage?job.stage:'Factory status · '+job.status)));
    const desk=el('a',['failed','cancelled'].includes(job.status)?'Open production desk to retry →':'Manage this job in the production desk →');
    desk.href='#control';box.append(desk);
    if(['queued','running'].includes(job.status))jobTimer=setTimeout(()=>watch(key).catch(e=>id('status').textContent=e.message),1800);
  }
}
const requestedPlan=new URLSearchParams(location.search).get('plan');
if(requestedPlan)localStorage.setItem('activeProduction',requestedPlan);
if(localStorage.getItem('activeProduction'))watch(localStorage.getItem('activeProduction')).catch(e=>id('status').textContent=e.message);
