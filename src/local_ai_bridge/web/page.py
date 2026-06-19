from __future__ import annotations

import html
import json

from local_ai_bridge.web.page_assets import PAGE_SCRIPT, PAGE_STYLE
from local_ai_bridge.core.prompt_presets import load_prompt_presets


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
            "icons": [{"src": "/favicon.svg", "sizes": "any", "type": "image/svg+xml"}],
        },
        ensure_ascii=False,
    )


def render_favicon_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#5f89ff"/><stop offset="1" stop-color="#3157d9"/></linearGradient></defs>
<rect width="64" height="64" rx="16" fill="url(#g)"/>
<path d="M19 14h17c8 0 13 4 13 10 0 4-2 7-6 9 5 2 8 5 8 10 0 8-6 12-15 12H19V14zm10 9v7h7c3 0 5-1 5-4s-2-3-5-3h-7zm0 15v8h8c4 0 6-1 6-4s-2-4-6-4h-8z" fill="white"/>
</svg>"""


def _step(number: str, title: str, description: str, body: str) -> str:
    return f"""
<section class="card step-card">
  <div class="step-head"><span class="step-number">{number}</span><div><p class="eyebrow">Passaggio {number} di 3</p><h2>{title}</h2><p>{description}</p></div></div>
  {body}
</section>"""


def render_index(
    csrf_token: str,
    version: str,
    *,
    connection_address: str | None = None,
) -> str:
    preset_options = ['<option value="">Nessun preset</option>']
    for preset in load_prompt_presets():
        preset_options.append(
            f'<option value="{html.escape(preset.preset_id)}" title="{html.escape(preset.description)}">'
            f'{html.escape(preset.label)}</option>'
        )
    preset_select = "".join(preset_options)
    task_step = _step(
        "1",
        "Descrivi la richiesta",
        "Scrivi con parole semplici cosa vuoi creare, correggere o migliorare.",
        f"""
