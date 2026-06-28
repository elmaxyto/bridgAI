from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

from local_ai_bridge.web.page_assets import PAGE_SCRIPT, PAGE_STYLE
from local_ai_bridge.core.prompt_presets import load_prompt_presets


def _icon_path() -> Path:
    return Path(__file__).parents[1] / "resources" / "app_icon.svg"


def _icon_revision() -> str:
    return hashlib.sha256(_icon_path().read_bytes()).hexdigest()[:12]


def _icon_url() -> str:
    return f"/favicon.svg?v={_icon_revision()}"


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
            "icons": [{"src": _icon_url(), "sizes": "any", "type": "image/svg+xml"}],
        },
        ensure_ascii=False,
    )


def render_favicon_svg() -> str:
    return _icon_path().read_text(encoding="utf-8")


def _step(number: str, title: str, description: str, body: str) -> str:
    return f"""
<section class="card step-card">
  <div class="step-head"><span class="step-number">{number}</span><div><p class="eyebrow">Passaggio {number} di 3</p><h2>{title}</h2><p>{description}</p></div></div>
  {body}
</section>"""


def _power_user_settings_section() -> str:
    return """
<section class="card power-user-card">
<details id="powerUserSettings" ontoggle="if(this.open)loadPowerUserSettings()">
  <summary>Impostazioni power-user</summary>
  <div class="details-body">
    <p class="muted">Queste opzioni avanzate sono condivise con la versione desktop. Credenziali, 2FA, root progetti e chiavi cloud restano configurabili soltanto dal programma locale.</p>
    <div class="power-user-grid">
      <div class="settings-panel">
        <h3>Contesto AI avanzato</h3>
        <label class="switch-row" for="includeCustomPrompts"><input id="includeCustomPrompts" type="checkbox"><span class="switch-track" aria-hidden="true"></span><span>Includi le istruzioni personalizzate nel Super-Report</span></label>
        <label for="globalPrompt">Prompt globale</label>
        <textarea id="globalPrompt" class="settings-textarea" placeholder="Convenzioni, lingua, vincoli architetturali e preferenze valide per tutti i progetti..."></textarea>
      </div>
      <div class="settings-panel">
        <h3>Formati di scambio</h3>
        <p class="field-help"><strong>ZIP → ZIP è il flusso consigliato ed è l’unico verificato come pienamente funzionante. Usa i formati Markdown solo come alternativa: soprattutto per le modifiche in modalità patch, il risultato potrebbe non funzionare sempre.</strong></p>
        <label for="preferredWebAi">AI Web preferita</label>
        <select id="preferredWebAi" onchange="applyPreferredWebAiPreset()"><option value="chatgpt">ChatGPT</option><option value="claude">Claude</option><option value="gemini">Gemini</option><option value="custom">Personalizzato</option></select>
        <p class="field-help">ChatGPT e Claude usano ZIP → ZIP; Gemini usa ZIP → File Markdown di aggiornamento. Con Personalizzato scegli il flusso.</p>
        <label for="requestedFilesFormat">Formato dei file richiesti</label>
        <select id="requestedFilesFormat"><option value="zip">ZIP — consigliato</option><option value="markdown">Markdown — per AI senza supporto ZIP</option></select>
        <p class="field-help">Definisce cosa scarichi quando l’AI richiede file con #scarica.</p>
        <label for="updateFormat">Formato delle modifiche proposte</label>
        <select id="updateFormat"><option value="zip">ZIP — consigliato</option><option value="text">File Markdown di aggiornamento</option></select>
        <p class="field-help">Il file Markdown di aggiornamento contiene operazioni CREATE, REPLACE e DELETE complete. L’automazione browser viene disabilitata quando uno dei formati non usa ZIP.</p>
        <details class="compatibility-details" id="aiWebCompatibility">
          <summary>Compatibilità con le AI Web</summary>
          <div class="details-body">
            <p class="field-help">Il formato dei file richiesti è distinto dal formato delle modifiche proposte.</p>
            <div class="compatibility-table-wrap">
              <table class="compatibility-table">
                <thead><tr><th>AI Web</th><th>Formato dei file richiesti</th><th>Formato delle modifiche proposte</th></tr></thead>
                <tbody>
                  <tr><th scope="row">ChatGPT</th><td>ZIP o Markdown</td><td>ZIP o Markdown</td></tr>
                  <tr><th scope="row">Claude</th><td>ZIP o Markdown</td><td>ZIP o Markdown</td></tr>
                  <tr><th scope="row">Gemini Pro</th><td>ZIP o Markdown</td><td>Markdown</td></tr>
                  <tr><th scope="row">Perplexity</th><td>Markdown consigliato</td><td>Markdown</td></tr>
                  <tr><th scope="row">Microsoft Copilot</th><td>Markdown</td><td>Markdown</td></tr>
                </tbody>
              </table>
            </div>
            <p class="field-help"><strong>ZIP → ZIP è il percorso raccomandato e testato. Le modalità Markdown aumentano la compatibilità con alcune AI Web, ma non offrono la stessa garanzia operativa; in particolare, le patch Markdown potrebbero non essere applicabili in tutti i casi.</strong></p>
          </div>
        </details>
      </div>
    </div>
    <div id="projectPowerUserSettings" class="settings-panel">
      <h3>Progetto corrente</h3>
      <p id="projectPowerUserHint" class="field-help">Prompt ed esclusioni vengono salvati nel workspace aperto.</p>
      <label for="projectPrompt">Prompt del progetto</label>
      <textarea id="projectPrompt" class="settings-textarea" placeholder="Istruzioni specifiche del workspace selezionato..."></textarea>
      <label for="projectIgnore">File esclusi dal Super-Report</label>
      <textarea id="projectIgnore" class="settings-textarea compact-settings-textarea" placeholder="Un glob per riga, ad esempio dist/, *.sqlite o docs/generated/**"></textarea>
    </div>
    <p class="field-help">Le modifiche vengono salvate nella configurazione condivisa. Se la finestra desktop è già aperta, riaprila o aggiornane la schermata prima di modificare nuovamente le stesse opzioni.</p>
    <div class="actions"><button class="secondary" onclick="loadPowerUserSettings(true)">Ricarica impostazioni</button><button class="success" onclick="savePowerUserSettings()">Salva impostazioni power-user</button></div>
    <div id="powerUserResult" class="feedback"></div>
  </div>
</details>
</section>
"""


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
<div class="actions"><button onclick="generateReport()">Prepara richiesta per l’AI</button><button id="automationSendButton" class="success" onclick="sendReportToAutomation()" disabled>Invia automaticamente a ChatGPT</button></div>
<div class="provider-actions">
  <button data-provider="chatgpt" disabled onclick="openProvider('https://chatgpt.com/')">Continua su ChatGPT</button>
  <button data-provider="claude" disabled onclick="openProvider('https://claude.ai/new')">Continua su Claude</button>
  <button data-provider="gemini" disabled onclick="openProvider('https://gemini.google.com/')">Continua su Gemini</button>
