const state = document.querySelector("#state");

function normalizedBridgeUrl(value, legacyPort = 8765) {
  let raw = String(value || "").trim();
  if (!raw) raw = `http://127.0.0.1:${Number(legacyPort) || 8765}`;
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(raw)) raw = `https://${raw}`;
  return new URL(raw).origin;
}

async function refresh() {
  const value = await chrome.storage.local.get({
    enabled: false,
    serverUrl: "",
    port: 8765,
    token: ""
  });
  if (!value.enabled || !value.token) {
    state.textContent = "Automazione non configurata.";
    return;
  }
  try {
    const response = await fetch(
      `${normalizedBridgeUrl(value.serverUrl, value.port)}/api/extension/status`,
      { headers: { "X-BridgAI-Extension-Token": value.token } }
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    const request = payload.request_status || "nessuna richiesta in attesa";
    const folder = payload.update_directory || "Download standard";
    state.textContent = `Connessa — ${request}. ZIP: ${folder}.`;
  } catch (error) {
    state.textContent = `Non connessa: ${error.message}`;
  }
}

document.querySelector("#poll").addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ type: "BRIDGAI_POLL_NOW" });
  refresh();
});
document.querySelector("#options").addEventListener("click", () => chrome.runtime.openOptionsPage());
refresh();