<label for="task">Cosa vuoi ottenere?</label>
<div class="task-input-wrap"><textarea id="task" placeholder="Ad esempio: rendi più semplice la schermata iniziale e usa pulsanti più chiari..."></textarea><button id="dictationButton" class="dictation-button" type="button" onclick="toggleDictation()" aria-pressed="false" aria-label="Avvia dettatura vocale" title="Avvia dettatura vocale"><svg class="microphone-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15.5a3.5 3.5 0 0 0 3.5-3.5V6a3.5 3.5 0 1 0-7 0v6a3.5 3.5 0 0 0 3.5 3.5Zm-5-4a1 1 0 0 1 1 1 4 4 0 0 0 8 0 1 1 0 1 1 2 0 6 6 0 0 1-5 5.92V21h2a1 1 0 1 1 0 2H9a1 1 0 1 1 0-2h2v-2.58A6 6 0 0 1 6 12.5a1 1 0 0 1 1-1Z"/></svg><span class="sr-only" id="dictationLabel">Dettatura</span></button></div>
<div id="dictationResult" class="feedback"></div>
<label for="promptPreset">Preset di prompt</label>
<select id="promptPreset">{preset_select}</select>
<p class="field-help">Il preset aggiunge istruzioni alla richiesta senza modificare il testo scritto.</p>
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
  <h3>Checklist pre-applicazione</h3><div id="preApplyChecklist" class="pre-apply-checklist"></div>
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
<meta name="theme-color" content="#07111f"><link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="/favicon.svg"><script>(function(){{try{{var saved=localStorage.getItem('bridgai-web-theme');var system=window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';document.documentElement.dataset.theme=saved==='light'||saved==='dark'?saved:system}}catch(_){{document.documentElement.dataset.theme='dark'}}}})();</script><link rel="manifest" href="/manifest.webmanifest"><title>BridgAI Web {safe_version}</title><style>{PAGE_STYLE}</style></head>
<body>
<header><div class="header-row"><div class="brand"><span class="brand-mark" aria-hidden="true">B</span><div><strong>BridgAI Web</strong><small class="connection-line">Collegati a <strong id="connectionAddress">{displayed_address}</strong></small></div></div><div class="header-meta"><label class="language-control" for="languageSelect"><span class="sr-only">Lingua</span><select id="languageSelect" onchange="changeLanguage(this.value)" aria-label="Lingua interfaccia"><option value="it">IT</option><option value="en">EN</option></select></label><button id="themeToggle" class="theme-toggle" type="button" onclick="toggleTheme()" aria-label="Passa alla modalità chiara" title="Passa alla modalità chiara"><span id="themeIcon" aria-hidden="true">☀</span></button><span id="currentProject" class="project-chip">Nessun progetto aperto</span><span id="modeBadge" class="badge">Connessione…</span></div></div></header>
<div id="busy"><div>Operazione in corso…</div></div>
<main>
<section id="authCard" class="card"><h2>Accesso</h2><p class="muted">Inserisci le credenziali configurate in BridgAI.</p><div class="grid"><div><label for="authUsername">Username</label><input id="authUsername" autocomplete="username"></div><div><label for="authPassword">Password</label><input id="authPassword" type="password" autocomplete="current-password"></div><div id="secondFactorField"><label for="authSecondFactor">Codice 2FA o recupero</label><input id="authSecondFactor" inputmode="text" autocomplete="one-time-code" placeholder="123456 oppure XXXX-XXXX-XXXX"></div></div><p id="twoFactorHint" class="muted"></p><label class="switch-row" for="rememberCredentials"><input id="rememberCredentials" type="checkbox"><span class="switch-track" aria-hidden="true"></span><span>Ricorda l’accesso su questo browser</span></label><p class="muted">La password e il codice 2FA non vengono conservati. Se attivi questa opzione viene memorizzato soltanto un token di sessione revocabile, valido per un tempo limitato. Per Internet usa sempre HTTPS.</p><div class="actions"><button onclick="login()">Accedi</button><button class="secondary" onclick="logout()">Disconnetti</button></div><div id="authResult" class="feedback"></div></section>
<div id="appContent">
<section class="card"><div class="status-strip"><div><span class="muted">Progetto corrente</span><div id="workspacePath" class="project-name">Nessun workspace selezionato</div></div><button class="secondary" onclick="logout()">Disconnetti</button></div>
<details id="projectTools"><summary>Scegli o gestisci progetto</summary><div class="details-body"><label for="workspaceRoot">Cartella root progetti</label><input id="workspaceRoot" readonly placeholder="Non configurata nel programma BridgAI"><p id="rootHelp" class="muted">Configura la root nelle Impostazioni del programma BridgAI e riavvia la Web UI.</p><div id="workspacePicker"></div><div class="actions"><button id="openWorkspaceButton" onclick="setWorkspace()">Apri progetto</button><button class="secondary" onclick="refreshStatus()">Aggiorna elenco</button></div>
<div id="projectManagement"><div class="grid"><div><h3>Nuovo progetto</h3><label for="newProjectName">Nome cartella</label><input id="newProjectName" placeholder="mio-progetto"><label class="switch-row" for="initializeGit"><input id="initializeGit" type="checkbox" checked><span class="switch-track" aria-hidden="true"></span><span>Inizializza Git</span></label><div class="actions"><button class="success" onclick="createProject()">Crea e apri</button></div></div><div><h3>Clona da Git</h3><label for="cloneRepository">URL repository</label><input id="cloneRepository" placeholder="https://github.com/owner/repository.git"><label for="cloneProjectName">Nome cartella opzionale</label><input id="cloneProjectName"><div class="actions"><button class="success" onclick="cloneProject()">Clona e apri</button></div></div></div></div><div id="projectResult" class="feedback"></div></div></details></section>
<section class="hero"><div><p class="eyebrow">Workspace locale, controllo totale</p><h1>Cosa vuoi fare oggi?</h1><p>Prepara la richiesta, scambia i file con la tua AI e applica le modifiche solo dopo averle verificate.</p></div><div class="flow-pills" aria-label="Flusso in tre passaggi"><span>1 · Richiesta</span><span>2 · File</span><span>3 · Applica</span></div></section>
{task_step}{export_step}{update_step}
<section class="card github-simple-card"><div class="step-head"><span class="step-number">G</span><div><p class="eyebrow">Pubblicazione semplice</p><h2>GitHub in un clic</h2><p>Al primo utilizzo crea il repository; dopo, pubblica automaticamente gli aggiornamenti.</p></div></div><div class="status-strip"><div><span class="muted">Stato GitHub</span><div id="githubSimpleStatus" class="project-name">Controllo in corso…</div></div></div><div class="grid"><div><label id="githubRepoLabel" for="githubRepoName">Nome nuova repository GitHub</label><input id="githubRepoName" placeholder="nome-nuova-repository"><p id="githubRepoHelp" class="field-help">Verrà usato solo per creare la repository del progetto corrente.</p></div><div><label for="githubVisibility">Visibilità della nuova repository</label><select id="githubVisibility"><option value="private">Privato</option><option value="public">Pubblico</option></select></div></div><div class="actions"><button id="githubSimpleButton" class="success" onclick="simpleGithubAction()">Crea repository e pubblica</button><button id="githubOpenButton" class="secondary" onclick="openGithubRepository()" disabled>Apri repository</button></div><div id="githubSimpleResult" class="feedback"></div></section>
<section class="card advanced-card"><details id="verificationTools"><summary>Verifica e strumenti avanzati</summary><div class="details-body"><p class="muted">Usa questi comandi dopo l’applicazione o per la manutenzione del progetto. I test non annullano automaticamente l’aggiornamento: BridgAI distingue una verifica parziale da un errore strutturale e mostra sempre i dettagli.</p><div class="actions"><button class="success" onclick="runTests()">Esegui test</button><button class="secondary" onclick="runTool('/api/git/status','Git status completato')">Git status</button><button class="secondary" onclick="runTool('/api/git/diff','Git diff completato')">Git diff</button><button class="danger" onclick="rollback()">Rollback ultimo batch</button><button class="danger" onclick="restartProgram()">Riavvia BridgAI</button></div><div id="toolResult" class="feedback"></div></div></details></section>
</div></main><script>{script}</script></body></html>"""
