from __future__ import annotations

import html
import json

from local_ai_bridge.web.page_assets import PAGE_SCRIPT, PAGE_STYLE


def render_manifest(version: str) -> str:
    return json.dumps(
        {
            "name": f"BridgAI Web {version}",
            "short_name": "BridgAI",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0b1220",
            "theme_color": "#2563eb",
            "description": "Assistente mobile semplice per workspace BridgAI.",
        },
        ensure_ascii=False,
    )


def _step(number: str, title: str, description: str, body: str) -> str:
    return f"""
<section class="card">
  <div class="step-head"><span class="step-number">{number}</span><div><h2>{title}</h2><p>{description}</p></div></div>
  {body}
</section>"""


def render_index(
    csrf_token: str,
    version: str,
    *,
    connection_address: str | None = None,
) -> str:
    task_step = _step(
        "1",
        "Descrivi la richiesta",
        "Scrivi con parole semplici cosa vuoi creare, correggere o migliorare.",
        """
<label for="task">Cosa vuoi ottenere?</label>
<textarea id="task" placeholder="Ad esempio: rendi più semplice la schermata iniziale e usa pulsanti più chiari..."></textarea>
<div class="actions"><button onclick="generateReport()">Prepara richiesta per l’AI</button></div>
<div class="provider-actions">
  <button data-provider disabled onclick="openProvider('https://chatgpt.com/')">Continua su ChatGPT</button>
  <button data-provider disabled onclick="openProvider('https://claude.ai/new')">Continua su Claude</button>
  <button data-provider disabled onclick="openProvider('https://gemini.google.com/')">Continua su Gemini</button>
</div>
<div id="reportResult" class="feedback"></div>
<details id="reportDetails"><summary>Mostra o copia la richiesta preparata</summary><div class="details-body">
  <textarea id="report" readonly placeholder="La richiesta preparata apparirà qui."></textarea>
  <div class="actions"><button class="secondary" onclick="copyReport()">Copia richiesta</button></div>
</div></details>
""",
    )
    export_step = _step(
        "2",
        "Incolla la risposta dell’AI",
        "Quando l’AI richiede file con #scarica, incolla qui tutto il messaggio.",
        """
<label for="downloadRequest">Risposta ricevuta</label>
<textarea id="downloadRequest" placeholder="Incolla qui la risposta completa che contiene #scarica..."></textarea>
<div class="actions">
  <button class="secondary" onclick="pasteInto('downloadRequest','exportResult')">Incolla</button>
  <button onclick="exportFiles()">Prepara i file richiesti</button>
</div>
<div id="exportResult" class="feedback"></div>
""",
    )
    update_step = _step(
        "3",
        "Controlla e applica l’aggiornamento",
        "Carica lo ZIP restituito dall’AI. Nessun file viene scritto prima della tua conferma.",
        """
<label for="zipFile">ZIP dell’aggiornamento</label>
<input id="zipFile" type="file" accept=".zip,application/zip">
<div class="actions"><button onclick="uploadZip()">Analizza ZIP</button></div>
<div class="separator">oppure</div>
<details class="compact"><summary>Hai ricevuto testo SEARCH/REPLACE?</summary><div class="details-body">
  <textarea id="patchText" placeholder="FILE: src/...&#10;&lt;&lt;&lt;&lt;&lt;&lt;&lt; SEARCH&#10;...&#10;=======&#10;...&#10;&gt;&gt;&gt;&gt;&gt;&gt;&gt; REPLACE"></textarea>
  <div class="actions"><button class="secondary" onclick="pasteInto('patchText','planSummary')">Incolla</button><button onclick="inspectPatch()">Analizza testo</button></div>
</div></details>
<div id="planSummary" class="feedback"></div>
<div id="preview" class="preview">
  <h3>Anteprima modifiche</h3><ul id="changeList" class="change-list"></ul>
  <details><summary>Mostra diff completo</summary><pre id="diff"></pre></details>
  <div class="actions"><button id="applyButton" class="success" onclick="applyPlan()" disabled>Applica aggiornamento</button></div>
  <div id="applyResult" class="feedback"></div>
</div>
""",
    )
    displayed_address = html.escape(connection_address or "indirizzo in rilevamento…")
    safe_version = html.escape(version)
    script = PAGE_SCRIPT.replace("__CSRF__", json.dumps(csrf_token))
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#2563eb"><link rel="manifest" href="/manifest.webmanifest"><title>BridgAI Web {safe_version}</title><style>{PAGE_STYLE}</style></head>
<body>
<header><div class="header-row"><div class="brand"><strong>BridgAI Web</strong><small class="connection-line">Collegati a <strong id="connectionAddress">{displayed_address}</strong></small></div><div class="header-meta"><span id="currentProject" class="project-name">Nessun progetto aperto</span><span id="modeBadge" class="badge">Connessione…</span></div></div></header>
<div id="busy"><div>Operazione in corso…</div></div>
<main>
<section id="authCard" class="card"><h2>Accesso</h2><p class="muted">Inserisci le credenziali configurate in BridgAI.</p><div class="grid"><div><label for="authUsername">Username</label><input id="authUsername" autocomplete="username"></div><div><label for="authPassword">Password</label><input id="authPassword" type="password" autocomplete="current-password"></div></div><div class="actions"><button onclick="login()">Accedi</button><button class="secondary" onclick="logout()">Disconnetti</button></div><div id="authResult" class="feedback"></div></section>
<div id="appContent">
<section class="card"><div class="status-strip"><div><span class="muted">Progetto corrente</span><div id="workspacePath" class="project-name">Nessun workspace selezionato</div></div></div>
<details id="projectTools"><summary>Scegli o gestisci progetto</summary><div class="details-body"><label for="workspaceRoot">Cartella root progetti</label><input id="workspaceRoot" readonly placeholder="Non configurata nel programma BridgAI"><p id="rootHelp" class="muted">Configura la root nelle Impostazioni del programma BridgAI e riavvia la Web UI.</p><div id="workspacePicker"></div><div class="actions"><button id="openWorkspaceButton" onclick="setWorkspace()">Apri progetto</button><button class="secondary" onclick="refreshStatus()">Aggiorna elenco</button></div>
<div id="projectManagement"><div class="grid"><div><h3>Nuovo progetto</h3><label for="newProjectName">Nome cartella</label><input id="newProjectName" placeholder="mio-progetto"><label class="inline-check"><input id="initializeGit" type="checkbox" checked> Inizializza Git</label><div class="actions"><button class="success" onclick="createProject()">Crea e apri</button></div></div><div><h3>Clona da Git</h3><label for="cloneRepository">URL repository</label><input id="cloneRepository" placeholder="https://github.com/owner/repository.git"><label for="cloneProjectName">Nome cartella opzionale</label><input id="cloneProjectName"><div class="actions"><button class="success" onclick="cloneProject()">Clona e apri</button></div></div></div></div><div id="projectResult" class="feedback"></div></div></details></section>
<section class="hero"><h1>Cosa vuoi fare oggi?</h1><p>Segui i tre passaggi. Le funzioni tecniche restano disponibili, ma non intralciano il flusso principale.</p></section>
{task_step}{export_step}{update_step}
<section class="card advanced-card"><details id="verificationTools"><summary>Verifica e strumenti avanzati</summary><div class="details-body"><p class="muted">Usa questi comandi dopo l’applicazione o per la manutenzione del progetto.</p><div class="actions"><button class="success" onclick="runTool('/api/tests','Test completati')">Esegui test</button><button class="secondary" onclick="runTool('/api/git/status','Git status completato')">Git status</button><button class="secondary" onclick="runTool('/api/git/diff','Git diff completato')">Git diff</button><button class="danger" onclick="rollback()">Rollback ultimo batch</button><button class="danger" onclick="restartProgram()">Riavvia BridgAI</button></div><div id="toolResult" class="feedback"></div></div></details></section>
</div></main><script>{script}</script></body></html>"""
