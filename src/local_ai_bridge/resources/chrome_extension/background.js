importScripts("download_tracking.js");

const DEFAULTS = {
  enabled: false,
  serverUrl: "",
  port: 8765,
  token: "",
  downloadSubdirectory: "",
  syncedDownloadDirectory: ""
};
let activeRequestId = "";
let activeTabId = null;
let polling = false;
let lastDirectorySyncCheck = 0;

function normalizedBridgeUrl(value, legacyPort = 8765) {
  let raw = String(value || "").trim();
  if (!raw) raw = `http://127.0.0.1:${Number(legacyPort) || 8765}`;
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(raw)) raw = `https://${raw}`;
  const url = new URL(raw);
  if (url.username || url.password) {
    throw new Error("L’indirizzo BridgAI non può contenere credenziali.");
  }
  const localHost = ["127.0.0.1", "localhost"].includes(url.hostname);
  if (url.protocol !== "https:" && !(url.protocol === "http:" && localHost)) {
    throw new Error("Per un server remoto BridgAI è obbligatorio HTTPS.");
  }
  if (url.pathname !== "/" || url.search || url.hash) {
    throw new Error("Inserisci soltanto l’origine BridgAI, senza percorso o parametri.");
  }
  return url.origin;
}

async function config() {
  const stored = await chrome.storage.local.get(DEFAULTS);
  return { ...DEFAULTS, ...stored, serverUrl: normalizedBridgeUrl(stored.serverUrl, stored.port) };
}

function baseUrl(current) {
  return normalizedBridgeUrl(current.serverUrl, current.port);
}

function isLocalBridge(current) {
  const hostname = new URL(baseUrl(current)).hostname.toLowerCase();
  return hostname === "127.0.0.1" || hostname === "localhost" || hostname === "::1";
}

async function fetchBridge(current, path, options = {}) {
  if (!current.token) {
    throw new Error("Token BridgAI mancante.");
  }
  const headers = new Headers(options.headers || {});
  headers.set("X-BridgAI-Extension-Token", current.token);
  headers.set("X-BridgAI-Extension-Version", chrome.runtime.getManifest().version);
  return fetch(baseUrl(current) + path, { ...options, headers });
}

async function bridgeFetch(path, options = {}) {
  const current = await config();
  if (!current.enabled) {
    throw new Error("Estensione BridgAI non abilitata.");
  }
  return fetchBridge(current, path, options);
}

async function jsonPayload(response, fallbackLabel = "BridgAI") {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `${fallbackLabel} HTTP ${response.status}`);
  }
  return payload;
}

async function jsonRequest(path, options = {}) {
  return jsonPayload(await bridgeFetch(path, options));
}

async function verifyConnection(value = {}) {
  const current = {
    ...DEFAULTS,
    ...value,
    serverUrl: normalizedBridgeUrl(value.serverUrl, value.port)
  };
  const response = await fetchBridge(current, "/api/extension/status");
  const payload = await jsonPayload(response);
  const synchronized = await synchronizeDownloadDirectory(current, { force: true });
  return { ...payload, update_directory: synchronized.update_directory || "" };
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }
  return btoa(binary);
}


