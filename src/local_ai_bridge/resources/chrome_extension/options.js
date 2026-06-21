const enabled = document.querySelector("#enabled");
const serverUrl = document.querySelector("#serverUrl");
const token = document.querySelector("#token");
const downloadSubdirectory = document.querySelector("#downloadSubdirectory");
const status = document.querySelector("#status");

function normalizedBridgeUrl(value, legacyPort = 8765) {
  let raw = String(value || "").trim();
  if (!raw) raw = `http://127.0.0.1:${Number(legacyPort) || 8765}`;
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(raw)) raw = `https://${raw}`;
  const url = new URL(raw);
  if (url.username || url.password) {
    throw new Error("L’indirizzo non può contenere credenziali.");
  }
  const localHost = ["127.0.0.1", "localhost"].includes(url.hostname);
  if (url.protocol !== "https:" && !(url.protocol === "http:" && localHost)) {
    throw new Error("Per un server remoto è obbligatorio HTTPS.");
  }
  if (url.pathname !== "/" || url.search || url.hash) {
    throw new Error("Inserisci soltanto l’origine BridgAI, senza percorso o parametri.");
  }
  return url.origin;
}

function normalizedDownloadSubdirectory(value) {
  const raw = String(value || "").trim().replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
  if (!raw) return "";
  const parts = raw.split("/").map((part) => part.trim());
  if (parts.some((part) => !part || part === "." || part === "..")) {
    throw new Error("La sottocartella Download contiene un segmento non valido.");
  }
  if (parts.some((part) => /[\x00-\x1f:*?\"<>|]/.test(part))) {
    throw new Error("La sottocartella Download contiene caratteri non validi.");
  }
  return parts.join("/");
}

async function load() {
  const value = await chrome.storage.local.get({
    enabled: false,
    serverUrl: "",
    port: 8765,
    token: "",
    downloadSubdirectory: ""
  });
  enabled.checked = value.enabled;
  serverUrl.value = normalizedBridgeUrl(value.serverUrl, value.port);
  token.value = value.token;
  downloadSubdirectory.value = normalizedDownloadSubdirectory(value.downloadSubdirectory);
}

async function ensureOriginPermission(url) {
  const parsed = new URL(url);
  const localHost = ["127.0.0.1", "localhost"].includes(parsed.hostname);
  if (localHost) return;
  const origins = [`${parsed.origin}/*`];
  if (await chrome.permissions.contains({ origins })) return;
  const granted = await chrome.permissions.request({ origins });
  if (!granted) throw new Error("Permesso negato per il server BridgAI selezionato.");
}

async function verify(value) {
  const payload = await chrome.runtime.sendMessage({
    type: "BRIDGAI_VERIFY",
    config: value
  });
  if (!payload) throw new Error("Nessuna risposta dal service worker BridgAI.");
  if (payload.error) throw new Error(payload.error);
  return payload;
}

document.querySelector("#save").addEventListener("click", async () => {
  status.textContent = "Verifica configurazione e cartella Download…";
  try {
    const value = {
      enabled: enabled.checked,
      serverUrl: normalizedBridgeUrl(serverUrl.value),
      token: token.value.trim(),
      downloadSubdirectory: normalizedDownloadSubdirectory(downloadSubdirectory.value)
    };
    await ensureOriginPermission(value.serverUrl);
    await chrome.storage.local.set(value);
    serverUrl.value = value.serverUrl;
    downloadSubdirectory.value = value.downloadSubdirectory;
    const payload = await verify(value);
    const folder = payload.update_directory || "cartella Download standard";
    status.textContent = `Connessa a BridgAI ${payload.application_version}. ZIP: ${folder}.`;
    chrome.runtime.sendMessage({ type: "BRIDGAI_POLL_NOW" });
  } catch (error) {
    status.textContent = `Non connessa: ${error.message}`;
  }
});

load().catch((error) => {
  status.textContent = `Configurazione non valida: ${error.message}`;
});
