from __future__ import annotations

import html
import json


def render_manifest(version: str) -> str:
    return json.dumps(
        {
            "name": f"BridgAI Web {version}",
            "short_name": "BridgAI",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0b1220",
            "theme_color": "#2563eb",
            "description": "Pannello mobile-first per gestire workspace BridgAI remoti.",
        },
        ensure_ascii=False,
    )


def render_index(
    csrf_token: str,
    version: str,
    *,
    connection_address: str | None = None,
) -> str:
    page = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#2563eb">
<link rel="manifest" href="/manifest.webmanifest">
<title>BridgAI Web __VERSION__</title>
<style>
:root { color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
* { box-sizing: border-box; }
body { margin:0; background:#0b1220; color:#e5e7eb; }
header { position:sticky; top:0; z-index:10; padding:calc(.75rem + env(safe-area-inset-top)) 1rem .75rem;
  background:rgba(15,23,42,.96); border-bottom:1px solid #263449; backdrop-filter:blur(12px); }
header .row { max-width:980px; margin:auto; display:flex; align-items:center; justify-content:space-between; gap:.75rem; }
header strong { font-size:1.05rem; }
header small { display:block; color:#94a3b8; margin-top:.15rem; }
main { max-width:980px; margin:auto; padding:1rem 1rem calc(2rem + env(safe-area-inset-bottom)); display:grid; gap:.9rem; }
.card { background:#111c2f; border:1px solid #263449; border-radius:1rem; padding:1rem; box-shadow:0 12px 30px rgba(0,0,0,.16); }
.card h2 { font-size:1.05rem; margin:0 0 .75rem; }
.card h3 { font-size:.98rem; margin:1rem 0 .35rem; }
.grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.65rem; }
label { display:block; margin:.65rem 0 .3rem; font-size:.9rem; font-weight:700; color:#cbd5e1; }
input, select, textarea, button { width:100%; border-radius:.7rem; border:1px solid #334155; padding:.78rem; font:inherit; }
input, select, textarea { background:#0b1220; color:#e5e7eb; }
input:disabled, select:disabled { opacity:.7; }
textarea { min-height:10rem; resize:vertical; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; line-height:1.45; }
button { border:0; background:#2563eb; color:white; font-weight:800; cursor:pointer; min-height:2.8rem; }
button.secondary { background:#334155; } button.danger { background:#b91c1c; } button.success { background:#047857; }
button:disabled { opacity:.5; cursor:not-allowed; }
.actions { display:grid; grid-template-columns:repeat(auto-fit,minmax(145px,1fr)); gap:.55rem; margin-top:.65rem; }
.inline-check { display:flex; align-items:center; gap:.55rem; margin-top:.75rem; color:#cbd5e1; font-weight:700; }
.inline-check input { width:auto; min-width:1.1rem; height:1.1rem; margin:0; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; background:#07101f; border:1px solid #263449; padding:.8rem; border-radius:.7rem; max-height:30rem; overflow:auto; margin:.7rem 0 0; }
.muted { color:#94a3b8; font-size:.88rem; } .ok { color:#86efac; } .error { color:#fca5a5; }
.badge { display:inline-block; padding:.2rem .5rem; border-radius:999px; background:#1e3a5f; color:#bfdbfe; font-size:.75rem; }
.connection-line { display:block; margin-top:.18rem; color:#94a3b8; }
.connection-line strong { color:#dbeafe; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }
.divider { border:0; border-top:1px solid #263449; margin:1rem 0; }
#authCard { display:none; }
#appContent { display:none; }
#busy { position:fixed; inset:0; display:none; place-items:center; background:rgba(2,6,23,.72); z-index:30; }
#busy div { background:#111c2f; border:1px solid #334155; border-radius:1rem; padding:1rem 1.4rem; font-weight:800; }
@media (max-width:640px) { .grid { grid-template-columns:1fr; } main { padding-inline:.7rem; } .card { border-radius:.85rem; padding:.85rem; } }
</style>
</head>
<body>
<header><div class="row"><div><strong>BridgAI Web</strong><small>Server workspace control · __VERSION__</small><small class="connection-line">Collegati a <strong id="connectionAddress">__CONNECTION_ADDRESS__</strong></small></div><div style="display:flex;align-items:center;gap:.55rem;"><span id="modeBadge" class="badge">Connessione…</span><button id="restartBtn" class="danger" style="display:none;padding:.2rem .6rem;min-height:unset;width:auto;font-size:.78rem;" onclick="restartProgram()">Riavvia</button></div></div></header>
<div id="busy"><div>Operazione in corso…</div></div>
<main>
<section id="authCard" class="card">
<h2>Accesso</h2>
<p class="muted">Inserisci le credenziali configurate nel programma BridgAI. Rimangono soltanto nella sessione di questo browser.</p>
<div class="grid"><div><label for="authUsername">Username</label><input id="authUsername" autocomplete="username"></div><div><label for="authPassword">Password</label><input id="authPassword" type="password" autocomplete="current-password"></div></div>
<div class="actions"><button onclick="login()">Accedi</button><button class="secondary" onclick="logout()">Disconnetti</button></div>
<pre id="authResult"></pre>
</section>

<div id="appContent">
<section class="card">
<h2>1. Progetti sul server</h2>
<label for="workspaceRoot">Cartella root progetti</label>
<input id="workspaceRoot" readonly placeholder="Non configurata nel programma BridgAI">
<p id="rootHelp" class="muted">La root viene configurata nelle Impostazioni del programma BridgAI.</p>
<div class="actions"><button class="secondary" onclick="refreshStatus()">Aggiorna elenco</button></div>

<hr class="divider">
<div id="workspacePicker"></div>
<div class="actions"><button onclick="setWorkspace()">Apri progetto</button></div>

<div id="projectManagement">
<hr class="divider">
<div class="grid">
<div>
<h3>Nuovo progetto</h3>
<label for="newProjectName">Nome cartella</label><input id="newProjectName" placeholder="mio-progetto" autocomplete="off">
<label class="inline-check"><input id="initializeGit" type="checkbox" checked> Inizializza repository Git</label>
<div class="actions"><button class="success" onclick="createProject()">Crea e apri</button></div>
</div>
<div>
<h3>Clona da Git</h3>
<label for="cloneRepository">URL repository</label><input id="cloneRepository" placeholder="https://github.com/owner/repository.git" autocomplete="off">
<label for="cloneProjectName">Nome cartella opzionale</label><input id="cloneProjectName" placeholder="Ricavato automaticamente dall’URL" autocomplete="off">
<p class="muted">Usa HTTPS o SSH. Credenziali e chiavi restano nella configurazione Git del server.</p>
<div class="actions"><button class="success" onclick="cloneProject()">Clona e apri</button></div>
</div>
</div>
</div>
<pre id="projectResult">Caricamento…</pre>
</section>

<section class="card">
<h2>2. Prepara la richiesta per ChatGPT</h2>
<label for="task">Task</label><textarea id="task" placeholder="Descrivi la modifica o il problema da affidare all’AI…"></textarea>
<div class="actions"><button onclick="generateReport()">Genera Super-Report</button><button class="secondary" onclick="copyText('report')">Copia report</button></div>
<label for="report">Report</label><textarea id="report" readonly placeholder="Il report apparirà qui."></textarea>
</section>

<section class="card">
<h2>3. Esporta i file richiesti</h2>
<p class="muted">Incolla la risposta contenente la riga <code>#scarica</code>. Lo ZIP verrà scaricato direttamente sul telefono.</p>
<label for="downloadRequest">Risposta AI</label><textarea id="downloadRequest" placeholder="#scarica src/app.py, tests/test_app.py"></textarea>
<div class="actions"><button onclick="exportFiles()">Crea e scarica ZIP</button></div>
<pre id="exportResult"></pre>
</section>

<section class="card">
<h2>4. Analizza la modifica restituita</h2>
<div class="grid">
<div>
<label for="zipFile">ZIP restituito dall’AI</label><input id="zipFile" type="file" accept=".zip,application/zip">
<div class="actions"><button onclick="uploadZip()">Carica e analizza ZIP</button></div>
</div>
<div>
<label for="patchText">Oppure risposta SEARCH/REPLACE</label><textarea id="patchText" placeholder="FILE: src/...\n<<<<<<< SEARCH\n...\n=======\n...\n>>>>>>> REPLACE"></textarea>
<div class="actions"><button onclick="inspectPatch()">Analizza patch</button></div>
</div>
</div>
<pre id="planSummary">Nessun piano analizzato.</pre>
<label for="diff">Diff</label><textarea id="diff" readonly></textarea>
<div class="actions"><button id="applyButton" class="danger" onclick="applyPlan()" disabled>Applica piano</button><button class="secondary" onclick="rollback()">Rollback ultimo batch</button></div>
<pre id="applyResult"></pre>
</section>

<section class="card">
<h2>5. Verifica</h2>
<div class="actions"><button class="success" onclick="runTests()">Esegui test rilevati</button><button class="secondary" onclick="gitStatus()">Git status</button><button class="secondary" onclick="gitDiff()">Git diff</button></div>
<pre id="toolResult"></pre>
</section>
</div>
</main>
<script>
const csrf = __CSRF__;
let currentPlanId = null;
let lastStatus = null;
const authKey = 'bridgai-web-basic-auth';

function authorization() { return sessionStorage.getItem(authKey) || ''; }
function headers(extra) {
  const value = {...(extra || {})};
  if (authorization()) value['Authorization'] = authorization();
  return value;
}
function setBusy(value) { document.getElementById('busy').style.display = value ? 'grid' : 'none'; }
function show(id, value, isError=false) {
  const element = document.getElementById(id);
  element.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  element.className = isError ? 'error' : '';
}
async function jsonResponse(response) {
  const data = await response.json().catch(() => ({error:'Risposta server non valida'}));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
async function api(path, body) {
  const response = await fetch(path, {
    method:'POST',
    headers:headers({'Content-Type':'application/json','X-Local-Bridge-CSRF':csrf}),
    body:JSON.stringify(body || {}),
  });
  return jsonResponse(response);
}
async function withBusy(action, errorTarget) {
  setBusy(true);
  try { return await action(); }
  catch (error) { show(errorTarget, error.message, true); throw error; }
  finally { setBusy(false); }
}
function login() {
  const username = document.getElementById('authUsername').value.trim();
  const password = document.getElementById('authPassword').value;
  if (!username || !password) { show('authResult', 'Inserisci username e password.', true); return; }
  sessionStorage.setItem(authKey, 'Basic ' + btoa(unescape(encodeURIComponent(username + ':' + password))));
  document.getElementById('authPassword').value = '';
  refreshStatus();
}
function logout() { sessionStorage.removeItem(authKey); lastStatus=null; currentPlanId=null; refreshStatus(); }
function renderConnection(status) {
  const address = status.connection_address || window.location.host;
  document.getElementById('connectionAddress').textContent = address;
}
function renderWorkspacePicker(status) {
  const host = document.getElementById('workspacePicker');
  const items = status.workspaces || [];
  if (status.workspace_root || status.fixed_workspace) {
    host.innerHTML = '<label for="workspace">Progetto</label><select id="workspace"></select>';
    const select = document.getElementById('workspace');
    const placeholder = document.createElement('option');
    placeholder.value = ''; placeholder.textContent = items.length ? 'Seleziona un progetto…' : 'Nessun progetto disponibile';
    select.appendChild(placeholder);
    items.forEach(item => {
      const option = document.createElement('option'); option.value=item.value;
      option.textContent=item.name + (item.git ? ' · Git' : '');
      if (item.value === status.workspace) option.selected=true;
      select.appendChild(option);
    });
  } else {
    host.innerHTML = '<p class="muted">Configura prima la cartella root dei progetti nelle Impostazioni del programma BridgAI, quindi riavvia l’interfaccia web.</p>';
  }
}
function renderProjectSettings(status) {
  const rootInput = document.getElementById('workspaceRoot');
  rootInput.value = status.workspace_root || '';
  document.getElementById('projectManagement').style.display = status.can_manage_projects ? 'block' : 'none';
  if (status.fixed_workspace) {
    document.getElementById('rootHelp').textContent = 'Il server è limitato a un workspace fisso configurato all’avvio.';
  } else if (status.workspace_root) {
    document.getElementById('rootHelp').textContent = 'Root configurata nel programma BridgAI. Ogni cartella diretta viene proposta come progetto.';
  } else {
    document.getElementById('rootHelp').textContent = 'Configura la root nelle Impostazioni del programma BridgAI e riavvia la Web UI.';
  }
}
async function refreshStatus() {
  try {
    const response = await fetch('/api/status', {headers:headers()});
    const status = await jsonResponse(response);
    lastStatus = status;
    document.getElementById('authCard').style.display = 'none';
    document.getElementById('appContent').style.display = 'block';
    document.getElementById('restartBtn').style.display = 'inline-block';
    document.getElementById('modeBadge').textContent = status.remote_mode ? 'Remoto protetto' : 'Locale';
    renderConnection(status);
    renderProjectSettings(status);
    renderWorkspacePicker(status);
    show('projectResult', {
      workspace:status.workspace,
      workspace_root:status.workspace_root,
      projects:(status.workspaces || []).map(item => item.name),
      pending_plan:status.pending_plan,
    });
    show('authResult', 'Accesso riuscito.');
  } catch(error) {
    document.getElementById('authCard').style.display = 'block';
    document.getElementById('appContent').style.display = 'none';
    document.getElementById('restartBtn').style.display = 'none';
    document.getElementById('modeBadge').textContent = 'Accesso richiesto';
    show('authResult', error.message, true); show('projectResult', error.message, true);
  }
}
async function restartProgram() {
  if (!confirm("Sei sicuro di voler riavviare il programma?")) return;
  await withBusy(async () => {
    const data = await api('/api/restart', {});
    alert("Richiesta di riavvio inviata. La pagina si ricaricherà tra pochi secondi.");
    setTimeout(() => {
      window.location.reload();
    }, 4000);
  }, 'projectResult').catch(() => {});
}
async function setWorkspace() { await withBusy(async()=>{
  const selector=document.getElementById('workspace');
  if(!selector) throw new Error('Configura prima la cartella root dei progetti nel programma BridgAI.');
  const value=selector.value; if(!value) throw new Error('Seleziona un progetto.');
  const data=await api('/api/workspace',{path:value});
  show('projectResult',data); currentPlanId=null; document.getElementById('applyButton').disabled=true; await refreshStatus();
},'projectResult').catch(()=>{}); }
async function createProject() {
  const name=document.getElementById('newProjectName').value.trim();
  if(!confirm(`Creare il progetto “${name}” nella root configurata?`)) return;
  await withBusy(async()=>{
    const data=await api('/api/projects/create',{name,initialize_git:document.getElementById('initializeGit').checked,confirm:'CREATE'});
    document.getElementById('newProjectName').value=''; show('projectResult',data); await refreshStatus();
  },'projectResult').catch(()=>{});
}
async function cloneProject() {
  const repository=document.getElementById('cloneRepository').value.trim();
  const name=document.getElementById('cloneProjectName').value.trim();
  if(!confirm(`Clonare questo repository nella root progetti?\n${repository}`)) return;
  await withBusy(async()=>{
    const data=await api('/api/projects/clone',{repository,name,confirm:'CLONE'});
    document.getElementById('cloneRepository').value=''; document.getElementById('cloneProjectName').value='';
    show('projectResult',data); await refreshStatus();
  },'projectResult').catch(()=>{});
}
async function generateReport() { await withBusy(async()=>{
  const data=await api('/api/report',{task:document.getElementById('task').value}); document.getElementById('report').value=data.report;
},'report').catch(()=>{}); }
async function copyText(id) {
  const value=document.getElementById(id).value; if(!value) return;
  try { await navigator.clipboard.writeText(value); } catch(_) { document.getElementById(id).select(); document.execCommand('copy'); }
}
async function downloadArtifact(id, filename) {
  const response=await fetch('/api/artifacts/'+encodeURIComponent(id),{headers:headers()});
  if(!response.ok) throw new Error((await response.json()).error || 'Download fallito');
  const blob=await response.blob(); const url=URL.createObjectURL(blob); const link=document.createElement('a');
  link.href=url; link.download=filename || 'download.bin'; document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
}
async function exportFiles() { await withBusy(async()=>{
  const data=await api('/api/export',{text:document.getElementById('downloadRequest').value}); show('exportResult',data.files); await downloadArtifact(data.artifact_id,data.filename);
},'exportResult').catch(()=>{}); }
function showPlan(data) {
  currentPlanId=data.plan_id; document.getElementById('applyButton').disabled=false; document.getElementById('diff').value=data.diff || '';
  show('planSummary',{type:data.plan_type, changes:data.changes, warnings:data.warnings, commit_message:data.commit_message});
}
async function uploadZip() { await withBusy(async()=>{
  const file=document.getElementById('zipFile').files[0]; if(!file) throw new Error('Seleziona uno ZIP.');
  const response=await fetch('/api/zip/upload',{method:'POST',headers:headers({'Content-Type':'application/zip','X-File-Name':encodeURIComponent(file.name),'X-Local-Bridge-CSRF':csrf}),body:await file.arrayBuffer()});
  showPlan(await jsonResponse(response));
},'planSummary').catch(()=>{}); }
async function inspectPatch() { await withBusy(async()=>showPlan(await api('/api/patch/inspect',{text:document.getElementById('patchText').value})),'planSummary').catch(()=>{}); }
async function applyPlan() {
  if(!currentPlanId || !confirm('Applicare davvero il piano mostrato al workspace?')) return;
  await withBusy(async()=>{ const data=await api('/api/plan/apply',{plan_id:currentPlanId,confirm:'APPLY'}); show('applyResult',data); currentPlanId=null; document.getElementById('applyButton').disabled=true; },'applyResult').catch(()=>{});
}
async function rollback() {
  if(!confirm('Ripristinare l’ultimo batch applicato?')) return;
  await withBusy(async()=>show('applyResult',await api('/api/rollback',{confirm:'ROLLBACK'})),'applyResult').catch(()=>{});
}
async function runTests() { await withBusy(async()=>{ const data=await api('/api/tests',{}); show('toolResult',data.output); },'toolResult').catch(()=>{}); }
async function gitStatus() { await withBusy(async()=>{ const data=await api('/api/git/status',{}); show('toolResult',data.output); },'toolResult').catch(()=>{}); }
async function gitDiff() { await withBusy(async()=>{ const data=await api('/api/git/diff',{}); show('toolResult',data.output); },'toolResult').catch(()=>{}); }
refreshStatus();
</script>
</body></html>"""
    displayed_address = connection_address or "indirizzo in rilevamento…"
    return (
        page.replace("__VERSION__", html.escape(version))
        .replace("__CONNECTION_ADDRESS__", html.escape(displayed_address))
        .replace("__CSRF__", json.dumps(csrf_token))
    )
