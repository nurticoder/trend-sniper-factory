import {decisions} from './workers.js';
const byId = id => document.getElementById(id);
function element(tag,text) {
  const node=document.createElement(tag);
  node.textContent=text;
  return node;
}
async function request(url,method='GET') {
  const response=await fetch(url,{method});
  if (!response.ok) throw new Error((await response.json()).detail || 'Request failed');
  return response.json();
}
function link(text,url) {
  const a=element('a',text); a.href=url; return a;
}
function display(data) {
  byId('steam-stamp').textContent='Steam observations · '+data.date+' UTC';
  byId('picks').replaceChildren(...data.cards.map(c=>{
    const card=element('article',''); card.className='pick';
    const label=element('span',c.niche); label.className='card-label';
    const move=c.last_week_rank===-1?'No previous rank reported.':('Climbed '+(c.last_week_rank-c.rank)+' places from #'+c.last_week_rank+'.');
    card.append(label,element('h2',c.name),element('strong','Rank #'+c.rank+' · '+c.peak_in_game.toLocaleString()+' peak players'),element('p',move+(c.last_week_rank===-1?' Guess-the-game reveal using its player count.':' An animated before-and-after follows its climb through the chart.')),link('View chart evidence ↗',data.source));
    const button=element('button','Produce Short →');button.className='primary';
    button.onclick=async()=>{
      button.disabled=true;
      try {await request('/api/radar/'+c.appid+'/produce','POST');location.hash='control';}
      catch(e){byId('message').textContent=e.message;}
      finally{button.disabled=false;}
    };
    card.append(button);return card;
  }));
}
let timer;
async function jobs(){
  clearTimeout(timer);
  const list=await request('/api/productions');
  const container=byId('jobs');
  // Keep completed previews and review forms mounted while the queue updates.
  if(list.length && !container.children.length)container.textContent='';
  list.forEach((j,index)=>{
    const previous=container.querySelector('[data-job="'+j.id+'"]');
    const signature=JSON.stringify([j.status,j.stage,j.error,j.has_report]);
    if(previous?.dataset.signature===signature)return;
    const box=element('article','');box.className='job';
    box.append(element('h3',j.title),element('p',j.status==='failed'?j.error:(j.status==='running' && j.stage?j.stage:j.status)));
    if(j.status==='ready'){
      const base='/api/productions/'+j.id+'/';
      const video=element('video','');video.controls=true;video.preload='metadata';video.src=base+'short.mp4';
      const download=link('Download MP4',video.src);download.download='short.mp4';
      if(j.has_report)video.poster=base+'cover.jpg';
      box.append(video,download,link('Title & description',base+'metadata.txt'));
      if(j.has_report)box.append(decisions(j));
    }
    box.dataset.job=j.id;
    box.dataset.signature=signature;
    if(previous)previous.replaceWith(box);
    else container.insertBefore(box,container.children[index] || null);
  });
  if(!list.length)byId('jobs').textContent='Choose a recommendation above to produce your first Short.';
  if(list.some(j=>['queued','running'].includes(j.status)))timer=setTimeout(()=>jobs().catch(report),1800);
}
function report(e){byId('message').textContent=e.message;}
async function scan(){
  byId('scan').disabled=true;byId('message').textContent='Checking the latest chart and resolving game titles…';
  try{display(await request('/api/radar/refresh','POST'));byId('message').textContent='Rank movement measures Steam activity. YouTube demand is still unmeasured.';}
  catch(e){report(e);}finally{byId('scan').disabled=false;}
}
export function openSteam(){
byId('scan').onclick=scan;
request('/api/radar').then(data=>{display(data);if(Date.now()-Date.parse(data.date)>86400000)scan();}).catch(report);
}
export {jobs};
