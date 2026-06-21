let currentRequestId = "";
let responseWatchToken = 0;

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function assistantMessages() {
  return [...document.querySelectorAll('[data-message-author-role="assistant"]')];
}

function composer() {
  return (
    document.querySelector("#prompt-textarea") ||
    document.querySelector('textarea[data-id="root"]') ||
    document.querySelector('[contenteditable="true"][data-lexical-editor="true"]') ||
    document.querySelector('form textarea')
  );
}

function setComposerText(text) {
  const editor = composer();
  if (!editor) throw new Error("Campo del prompt ChatGPT non trovato.");
  editor.focus();
  if (editor instanceof HTMLTextAreaElement || editor instanceof HTMLInputElement) {
    const setter = Object.getOwnPropertyDescriptor(editor.constructor.prototype, "value")?.set;
    if (setter) setter.call(editor, text);
    else editor.value = text;
  } else {
    editor.textContent = "";
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    editor.appendChild(paragraph);
  }
  editor.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: text }));
  editor.dispatchEvent(new Event("change", { bubbles: true }));
}

async function sendComposer(timeoutMilliseconds = 60000) {
  const deadline = Date.now() + timeoutMilliseconds;
  while (Date.now() < deadline) {
    const button =
      document.querySelector('[data-testid="send-button"]') ||
      [...document.querySelectorAll("button")].find((item) => {
        const label = `${item.getAttribute("aria-label") || ""} ${item.textContent || ""}`.toLowerCase();
        return label.includes("send") || label.includes("invia");
      });
    if (button && !button.disabled && button.getAttribute("aria-disabled") !== "true") {
      button.click();
      return;
    }
    await sleep(150);
  }
  throw new Error("Il pulsante di invio ChatGPT non è diventato disponibile.");
}

function generationInProgress() {
  if (document.querySelector('[data-testid="stop-button"], [data-testid*="stop-generating"]')) {
    return true;
  }
  return [...document.querySelectorAll("button")].some((button) => {
    const value = [
      button.getAttribute("aria-label") || "",
      button.getAttribute("data-testid") || "",
      button.textContent || ""
    ].join(" ").toLowerCase();
    return /stop (?:generating|response|streaming)|interrompi|arresta|termina/.test(value);
  });
}

function normalizedCandidateText(value) {
  const raw = String(value || "");
  try {
    return decodeURIComponent(raw);
  } catch (_error) {
    return raw;
  }
}