</div>
<div id="reportResult" class="feedback"></div>
<details id="reportDetails"><summary>Mostra o copia la richiesta preparata</summary><div class="details-body">
  <textarea id="report" readonly placeholder="La richiesta preparata apparirà qui."></textarea>
  <div class="actions"><button class="secondary" onclick="copyReport()">Copia richiesta</button></div>
</div></details>
<details id="browserAutomation"><summary>Automazione browser da server</summary><div class="details-body">
  <p class="muted">Il telefono controlla il flusso, mentre un Chrome fidato e acceso esegue ChatGPT. Per collegamenti via Internet usa esclusivamente HTTPS.</p>
  <div class="status-strip"><div><span class="muted">Stato browser fidato</span><div id="automationStatus" class="project-name">Controllo in corso…</div></div></div>
  <label for="automationServerUrl">Indirizzo da inserire nell’estensione</label><input id="automationServerUrl" readonly>
  <label for="automationToken">Token estensione</label><input id="automationToken" readonly type="text" autocomplete="off" placeholder="Genera un token per configurare l’estensione">
  <div class="actions"><button onclick="configureBrowserAutomation()">Genera o ruota token</button><button class="secondary" onclick="copyValue('automationServerUrl')">Copia indirizzo</button><button class="secondary" onclick="copyValue('automationToken')">Copia token</button><button class="danger" onclick="disableBrowserAutomation()">Disabilita</button></div>
  <div id="automationResult" class="feedback"></div>
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
<p id="exportFormatHint" class="field-help">Formato attivo: ZIP.</p>
<div id="exportResult" class="feedback"></div>
""",
    )
    update_step = _step(
        "3",
        "Controlla e applica l’aggiornamento",
        "Usa il formato selezionato nelle impostazioni avanzate. Nessun file viene scritto prima della tua conferma.",
        """
<div id="zipUpdateInput">
  <label for="zipFile">ZIP dell’aggiornamento</label>
  <input id="zipFile" type="file" accept=".zip,application/zip">
  <div class="actions"><button onclick="uploadZip()">Analizza ZIP</button></div>
