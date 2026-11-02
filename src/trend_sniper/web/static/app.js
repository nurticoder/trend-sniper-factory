'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = {opportunities: [], ideas: [], view: 'board', loaded: false};
const dirty = new Map();
const saving = new Set();
let parentId = null;
let ideaId = null;
let toastTimer;
const labels = {research: 'Research', idea: 'Ideas', writing: 'Writing', script_ready: 'Script ready'};

function toast(message) {
  const box = $('#toast'); box.textContent = message; box.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { box.hidden = true; }, 4000);
}
async function api(path, options = {}) {
  const response = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
  const body = await response.json();
  if (!response.ok) {
    const detail = body.detail;
    const message = Array.isArray(detail) ? detail.map(e => `${e.loc.slice(1).join('.')}: ${e.msg}`).join('\n') : detail;
    throw new Error(message || `Request failed (${response.status})`);
  }
  return body;
}
function dateLabel(value) {
  return value ? new Date(value).toLocaleDateString(undefined, {month:'short', day:'numeric', year:'numeric'}) : 'No dated evidence';
}
function inputDate(value) {
  if (!value) return '';
  const date = new Date(value); return new Date(date - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}
function activeOpportunities() { return state.opportunities.filter(o => !o.archived); }
function matches(item, extra = '') {
  const query = $('#search').value.trim().toLowerCase();
  return !query || `${item.topic || ''} ${item.niche || ''} ${item.title || ''} ${item.hook || ''} ${extra}`.toLowerCase().includes(query);
}
function draw() {
  if (!state.loaded) return;
  const active = activeOpportunities();
  const ids = new Set(active.map(o => o.id));
  const ideas = state.ideas.filter(i => ids.has(i.opportunity_id));
  const ready = ideas.filter(i => i.stage === 'script_ready');
  $('#stats').innerHTML = [
    [active.length, 'Opportunities', '↗', 'Saved topics to investigate'],
    [ideas.length, 'Ideas in development', '≡', 'Original angles and scripts'],
    [ready.length, 'Scripts ready', '✓', 'Ready for production planning'],
  ].map(([value, title, icon, note]) => `<article class="stat"><div class="stat-top">${title}<span class="stat-icon" aria-hidden="true">${icon}</span></div><div class="stat-value">${value}</div><div class="stat-note">${note}</div></article>`).join('');
  const opportunities = state.opportunities.filter(o => ($('#show-archived').checked || !o.archived));
  const opportunityMap = new Map(opportunities.map(o => [o.id, o]));
  const shown = opportunities.filter(o => matches(o) || state.ideas.some(i => i.opportunity_id === o.id && matches(i)));
  const isLibrary = state.view === 'library';
  $('#view-name').textContent = isLibrary ? 'Opportunity library' : 'Control room';
  $('#page-title').innerHTML = isLibrary ? 'Opportunity library<span>.</span>' : 'The control room<span>.</span>';
  $('#page-subtitle').textContent = isLibrary ? 'Every topic, source and original angle. In one place.' : 'Find the angle. Build the story. Make something original.';
  $('#workspace-title').textContent = isLibrary ? 'Saved opportunities' : 'Your pipeline';
  $('#workspace-count').textContent = `${shown.length} ${shown.length === 1 ? 'opportunity' : 'opportunities'}`;
  if (isLibrary) {
    $('#workspace').innerHTML = shown.length ? `<div class="library-grid">${shown.map(opportunityCard).join('')}</div>` : `<div class="library-empty"><h3>${state.opportunities.length ? 'No matching opportunities' : 'Your next story starts here.'}</h3><p>${state.opportunities.length ? 'Try another search or include archived opportunities.' : 'Add a topic and the audience you want to reach. You can develop the evidence as you go.'}</p><button class="primary" data-action="new">＋ New opportunity</button></div>`;
    return;
  }
  const filteredIdeas = state.ideas.filter(i => {
    const parent = opportunityMap.get(i.opportunity_id);
    return parent && (matches(i) || matches(parent));
  });
  $('#workspace').innerHTML = `<div class="board">${Object.keys(labels).map(stage => {
    const records = stage === 'research' ? shown : filteredIdeas.filter(i => i.stage === stage);
    const emptyTitles = {research:'Find your first signal', idea:'Explore a fresh angle', writing:'Give the idea a story', script_ready:'Make the brief complete'};
    const emptyDescriptions = {research:'Add a game, audience or emerging topic.', idea:'Open an opportunity to add an idea.', writing:'Move a script to Writing as you develop it.', script_ready:'Hook, payoff, script and storyboard go here.'};
    return `<section class="column ${stage}" aria-label="${labels[stage]}"><div class="column-heading"><span class="stage-dot"></span>${labels[stage]}<span class="count">${records.length}</span></div>${records.length ? records.map(r => stage === 'research' ? opportunityCard(r) : ideaCard(r, opportunityMap.get(r.opportunity_id))).join('') : `<div class="column-empty"><div class="empty-dash"><span class="empty-icon">${stage === 'research' ? '⌕' : '＋'}</span><strong>${emptyTitles[stage]}</strong>${emptyDescriptions[stage]}</div></div>`}${stage === 'research' ? '<button class="column-add" data-action="new">＋ Add opportunity</button>' : ''}</section>`;
  }).join('')}</div>`;
}
function opportunityCard(o) {
  const count = state.ideas.filter(i => i.opportunity_id === o.id).length;
  return `<button class="card" data-action="opportunity" data-id="${esc(o.id)}"><span class="card-label">${esc(o.niche)}</span><h3>${esc(o.topic)}</h3><p>${esc(o.hypothesis || 'No hypothesis yet. Add an angle to explore.')}</p><div class="card-footer"><span>${o.archived ? 'Archived' : o.evidence_notes ? 'Manual evidence' : 'Hypothesis only'}</span><span>${count} ${count === 1 ? 'idea' : 'ideas'} ↗</span></div></button>`;
}
function ideaCard(i, parent) {
  return `<button class="card" data-action="idea" data-id="${esc(i.id)}"><span class="card-label">${esc(parent?.topic || 'Idea')}</span><h3>${esc(i.title)}</h3><p>${esc(i.hook || 'Add a hook that earns the opening seconds.')}</p><div class="card-footer"><span>Manual script</span><span>v${i.revision} ↗</span></div></button>`;
}
async function load() {
  $('#refresh').disabled = true;
  try {
    Object.assign(state, await api('/api/workspace'), {loaded: true});
    $('#load-error').hidden = true; draw();
  } catch (error) {
    $('#load-error').textContent = `${error.message}. Workspace could not refresh. Start the local server and use Refresh to retry.${state.loaded ? ' Displaying the last loaded records.' : ''}`;
    $('#load-error').hidden = false;
  } finally { $('#refresh').disabled = false; }
}
function fill(form, record) {
  form.reset();
  for (const element of form.elements) {
    if (!element.name) continue;
    if (element.type === 'checkbox') element.checked = Boolean(record?.[element.name]);
    else if (element.name === 'observed_at') element.value = inputDate(record?.observed_at);
    else element.value = record?.[element.name] ?? (element.name === 'stage' ? 'idea' : '');
  }
  $('.form-error', form).hidden = true;
}
function changed(dialog, yes) {
  dirty.set(dialog, yes);
  const target = dialog === 'opportunity-dialog' ? $('#opportunity-save-state') : $('#idea-save-state');
  if (yes) target.textContent = 'Unsaved changes';
}
function show(dialog) { if (!$(dialog).open) $(dialog).showModal(); }
function closeDialog(id) {
  if (saving.has(id)) return toast('Saving your work. Please wait a moment.');
  if (dirty.get(id) && !confirm('Discard unsaved changes? Your last saved version will stay intact.')) return;
  $('#' + id).close(); dirty.set(id, false);
}
function openOpportunity(id = null) {
  parentId = id;
  const opportunity = state.opportunities.find(o => o.id === id);
  fill($('#opportunity-form'), opportunity);
  $('#opportunity-heading').textContent = opportunity?.topic || 'New opportunity';
  $('#opportunity-save-state').textContent = opportunity ? `Saved ${dateLabel(opportunity.updated_at)} · v${opportunity.revision}` : 'Not saved yet';
  changed('opportunity-dialog', false);
  drawIdeas(); show('#opportunity-dialog');
}
function drawIdeas() {
  const parent = state.opportunities.find(o => o.id === parentId);
  $('#add-idea').disabled = !parent || parent.archived;
  $('#export-brief').disabled = !parent;
  const ideas = state.ideas.filter(i => i.opportunity_id === parentId);
  $('#idea-list').innerHTML = ideas.length ? ideas.map(i => ideaCard(i, parent)).join('') : `<div class="idea-empty">${!parent ? 'Save this opportunity first. Then give it a few original angles.' : parent.archived ? 'This opportunity is archived. Unarchive it to add ideas.' : 'No ideas yet. Start with a specific promise and a satisfying payoff.'}</div>`;
}
async function openIdea(id = null) {
  if (dirty.get('opportunity-dialog')) { toast('Save opportunity edits before opening a script.'); return; }
  const idea = state.ideas.find(i => i.id === id);
  if (idea) parentId = idea.opportunity_id;
  ideaId = id;
  fill($('#idea-form'), idea);
  $('#idea-heading').textContent = idea?.title || 'Develop your idea';
  $('#idea-save-state').textContent = idea ? `Saved · version ${idea.revision}` : 'Not saved yet';
  changed('idea-dialog', false);
  $('#version-history').replaceChildren();
  show('#idea-dialog');
  if (id) await loadVersions(id);
}
async function loadVersions(id) {
  try {
    const versions = await api(`/api/ideas/${id}/versions`);
    if (ideaId !== id) return;
    $('#version-history').innerHTML = `<h3>Saved versions (${versions.length})</h3>${versions.map(v => `<details><summary>Version ${v.revision} · ${esc(dateLabel(v.updated_at))} · ${labels[v.stage]}</summary><div class="version-body"><strong>${esc(v.title)}</strong><br><br>HOOK\n${esc(v.hook)}\n\nPAYOFF\n${esc(v.payoff)}\n\nSCRIPT\n${esc(v.script)}\n\nSTORYBOARD\n${esc(v.storyboard)}\n\nAUDIO\n${esc(v.audio_notes)}</div></details>`).join('')}`;
  } catch (error) { $('#version-history').textContent = `Version history unavailable: ${error.message}`; }
}
async function saveForm(event, kind) {
  event.preventDefault();
  const form = event.target;
  const submit = $('button[type=submit]', form);
  if (submit.disabled) return;
  const errorBox = $('.form-error', form);
  const fields = Object.fromEntries(new FormData(form));
  const isOpportunity = kind === 'opportunity';
  let current, path, id;
  if (isOpportunity) {
    id = parentId;
    current = state.opportunities.find(o => o.id === id);
    fields.archived = form.elements.archived.checked;
    fields.source_url = fields.source_url.trim() || null;
    fields.observed_at = fields.observed_at ? new Date(fields.observed_at).toISOString() : null;
    path = id ? `/api/opportunities/${id}` : '/api/opportunities';
  } else {
    id = ideaId;
    current = state.ideas.find(i => i.id === id);
    path = id ? `/api/ideas/${id}` : `/api/opportunities/${parentId}/ideas`;
  }
  if (current) fields.expected_revision = current.revision;
  const dialogId = isOpportunity ? 'opportunity-dialog' : 'idea-dialog';
  saving.add(dialogId);
  const controls = [...form.elements];
  controls.forEach(control => { control.disabled = true; });
  const buttonLabel = submit.textContent; submit.textContent = 'Saving…';
  errorBox.hidden = true;
  try {
    const record = await api(path, {method: id ? 'PUT' : 'POST', body: JSON.stringify(fields)});
    const collection = isOpportunity ? 'opportunities' : 'ideas';
    state[collection] = [record, ...state[collection].filter(i => i.id !== record.id)];
    if (isOpportunity) {
      parentId = record.id;
      $('#opportunity-heading').textContent = record.topic;
      $('#opportunity-save-state').textContent = `Saved ${dateLabel(record.updated_at)} · v${record.revision}`;
    } else {
      ideaId = record.id;
      $('#idea-heading').textContent = record.title;
      $('#idea-save-state').textContent = `Saved · version ${record.revision}`;
      await loadVersions(record.id);
    }
    changed(isOpportunity ? 'opportunity-dialog' : 'idea-dialog', false);
    draw(); drawIdeas(); toast(isOpportunity ? 'Opportunity saved locally' : `Script saved · version ${record.revision}`);
  } catch (error) { errorBox.textContent = error.message; errorBox.hidden = false; }
  finally {
    controls.forEach(control => { control.disabled = false; });
    submit.textContent = buttonLabel; saving.delete(dialogId);
  }
}
function info(type) {
  $('#info-heading').textContent = type === 'connections' ? 'Your connections' : 'From signal to story';
  const sections = type === 'connections' ? [
    ['Local workspace · active', 'Opportunities, manual evidence and script versions are stored in SQLite on this computer.'],
    ['Discovery · not connected', 'No live trend data is being collected. Add reference links and dated observations manually for now.'],
    ['AI scripts · not connected', 'The script studio supports manual writing. A configurable generation provider comes in a later milestone.'],
    ['Production · developer CLI only', 'The existing renderer is not connected to this dashboard yet. There are no background render jobs.'],
    ['YouTube & analytics · not connected', 'This dashboard cannot upload, schedule, publish or read channel analytics. No account access is required.'],
  ] : [
    ['01 / Find the opportunity', 'Define a topic and the viewer you want to reach. Keep your hypothesis separate from observed evidence.'],
    ['02 / Develop the angle', 'Save dated source notes, then explore multiple original concepts. A big game alone is not a niche.'],
    ['03 / Write the brief', 'Give each idea a hook, payoff, script, storyboard and purposeful audio cues. Every save keeps a new version.'],
    ['04 / Hand off to production', 'Export your saved brief as JSON. Production, licensed sound selection and publishing are the next milestones. “Script ready” is an editorial label, not publication approval.'],
  ];
  $('#info-content').innerHTML = sections.map(([title, text]) => `<section><h3>${title}</h3><div>${text}</div></section>`).join('');
  show('#info-dialog');
}
$('#new-opportunity').addEventListener('click', () => openOpportunity());
$('#refresh').addEventListener('click', load);
$('#search').addEventListener('input', draw);
$('#show-archived').addEventListener('change', draw);
$('#connections-open').addEventListener('click', () => info('connections'));
$('#workflow-open').addEventListener('click', () => info('workflow'));
$('#add-idea').addEventListener('click', () => openIdea());
$('#opportunity-form').addEventListener('submit', event => saveForm(event, 'opportunity'));
$('#idea-form').addEventListener('submit', event => saveForm(event, 'idea'));
for (const [formId, dialogId] of [['opportunity-form', 'opportunity-dialog'], ['idea-form', 'idea-dialog']]) {
  $('#' + formId).addEventListener('input', () => changed(dialogId, true));
}
for (const dialog of document.querySelectorAll('dialog')) {
  dialog.addEventListener('cancel', event => {event.preventDefault(); closeDialog(dialog.id);});
}
document.addEventListener('click', event => {
  const close = event.target.closest('[data-close]');
  if (close) return closeDialog(close.dataset.close);
  const nav = event.target.closest('[data-view]');
  if (nav) {
    state.view = nav.dataset.view;
    document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', b === nav));
    draw(); return;
  }
  const button = event.target.closest('[data-action]');
  if (!button) return;
  if (button.dataset.action === 'new') openOpportunity();
  if (button.dataset.action === 'opportunity') openOpportunity(button.dataset.id);
  if (button.dataset.action === 'idea') openIdea(button.dataset.id);
});
$('#export-brief').addEventListener('click', async () => {
  if (dirty.get('opportunity-dialog')) return toast('Save your opportunity before exporting.');
  const button = $('#export-brief'); button.disabled = true;
  try {
    const record = await api(`/api/opportunities/${parentId}/export`);
    const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], {type:'application/json'}));
    const link = document.createElement('a'); link.href = url; link.download = 'production-brief.json';
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast('Production brief exported');
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; }
});
window.addEventListener('beforeunload', event => {
  if ([...dirty.values()].some(Boolean)) {event.preventDefault(); event.returnValue = '';}
});
load();
