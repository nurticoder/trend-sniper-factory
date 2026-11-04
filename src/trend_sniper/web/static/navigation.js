import {openSteam} from './radar.js';
import {jobs,stopDesk} from './desk.js?v=operations1';

const panels = [...document.querySelectorAll('[data-panel]')];
const navigation = document.querySelector('nav[aria-label="Control center"]');
let steamLoaded = false;

async function showBriefs(){
  const box=document.getElementById('briefs');
  try{
    const response=await fetch('/api/workspace');
    if(!response.ok)throw Error();
    const data=await response.json();
    box.replaceChildren();
    for(const opportunity of data.opportunities){
      const entry=document.createElement('details');
      const title=document.createElement('summary');
      title.textContent=opportunity.topic;
      entry.append(title);
      const note=document.createElement('p');
      note.textContent=opportunity.hypothesis || opportunity.niche;
      entry.append(note);
      for(const idea of data.ideas.filter(i=>i.opportunity_id===opportunity.id)){
        const script=document.createElement('p');
        script.textContent=idea.title+' — '+(idea.script || idea.hook || 'Draft');
        entry.append(script);
      }
      box.append(entry);
    }
    if(!data.opportunities.length)box.textContent='No saved briefs yet.';
  }catch{box.textContent='Could not load saved briefs. Reopen Control room to retry.';}
}

function navigate(){
  stopDesk();
  const active=panels.find(p=>'#'+p.id===location.hash) || panels[0];
  for(const panel of panels)panel.hidden=panel!==active;
  for(const link of navigation.querySelectorAll('a')){
    if(link.hash==='#'+active.id)link.setAttribute('aria-current','page');
    else link.removeAttribute('aria-current');
  }
  if(active.id==='steam' && !steamLoaded){openSteam();steamLoaded=true;}
  if(active.id==='control'){
    showBriefs();
    jobs();
  }
  window.scrollTo(0,0);
}
window.addEventListener('hashchange',navigate);
navigate();
