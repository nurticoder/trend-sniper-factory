const node=(tag,text='')=>Object.assign(document.createElement(tag),{textContent:text});
async function api(url,method='GET',body){
 const r=await fetch(url,{method,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});
 const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Cloud connection request failed');return data;
}
async function refresh(){
 const status=document.getElementById('remote-worker-status');if(!status)return;
 try{const data=await api('/api/remote-worker');status.textContent=data.detail;return data;}catch(e){status.textContent=e.message;return {connected:false};}
}
export function automaticPlan(box,job,plan,open){
 box.append(node('strong','The factory handles footage and editing'),node('p','This is a saved draft. The factory will research its claims again, search several sources, inspect matching moments and revise unsuccessful scenes before building a remote preview.'));
 const details=node('details');details.append(node('summary','Inspect the saved draft'));
 for(const scene of plan.scenes || [])details.append(node('p',scene.narration));box.append(details);
 const button=node('button','Finish video automatically');button.className='primary';box.append(button);
 const message=node('p');message.setAttribute('role','status');box.append(message);
 button.onclick=async()=>{button.disabled=true;try{
  const connection=await refresh();
  if(!connection?.connected){message.textContent='Connect the cloud worker once in Factory services. Source footage will not be downloaded to this computer.';const link=node('a','Open cloud connection');link.href='#control';link.onclick=()=>document.getElementById('readiness').open=true;message.append(link);return;}
  await open(await api('/api/content-plans/'+job+'/automatic','POST'));
 }catch(e){message.textContent=e.message;}finally{button.disabled=false;}};
}
const form=document.getElementById('remote-connect');
if(form){form.onsubmit=async e=>{e.preventDefault();const token=document.getElementById('remote-token'),button=form.querySelector('button');button.disabled=true;
 try{const job=await api('/api/remote-worker/connect','POST',{token:token.value,space_name:document.getElementById('remote-space').value});token.value='';
  document.getElementById('remote-worker-status').textContent='Checking eligibility and deploying CPU Basic. No subscription or hardware upgrade will be purchased.';
  const poll=async()=>{try{const state=(await api('/api/productions')).find(x=>x.id===job.id);if(['queued','running'].includes(state?.status)){document.getElementById('remote-worker-status').textContent=state.stage || state.status;setTimeout(poll,2000);}else if(state?.status==='failed'){document.getElementById('remote-worker-status').textContent=state.error;}else await refresh();}catch(e){document.getElementById('remote-worker-status').textContent=e.message;}};poll();
 }catch(e){document.getElementById('remote-worker-status').textContent=e.message;}finally{token.value='';button.disabled=false;}};
 refresh();
}
