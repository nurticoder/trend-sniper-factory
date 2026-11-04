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