function looksLikeZip(value) {
  return /\.zip(?:\b|[?#])/i.test(normalizedCandidateText(value));
}

function zipRoots(container) {
  const article = container?.closest?.("article");
  const turn = container?.closest?.('[data-testid^="conversation-turn"]');
  const roots = [container, article, turn, article?.parentElement].filter(Boolean);
  return roots.filter((root, index) => roots.indexOf(root) === index);
}

function visible(element) {
  if (!element || element.hidden) return false;
  const style = window.getComputedStyle(element);
  return style.display !== "none" && style.visibility !== "hidden";
}

function elementDetails(element) {
  return normalizedCandidateText([
    element?.getAttribute?.("href") || "",
    element?.href || "",
    element?.download || "",
    element?.getAttribute?.("aria-label") || "",
    element?.getAttribute?.("title") || "",
    element?.getAttribute?.("data-testid") || "",
    element?.getAttribute?.("data-file-name") || "",
    element?.getAttribute?.("data-filename") || "",
    element?.getAttribute?.("data-state") || "",
    element?.textContent || ""
  ].join(" "));
}

function nearbyZipText(element) {
  let current = element?.parentElement || null;
  for (let level = 0; current && level < 5; level += 1) {
    if (looksLikeZip(current.textContent || "")) return true;
    if (current.tagName === "ARTICLE") break;
    current = current.parentElement;
  }
  return false;
}

function zipLink(container) {
  const downloadWords = /(?:download|scarica|salva|save)/i;
  for (const root of zipRoots(container)) {
    const link = [...root.querySelectorAll("a[href]")].reverse().find((anchor) => {
      if (!visible(anchor)) return false;
      const ownDetails = elementDetails(anchor);
      return looksLikeZip(ownDetails) ||
        (downloadWords.test(ownDetails) && nearbyZipText(anchor));
    });
    if (link) return link;
  }
  return null;
}

function zipDownloadButton(container) {
  const downloadWords = /(?:download|scarica|salva|save)/i;
  for (const root of zipRoots(container)) {
    const button = [...root.querySelectorAll(
      'button, [role="button"], [data-testid*="download"], [aria-label*="ownload" i]'
    )].reverse().find((candidate) => {
      if (!visible(candidate) || candidate.disabled || candidate.getAttribute("aria-disabled") === "true") {
        return false;
      }
      const ownDetails = elementDetails(candidate);
      return looksLikeZip(ownDetails) ||
        (downloadWords.test(ownDetails) && nearbyZipText(candidate));
    });
    if (button) return button;
  }
  return null;
}

function zipFilename(element) {
  const candidates = [
    element?.download,
    element?.getAttribute?.("title"),
    element?.getAttribute?.("aria-label"),
    element?.textContent,
    element?.href
  ];
  for (const candidate of candidates) {
    const decoded = normalizedCandidateText(candidate).trim();
    const match = decoded.match(/([^\s"'<>\\/]+\.zip)\b/i);
    if (match) return match[1];
  }
  return "bridgai_update.zip";
}

async function waitForZipTarget(initialContainer, timeoutMilliseconds = 180000) {
  const deadline = Date.now() + timeoutMilliseconds;
  while (Date.now() < deadline) {
    const latest = assistantMessages().at(-1) || initialContainer;
    const link = zipLink(latest);
    if (link) return { kind: "link", element: link };
    const button = zipDownloadButton(latest);
    if (button) return { kind: "button", element: button };
    await sleep(250);
  }
  return null;
}

async function watchResponse(requestId, previousCount) {
  const token = ++responseWatchToken;
  let stableText = "";
  let stableCycles = 0;
  for (let cycle = 0; cycle < 2400 && token === responseWatchToken; cycle += 1) {
    await sleep(500);
    const messages = assistantMessages();
    if (messages.length <= previousCount) continue;
    const latest = messages[messages.length - 1];
    const text = (latest.innerText || latest.textContent || "").trim();
    if (!text) continue;
    if (text === stableText) stableCycles += 1;
    else {
      stableText = text;
      stableCycles = 0;
    }
    if (!generationInProgress() && stableCycles >= 3) {
      const bridgeResult = await chrome.runtime.sendMessage({
        type: "BRIDGAI_RESPONSE",
        requestId,
        text
      });
      if (bridgeResult?.error) {
        throw new Error(bridgeResult.error);
      }
      if (bridgeResult?.action === "wait_for_zip") {
        const target = await waitForZipTarget(latest);
        if (!target) {
          throw new Error("ChatGPT non ha mostrato uno ZIP scaricabile entro il tempo previsto.");
        }
        if (target.kind === "link") {
          const zipResult = await chrome.runtime.sendMessage({
            type: "BRIDGAI_ZIP_LINK",
            requestId,
            url: target.element.href || target.element.getAttribute("href"),
            filename: zipFilename(target.element)
          });
          if (zipResult?.error) {
            throw new Error(zipResult.error);
          }
          if (zipResult?.click_link) {
            const expected = await chrome.runtime.sendMessage({
              type: "BRIDGAI_EXPECT_ZIP_DOWNLOAD",
              requestId,
              filename: zipFilename(target.element)
            });
            if (expected?.error) throw new Error(expected.error);
            target.element.click();
          }
        } else if (target.kind === "button") {
          const expected = await chrome.runtime.sendMessage({
            type: "BRIDGAI_EXPECT_ZIP_DOWNLOAD",
            requestId,
            filename: zipFilename(target.element)
          });
          if (expected?.error) throw new Error(expected.error);
          target.element.click();
        }
      }
      return;
    }
  }
  if (token === responseWatchToken) {
    throw new Error("ChatGPT non ha completato una risposta utilizzabile entro il tempo previsto.");
  }
}

async function sendPrompt(requestId, prompt) {
  currentRequestId = requestId;
  const count = assistantMessages().length;
  setComposerText(prompt);
  await sendComposer();
  void watchResponse(requestId, count).catch((error) => {
    console.error("BridgAI response automation:", error);
    chrome.runtime.sendMessage({
      type: "BRIDGAI_AUTOMATION_ERROR",
      requestId,
      message: error.message
    }).catch(() => undefined);
  });
}

async function findFileInput() {
  let input = document.querySelector('input[type="file"]');
  if (input) return input;
  const attach = [...document.querySelectorAll("button")].find((button) => {
    const value = `${button.getAttribute("aria-label") || ""} ${button.textContent || ""}`.toLowerCase();
    return value.includes("attach") || value.includes("allega") || value.includes("upload");
  });
  attach?.click();
  for (let attempt = 0; attempt < 30; attempt += 1) {
    await sleep(200);
    input = document.querySelector('input[type="file"]');
    if (input) return input;
  }
  throw new Error("Controllo allegati ChatGPT non trovato.");
}

function attachmentRegion() {
  const editor = composer();
  return editor?.closest?.("form") || editor?.parentElement?.parentElement || document.body;
}

function attachmentIndicators(root = attachmentRegion()) {
  if (!root) return [];
  const selector = [
    '[data-testid*="attachment" i]',
    '[data-testid*="file" i]',
    '[aria-label*="attachment" i]',
    '[aria-label*="allegat" i]',
    'button[aria-label*="remove file" i]',
    'button[aria-label*="rimuovi file" i]'
  ].join(", ");
  return [...root.querySelectorAll(selector)].filter(visible);
}

function attachmentUploadInProgress(root = attachmentRegion()) {
  if (!root) return false;
  if (root.querySelector('[role="progressbar"], [data-state="loading"], [data-state="uploading"]')) {
    return true;
  }
  const text = String(root.innerText || root.textContent || "").toLowerCase();
  return /uploading|caricamento in corso|allegato in caricamento/.test(text);
}

function attachmentUploadFailed(root = attachmentRegion()) {
  const text = String(root?.innerText || root?.textContent || "").toLowerCase();
  return /upload failed|failed to upload|caricamento non riuscito|errore.*allegat/.test(text);
}

async function waitForAttachmentReady(filename, previousIndicatorCount, timeoutMilliseconds = 120000) {
  const expected = String(filename || "").trim().toLowerCase();
  const deadline = Date.now() + timeoutMilliseconds;
  let stableCycles = 0;
  while (Date.now() < deadline) {
    const root = attachmentRegion();
    if (attachmentUploadFailed(root)) {
      throw new Error("ChatGPT ha segnalato un errore durante il caricamento del contesto.");
    }
    const indicators = attachmentIndicators(root);
    const details = String(root?.innerText || root?.textContent || "").toLowerCase();
    const visibleEvidence =
      (expected && details.includes(expected)) ||
      indicators.length > previousIndicatorCount;
    if (visibleEvidence && !attachmentUploadInProgress(root)) stableCycles += 1;
    else stableCycles = 0;
    if (stableCycles >= 3) return;
    await sleep(250);
  }
  throw new Error("ChatGPT non ha completato il caricamento del contesto entro il tempo previsto.");
}

function base64Bytes(value) {
  if (!value) throw new Error("Contesto BridgAI mancante.");
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

async function attachContext(message) {
  const bytes = base64Bytes(message.artifactBase64);
  const filename = message.filename || "bridgai_context.zip";
  const file = new File([bytes], filename, { type: "application/zip" });
  const previousIndicatorCount = attachmentIndicators().length;
  const input = await findFileInput();
  const transfer = new DataTransfer();
  transfer.items.add(file);
  input.files = transfer.files;
  input.dispatchEvent(new Event("change", { bubbles: true }));
  await waitForAttachmentReady(filename, previousIndicatorCount);
  await sendPrompt(message.requestId, message.followupPrompt);
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "BRIDGAI_SEND_PROMPT") {
    sendPrompt(message.requestId, message.prompt)
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ error: error.message }));
    return true;
  }
  if (message?.type === "BRIDGAI_ATTACH_CONTEXT") {
    attachContext(message)
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ error: error.message }));
    return true;
  }
});

// A visible ChatGPT tab keeps the Manifest V3 worker responsive for quick hand-off.
setInterval(() => {
  chrome.runtime.sendMessage({ type: "BRIDGAI_POLL_NOW" }).catch(() => {});
}, 2500);
