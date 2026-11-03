const el=(tag,text)=>Object.assign(document.createElement(tag),{textContent:text});
const id=name=>document.getElementById(name);
let offset=0, busy=false;
async function api(url,options){
  const r=await fetch(url,options);
  if(!r.ok)throw Error('Could not load this request. Try again.');
  return r.json();
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
    el('p','Production brief: create an original illustrated explainer around one viewer question raised by these examples.'),
    references(c));
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
  b.append(el('small',c.category.toUpperCase()),el('h2',c.name),
    el('strong',c.pace===null?'View counts unavailable':c.pace.toLocaleString()+' views/day'),
    el('p',c.count+' matching uploads · '+c.channel+' · observed '+c.observed.slice(0,10)),detail,button);
  a.append(img,b);return a;
}
async function page(){
  if(busy||offset===null)return;
  busy=true;id('category').disabled=true;id('more').disabled=true;
  try{
    const d=await api('/api/niches?offset='+offset+'&category='+encodeURIComponent(id('category').value));
    if(id('category').options.length===1)for(const c of d.categories)id('category').add(new Option(c,c));
    id('stamp').textContent=d.total+' niches · Scan '+d.observed.slice(0,10)+' · '+d.sources+' feeds checked';
    id('cards').append(...d.cards.map(card));offset=d.next;
    id('more').hidden=offset===null;
    id('status').textContent=d.error?'Latest scan failed. Showing saved observations.':d.failed?d.failed+' feeds unavailable. Each card shows its observation date.':offset===null?'You’ve reached the end of this scan. New observations are checked daily while the factory runs.':'';
  }catch(e){id('status').textContent=e.message;}
  finally{busy=false;id('category').disabled=false;id('more').disabled=false;}
}
id('category').onchange=()=>{offset=0;id('cards').replaceChildren();id('more').hidden=false;page();};
id('more').onclick=page;
new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting))page();},{rootMargin:'180px'}).observe(id('more'));
api('/api/niche-selection').then(chosen).catch(e=>id('status').textContent=e.message);
page();