function normalizedFilename(value) {
  let raw = String(value || "").trim();
  try {
    raw = decodeURIComponent(raw);
  } catch (_error) {
    // Keep the undecoded value when a remote header contains invalid escapes.
  }
  raw = raw.split(/[?#]/, 1)[0].split(/[\\/]/).pop() || "";
  raw = raw.replace(/[\x00-\x1f\\/:*?"<>|]+/g, "_").trim();
  return raw.toLowerCase().endsWith(".zip") ? raw : "bridgai_update.zip";
}

function normalizedDownloadSubdirectory(value) {
  const raw = String(value || "").trim().replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
  if (!raw) return "";
  const parts = raw.split("/").map((part) => part.trim());
  if (parts.some((part) => !part || part === "." || part === "..")) {
    throw new Error("La sottocartella Download contiene un segmento non valido.");
  }
  if (parts.some((part) => /[\x00-\x1f:*?"<>|]/.test(part))) {
    throw new Error("La sottocartella Download contiene caratteri non validi.");
  }
  return parts.join("/");
}

function downloadFilename(current, filename) {
  const base = normalizedFilename(filename);
  const directory = normalizedDownloadSubdirectory(current.downloadSubdirectory);
  return directory ? `${directory}/${base}` : base;
}

function parentDirectory(value) {
  return String(value || "").replace(/[\\/][^\\/]+$/, "");
}

async function waitForDownload(downloadId, timeoutMilliseconds = 15000) {
  const deadline = Date.now() + timeoutMilliseconds;
  while (Date.now() < deadline) {
    const matches = await chrome.downloads.search({ id: downloadId });
    const item = matches[0];
    if (item?.state === "complete") return item;
    if (item?.state === "interrupted") {
      throw new Error("Chrome ha interrotto la verifica della cartella Download.");
    }
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error("Chrome non ha completato la verifica della cartella Download.");
}

async function postDownloadDirectory(current, payload) {
  const response = await fetchBridge(current, "/api/extension/download-directory", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return jsonPayload(response);
}

async function synchronizeDownloadDirectory(current, { force = false } = {}) {
  if (!isLocalBridge(current)) {
    await chrome.storage.local.set({ syncedDownloadDirectory: "" });
    const response = await fetchBridge(current, "/api/extension/status");
    return jsonPayload(response);
  }
  if (!force && Date.now() - lastDirectorySyncCheck < 60000) {
    return { update_directory: current.syncedDownloadDirectory || "" };
  }
  lastDirectorySyncCheck = Date.now();
  const directory = normalizedDownloadSubdirectory(current.downloadSubdirectory);
  if (!current.enabled || !directory) {
    const payload = await postDownloadDirectory(current, {
      enabled: Boolean(current.enabled),
      path: ""
    });
    await chrome.storage.local.set({ syncedDownloadDirectory: "" });
    return payload;
  }

  if (!force && current.syncedDownloadDirectory) {
    const statusResponse = await fetchBridge(current, "/api/extension/status");
    const statusPayload = await jsonPayload(statusResponse);
    if (statusPayload.update_directory === current.syncedDownloadDirectory) {
      return statusPayload;
    }
  }

  const probeName = `.bridgai-download-directory-${Date.now()}-${Math.random().toString(16).slice(2)}.tmp`;
  const downloadId = await chrome.downloads.download({
    url: "data:text/plain;base64,QnJpZGdBSSBkb3dubG9hZCBkaXJlY3RvcnkgcHJvYmUK",
    filename: `${directory}/${probeName}`,
    conflictAction: "uniquify",
    saveAs: false
  });
  const item = await waitForDownload(downloadId);
  try {
    const payload = await postDownloadDirectory(current, {
      enabled: true,
      path: item.filename
    });
    const synchronized = String(payload.update_directory || parentDirectory(item.filename));
    await chrome.storage.local.set({ syncedDownloadDirectory: synchronized });
    return payload;
  } finally {
    await chrome.downloads.removeFile(downloadId).catch(() => undefined);
    await chrome.downloads.erase({ id: downloadId }).catch(() => undefined);
  }
}

function filenameFromContentDisposition(value) {
  const header = String(value || "");
  const encoded = header.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
  if (encoded) return normalizedFilename(encoded[1].replace(/^"|"$/g, ""));
  const plain = header.match(/filename\s*=\s*"?([^";]+)"?/i);
  return plain ? normalizedFilename(plain[1]) : "";
}

function zipFilename(message, response) {
  const fromHeader = filenameFromContentDisposition(response.headers.get("Content-Disposition"));
  if (fromHeader) return fromHeader;
  const fromResponseUrl = normalizedFilename(response.url);
  if (fromResponseUrl !== "bridgai_update.zip") return fromResponseUrl;
  return normalizedFilename(message.filename);
}

function hasZipSignature(buffer) {
  const bytes = new Uint8Array(buffer);
  if (bytes.length < 4 || bytes[0] !== 0x50 || bytes[1] !== 0x4b) return false;
  const signature = (bytes[2] << 8) | bytes[3];
  return signature === 0x0304 || signature === 0x0506 || signature === 0x0708;
}

async function reportAutomationError(requestId, error) {
  const message = String(error?.message || error || "Errore sconosciuto dell’automazione.").trim();
  if (!requestId || !message) return;
  try {
    await jsonRequest("/api/extension/error", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: requestId, message })
    });
  } catch (reportError) {
    console.debug("BridgAI error reporting:", reportError.message);
  }
}

const downloadTracking = self.BridgAIDownloadTracking.create({
  getConfig: config,
  bridgeBaseUrl: baseUrl,
  jsonRequest,
  normalizedFilename,
  downloadFilename,
  reportError: reportAutomationError
});

async function downloadArtifact(artifactUrl) {
  const current = await config();
  if (!current.enabled || !current.token) {
    throw new Error("Estensione BridgAI non configurata.");
  }
  const expectedBase = baseUrl(current);
  const url = new URL(artifactUrl, `${expectedBase}/`);
  if (url.origin !== expectedBase) {
    throw new Error("URL del contesto BridgAI non valido.");
  }
  const response = await fetchBridge(current, `${url.pathname}${url.search}`);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || `Download contesto HTTP ${response.status}`);
  }
  return arrayBufferToBase64(await response.arrayBuffer());
}

async function chatgptTab() {
  const tabs = await chrome.tabs.query({ url: "https://chatgpt.com/*" });
  if (tabs.length) {
    return tabs.find((tab) => tab.active) || tabs[0];
  }
  return chrome.tabs.create({ url: "https://chatgpt.com/", active: true });
}

async function waitForTab(tabId) {
  const tab = await chrome.tabs.get(tabId);
  if (tab.status === "complete") return;
  await new Promise((resolve) => {
    const listener = (changedId, info) => {
      if (changedId === tabId && info.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
    setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    }, 20000);
  });
}

async function deliverRequest(request) {
  const tab = await chatgptTab();
  activeRequestId = request.request_id;
  activeTabId = tab.id;
  await waitForTab(tab.id);
  const message = {
    type: "BRIDGAI_SEND_PROMPT",
    requestId: request.request_id,
    prompt: request.prompt
  };
  let result;
  try {
    result = await chrome.tabs.sendMessage(tab.id, message);
  } catch (_error) {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content.js"]
    });
    await new Promise((resolve) => setTimeout(resolve, 250));
    result = await chrome.tabs.sendMessage(tab.id, message);
  }
  if (result?.error) {
    throw new Error(result.error);
  }
}