</div>
<div id="textUpdateInput" hidden>
  <label for="markdownUpdateFile">File Markdown di aggiornamento</label>
  <input id="markdownUpdateFile" type="file" accept=".md,.txt,text/markdown,text/plain">
  <p class="field-help">Seleziona o trascina qui il file .md o .txt restituito dall’AI.</p>
  <div class="actions"><button onclick="uploadMarkdownUpdate()">Analizza file</button></div>
  <div class="manual-fallback">
    <h3>Oppure incolla manualmente la risposta</h3>
    <textarea id="patchText" placeholder="Incolla qui tutte le operazioni CREATE, REPLACE e DELETE del file Markdown di aggiornamento..."></textarea>
    <div class="actions"><button class="secondary" onclick="pasteInto('patchText','planSummary')">Incolla</button><button onclick="inspectTextUpdate()">Analizza testo incollato</button></div>
  </div>
</div>
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
    icon_url = html.escape(_icon_url(), quote=True)
    script = PAGE_SCRIPT.replace("__CSRF__", json.dumps(csrf_token))
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#07111f"><link rel="icon" href="{icon_url}" type="image/svg+xml"><link rel="apple-touch-icon" href="{icon_url}"><script>(function(){{try{{var saved=localStorage.getItem('bridgai-web-theme');var system=window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';document.documentElement.dataset.theme=saved==='light'||saved==='dark'?saved:system}}catch(_){{document.documentElement.dataset.theme='dark'}}}})();</script><link rel="manifest" href="/manifest.webmanifest"><title>BridgAI Web {safe_version}</title><style>{PAGE_STYLE}</style></head>
<body>
<header><div class="header-row"><div class="brand"><img class="brand-mark" src="{icon_url}" alt="" aria-hidden="true"><div><strong>BridgAI Web</strong><small class="connection-line">Collegati a <strong id="connectionAddress">{displayed_address}</strong></small></div></div><div class="header-meta"><label class="language-control" for="languageSelect"><span class="sr-only">Lingua</span><select id="languageSelect" onchange="changeLanguage(this.value)" aria-label="Lingua interfaccia"><option value="it">IT</option><option value="en">EN</option></select></label><button id="themeToggle" class="theme-toggle" type="button" onclick="toggleTheme()" aria-label="Passa alla modalità chiara" title="Passa alla modalità chiara"><span id="themeIcon" aria-hidden="true">☀</span></button><span id="currentProject" class="project-chip">Nessun progetto aperto</span><span id="modeBadge" class="badge">Connessione…</span></div></div></header>
<div id="busy"><div>Operazione in corso…</div></div>
<main>
<section id="authCard" class="card"><h2>Accesso</h2><p class="muted">Inserisci le credenziali configurate in BridgAI.</p><div class="grid"><div><label for="authUsername">Username</label><input id="authUsername" autocomplete="username"></div><div><label for="authPassword">Password</label><div class="password-field"><input id="authPassword" type="password" autocomplete="current-password"><button id="passwordVisibilityToggle" class="password-toggle" type="button" onclick="togglePasswordVisibility()" aria-label="Mostra password" title="Mostra password" aria-pressed="false"><svg class="password-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path class="password-icon-show" d="M12 5c5.2 0 9.3 4.1 10.5 6.3a1.4 1.4 0 0 1 0 1.4C21.3 14.9 17.2 19 12 19S2.7 14.9 1.5 12.7a1.4 1.4 0 0 1 0-1.4C2.7 9.1 6.8 5 12 5Zm0 2C8.2 7 5 9.8 3.5 12 5 14.2 8.2 17 12 17s7-2.8 8.5-5C19 9.8 15.8 7 12 7Zm0 2.2A2.8 2.8 0 1 1 12 14.8a2.8 2.8 0 0 1 0-5.6Z"/><path class="password-icon-hide" d="m3.3 2 18.7 18.7-1.3 1.3-3.1-3.1A12.7 12.7 0 0 1 12 20C6.8 20 2.7 15.9 1.5 13.7a1.4 1.4 0 0 1 0-1.4 16 16 0 0 1 4.1-4.8L2 3.3 3.3 2Zm3.8 7A13.8 13.8 0 0 0 3.5 13c1.5 2.2 4.7 5 8.5 5 1.4 0 2.7-.4 3.9-1l-2-2a3 3 0 0 1-3.9-3.9L7.1 9Zm4.8-4c5.2 0 9.3 4.1 10.5 6.3a1.4 1.4 0 0 1 0 1.4 15.5 15.5 0 0 1-2.3 3.1l-1.4-1.4a13 13 0 0 0 1.8-2.4c-1.5-2.2-4.7-5-8.5-5-.7 0-1.4.1-2 .3L8.4 5.7c1.1-.4 2.3-.7 3.5-.7Z"/></svg><span id="passwordVisibilityLabel" class="sr-only">Mostra password</span></button></div></div><div id="secondFactorField"><label for="authSecondFactor">Codice 2FA</label><input id="authSecondFactor" inputmode="numeric" autocomplete="one-time-code" placeholder="123456"></div></div><p id="twoFactorHint" class="muted"></p><label class="switch-row" for="rememberCredentials"><input id="rememberCredentials" type="checkbox"><span class="switch-track" aria-hidden="true"></span><span>Ricorda l’accesso su questo browser</span></label><p class="muted">La password e il codice 2FA non vengono conservati. Se attivi questa opzione viene memorizzato soltanto un token di sessione revocabile, valido per un tempo limitato. Per Internet usa sempre HTTPS.</p><div class="actions"><button onclick="login()">Accedi</button><button class="secondary" onclick="logout()">Disconnetti</button></div><div id="authResult" class="feedback"></div></section>
<div id="appContent">
<section class="card"><div class="status-strip"><div><span class="muted">Progetto corrente</span><div id="workspacePath" class="project-name">Nessun workspace selezionato</div></div><button class="secondary" onclick="logout()">Disconnetti</button></div>
<details id="projectTools"><summary>Scegli o gestisci progetto</summary><div class="details-body"><label for="workspaceRoot">Cartella root progetti</label><input id="workspaceRoot" readonly placeholder="Non configurata nel programma BridgAI"><p id="rootHelp" class="muted">Configura la root nelle Impostazioni del programma BridgAI e riavvia la Web UI.</p><div id="workspacePicker"></div><div class="actions"><button id="openWorkspaceButton" onclick="setWorkspace()">Apri progetto</button><button class="secondary" onclick="refreshStatus()">Aggiorna elenco</button></div>
<div id="projectManagement"><div class="grid"><div><h3>Nuovo progetto</h3><label for="newProjectName">Nome cartella</label><input id="newProjectName" placeholder="mio-progetto"><label class="switch-row" for="initializeGit"><input id="initializeGit" type="checkbox" checked><span class="switch-track" aria-hidden="true"></span><span>Inizializza Git</span></label><div class="actions"><button class="success" onclick="createProject()">Crea e apri</button></div></div><div><h3>Clona da Git</h3><label for="cloneRepository">URL repository</label><input id="cloneRepository" placeholder="https://github.com/owner/repository.git"><label for="cloneProjectName">Nome cartella opzionale</label><input id="cloneProjectName"><div class="actions"><button class="success" onclick="cloneProject()">Clona e apri</button></div></div></div></div><div id="projectResult" class="feedback"></div></div></details></section>
<section class="hero"><div><p class="eyebrow">Workspace locale, controllo totale</p><h1>Cosa vuoi fare oggi?</h1><p>Prepara la richiesta, scambia i file con la tua AI e applica le modifiche solo dopo averle verificate.</p></div><div class="flow-pills" aria-label="Flusso in tre passaggi"><span>1 · Richiesta</span><span>2 · File</span><span>3 · Applica</span></div></section>
{task_step}{export_step}{update_step}
<section class="card github-simple-card"><div class="step-head"><span class="step-number">G</span><div><p class="eyebrow">Pubblicazione semplice</p><h2>GitHub in un clic</h2><p>Al primo utilizzo crea il repository; dopo, pubblica automaticamente gli aggiornamenti.</p></div></div><div class="status-strip"><div><span class="muted">Stato GitHub</span><div id="githubSimpleStatus" class="project-name">Controllo in corso…</div></div></div><div class="grid"><div><label id="githubRepoLabel" for="githubRepoName">Nome nuova repository GitHub</label><input id="githubRepoName" placeholder="nome-nuova-repository"><p id="githubRepoHelp" class="field-help">Verrà usato solo per creare la repository del progetto corrente.</p></div><div><label for="githubVisibility">Visibilità della nuova repository</label><select id="githubVisibility"><option value="private">Privato</option><option value="public">Pubblico</option></select></div></div><div class="actions"><button id="githubSimpleButton" class="success" onclick="simpleGithubAction()">Crea repository e pubblica</button><button id="githubOpenButton" class="secondary" onclick="openGithubRepository()" disabled>Apri repository</button></div><div id="githubSimpleResult" class="feedback"></div></section>
<section class="card advanced-card"><details id="verificationTools"><summary>Verifica e strumenti avanzati</summary><div class="details-body"><p class="muted">Usa questi comandi dopo l’applicazione o per la manutenzione del progetto. I test non annullano automaticamente l’aggiornamento: BridgAI distingue una verifica parziale da un errore strutturale e mostra sempre i dettagli.</p><div class="actions"><button class="success" onclick="runTests()">Esegui test</button><button class="secondary" onclick="runTool('/api/git/status','Git status completato')">Git status</button><button class="secondary" onclick="runTool('/api/git/diff','Git diff completato')">Git diff</button><button class="danger" onclick="rollback()">Rollback ultimo batch</button><button class="danger" onclick="restartProgram()">Riavvia BridgAI</button></div><div id="toolResult" class="feedback"></div></div></details></section>
{_power_user_settings_section()}
</div></main><script>{script}</script></body></html>"""