async function poll() {
  if (polling) return;
  polling = true;
  try {
    const current = await config();
    if (!current.enabled || !current.token) return;
    await downloadTracking.retry();
    await synchronizeDownloadDirectory(current).catch((error) => {
      console.debug("BridgAI download directory:", error.message);
    });
    const payload = await jsonRequest("/api/extension/next");
    if (payload.request) {
      try {
        await deliverRequest(payload.request);
      } catch (error) {
        await reportAutomationError(payload.request.request_id, error);
        throw error;
      }
    }
  } catch (error) {
    console.debug("BridgAI poll:", error.message);
  } finally {
    polling = false;
  }
}

async function postResponse(message, sender) {
  activeRequestId = message.requestId;
  activeTabId = sender.tab?.id ?? activeTabId;
  const payload = await jsonRequest("/api/extension/response", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: message.requestId, text: message.text })
  });
  if (payload.action === "attach_context" && activeTabId !== null) {
    const artifactBase64 = await downloadArtifact(payload.artifact_url);
    const result = await chrome.tabs.sendMessage(activeTabId, {
      type: "BRIDGAI_ATTACH_CONTEXT",
      requestId: message.requestId,
      artifactBase64,
      filename: payload.filename,
      followupPrompt: payload.followup_prompt
    });
    if (result?.error) {
      throw new Error(result.error);
    }
  }
  return payload;
}

async function uploadZipFromUrl(message) {
  const current = await config();
  try {
    const remote = await fetch(message.url, { credentials: "include" });
    if (!remote.ok) throw new Error(`Download HTTP ${remote.status}`);
    const bytes = await remote.arrayBuffer();
    if (!hasZipSignature(bytes)) {
      throw new Error("Il file ricevuto da ChatGPT non è uno ZIP valido.");
    }
    const filename = zipFilename(message, remote);
    const response = await bridgeFetch("/api/extension/zip", {
      method: "POST",
      headers: {
        "Content-Type": "application/zip",
        "X-File-Name": filename,
        "X-BridgAI-Request-ID": message.requestId
      },
      body: bytes
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `Upload HTTP ${response.status}`);
    await downloadTracking.clear(message.requestId);
    return payload;
  } catch (directError) {
    if (!isLocalBridge(current)) {
      throw new Error(
        `${directError.message}; il fallback tramite file locale non è disponibile con un server BridgAI remoto.`
      );
    }
    try {
      await downloadTracking.expect(message.requestId, message.filename);
      const downloadId = await chrome.downloads.download({
        url: message.url,
        filename: downloadFilename(current, message.filename),
        conflictAction: "uniquify",
        saveAs: false
      });
      await downloadTracking.track(downloadId, message.requestId, message.filename);
      return {
        fallback_download: true,
        download_id: downloadId,
        message: directError.message
      };
    } catch (downloadError) {
      return {
        click_link: true,
        message: `${directError.message}; ${downloadError.message}`
      };
    }
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "BRIDGAI_RESPONSE") {
    postResponse(message, sender).then(sendResponse).catch(async (error) => {
      await reportAutomationError(message.requestId, error);
      sendResponse({ error: error.message });
    });
    return true;
  }
  if (message?.type === "BRIDGAI_ZIP_LINK") {
    uploadZipFromUrl(message).then(sendResponse).catch(async (error) => {
      await reportAutomationError(message.requestId, error);
      sendResponse({ error: error.message });
    });
    return true;
  }
  if (message?.type === "BRIDGAI_EXPECT_ZIP_DOWNLOAD") {
    downloadTracking.expect(message.requestId, message.filename)
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ error: error.message }));
    return true;
  }
  if (message?.type === "BRIDGAI_AUTOMATION_ERROR") {
    reportAutomationError(message.requestId, message.message)
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ error: error.message }));
    return true;
  }
  if (message?.type === "BRIDGAI_VERIFY") {
    verifyConnection(message.config).then(sendResponse).catch((error) => sendResponse({ error: error.message }));
    return true;
  }
  if (message?.type === "BRIDGAI_POLL_NOW") {
    poll().then(() => sendResponse({ ok: true }));
    return true;
  }
});

chrome.runtime.onInstalled.addListener((details) => {
  chrome.alarms.create("bridgai-poll", { periodInMinutes: 0.5 });
  if (details.reason === "install") chrome.runtime.openOptionsPage();
  poll();
});
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create("bridgai-poll", { periodInMinutes: 0.5 });
  poll();
});
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "bridgai-poll") poll();
});
chrome.storage.onChanged.addListener(() => poll());
chrome.alarms.create("bridgai-poll", { periodInMinutes: 0.5 });
setInterval(poll, 2500);
poll();
