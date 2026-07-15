(() => {
if (globalThis.__bridgAIContentScriptLoaded) return;

let currentRequestId = "";
let responseWatchToken = 0;
let passiveDirectiveText = "";
let passiveDirectiveStableCycles = 0;
let passiveDirectiveWatchRunning = false;

const RESPONSE_STABLE_CYCLES = 5;
const PASSIVE_RESPONSE_STABLE_CYCLES = 3;
const CONTENT_HEARTBEAT_MS = 1000;
const submittedResponseKeys = new Set();
const pendingResponseKeys = new Set();

const providerApi = globalThis.BridgAIWebAIProviders;
const currentProvider = providerApi.fromLocation(window.location);
globalThis.__bridgAIContentScriptLoaded = true;
const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function providerName() {
  return currentProvider.label;
}

function visible(element) {
  if (!element || element.hidden) return false;
  const style = window.getComputedStyle(element);
  return style.display !== "none" && style.visibility !== "hidden";
}

function enabledControl(element) {
  return Boolean(
    element &&
    visible(element) &&
    !element.disabled &&
    element.getAttribute("aria-disabled") !== "true"
  );
}

function outermostElements(elements) {
  return elements.filter((candidate) =>
    !elements.some((other) => other !== candidate && other.contains(candidate))
  );
}

function assistantMessages() {
  const messages = providerApi
    .queryAll(document, currentProvider.assistantSelectors)
    .filter(visible);
  return outermostElements(messages).sort((left, right) => {
    if (left === right) return 0;
    const position = left.compareDocumentPosition(right);
    return position & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
  });
}

function composer() {
  const candidates = providerApi.queryAll(document, currentProvider.composerSelectors);
  return candidates.find((element) => visible(element) && !element.disabled) || candidates[0] || null;
}

function assertMessageProvider(message) {
  if (!message?.provider) return;
  const requested = providerApi.normalize(message.provider);
  if (requested !== currentProvider.id) {
    throw new Error(
      `La richiesta è destinata a ${providerApi.get(requested).label}, ma la scheda attiva è ${providerName()}.`
    );
  }
}

function setComposerText(text) {
  const editor = composer();
  if (!editor) throw new Error(`Campo del prompt ${providerName()} non trovato.`);
  const value = String(text || "");
  editor.focus();
  editor.dispatchEvent(new InputEvent("beforeinput", {
    bubbles: true,
    cancelable: true,
    inputType: "insertText",
    data: value
  }));
  if (editor instanceof HTMLTextAreaElement || editor instanceof HTMLInputElement) {
    const setter = Object.getOwnPropertyDescriptor(editor.constructor.prototype, "value")?.set;
    if (setter) setter.call(editor, value);
    else editor.value = value;
  } else {
    let inserted = false;
    try {
      const dataTransfer = new DataTransfer();
      dataTransfer.setData("text/plain", value);
      const pasteEvent = new ClipboardEvent("paste", {
        bubbles: true,
        cancelable: true,
        clipboardData: dataTransfer
      });
      editor.dispatchEvent(pasteEvent);
      if (pasteEvent.defaultPrevented) {
        inserted = true;
      }
    } catch (_e) {
      inserted = false;
    }

    if (!inserted) {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(editor);
      selection?.removeAllRanges();
      selection?.addRange(range);
      try {
        inserted = document.execCommand("insertText", false, value);
      } catch (_error) {
        inserted = false;
      }
    }

    if (!inserted) {
      editor.replaceChildren();
      const paragraph = document.createElement("p");
      paragraph.textContent = value;
      editor.appendChild(paragraph);
    }
  }
  editor.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: value }));
  editor.dispatchEvent(new Event("change", { bubbles: true }));
}

function composerRoots() {
  const editor = composer();
  const roots = [
    editor?.closest?.("form"),
    editor?.closest?.("fieldset"),
    editor?.parentElement,
    editor?.parentElement?.parentElement,
    document
  ].filter(Boolean);
  return roots.filter((root, index) => roots.indexOf(root) === index);
}

function controlText(element) {
  return [
    element?.getAttribute?.("aria-label") || "",
    element?.getAttribute?.("title") || "",
    element?.getAttribute?.("data-testid") || "",
    element?.getAttribute?.("mattooltip") || "",
    element?.textContent || ""
  ].join(" ").trim().toLowerCase();
}

function sendButton() {
  for (const root of composerRoots()) {
    const selected = providerApi.first(root, currentProvider.sendButtonSelectors, enabledControl);
    if (selected) return selected;
  }
  const sendWords = /\b(?:send|submit|invia|invio|manda)\b/i;
  for (const root of composerRoots()) {
    const selected = [...root.querySelectorAll("button, [role=button]")]
      .find((item) => enabledControl(item) && sendWords.test(controlText(item)));
    if (selected) return selected;
  }
  return null;
}

function composerTextContent() {
  const editor = composer();
  if (!editor) return "";
  if (editor instanceof HTMLTextAreaElement || editor instanceof HTMLInputElement) {
    return editor.value || "";
  }
  return editor.innerText || editor.textContent || "";
}

function submitComposerForm() {
  const editor = composer();
  const form = editor?.closest?.("form");
  if (!form) return false;
  if (typeof form.requestSubmit === "function") {
    form.requestSubmit();
    return true;
  }
  const event = new Event("submit", { bubbles: true, cancelable: true });
  form.dispatchEvent(event);
  return true;
}

async function sendComposer(timeoutMilliseconds = 15000) {
  const deadline = Date.now() + timeoutMilliseconds;
  const formFallbackAt = Date.now() + 2000;
  let formFallbackTried = false;
  while (Date.now() < deadline) {
    const button = sendButton();
    if (button) {
      button.click();
      return;
    }
    if (!formFallbackTried && Date.now() >= formFallbackAt && composerTextContent().trim()) {
      formFallbackTried = submitComposerForm();
      if (formFallbackTried) {
        await sleep(500);
        if (generationInProgress() || !composerTextContent().trim()) return;
      }
    }
    await sleep(150);
  }
  throw new Error(`Il pulsante di invio ${providerName()} non è diventato disponibile.`);
}

function generationInProgress() {
  if (providerApi.first(document, currentProvider.streamingSelectors || [], visible)) {
    return true;
  }
  if (providerApi.first(document, currentProvider.stopButtonSelectors, enabledControl)) {
    return true;
  }
  return [...document.querySelectorAll("button, [role=button]")].some((button) => {
    if (!visible(button)) return false;
    return /stop (?:generating|response|streaming)|interrompi|arresta|termina/.test(controlText(button));
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
  const modelResponse = container?.closest?.("model-response");
  const assistant = container?.closest?.('[data-testid*="assistant" i]');
  const roots = [container, article, turn, modelResponse, assistant, article?.parentElement].filter(Boolean);
  return roots.filter((root, index) => roots.indexOf(root) === index);
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
  for (let level = 0; current && level < 6; level += 1) {
    if (looksLikeZip(current.textContent || "")) return true;
    if (["ARTICLE", "MODEL-RESPONSE"].includes(current.tagName)) break;
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
      if (!enabledControl(candidate)) return false;
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

function assistantResponseBaseline() {
  const messages = assistantMessages();
  const latest = messages.at(-1) || null;
  return {
    count: messages.length,
    latest,
    text: responseText(latest)
  };
}

function isNewAssistantResponse(messages, baseline) {
  const latest = messages.at(-1) || null;
  if (!latest) return false;
  const text = responseText(latest);
  return messages.length > baseline.count || latest !== baseline.latest || text !== baseline.text;
}

function responseText(message) {
  return (message?.innerText || message?.textContent || "").trim();
}

function responseSubmissionKey(requestId, text) {
  const normalized = String(text || "").replace(/\s+/g, " ").trim();
  return `${requestId}:${normalized.length}:${normalized.slice(0, 160)}:${normalized.slice(-160)}`;
}

function rememberSubmittedResponseKey(key) {
  submittedResponseKeys.add(key);
  while (submittedResponseKeys.size > 30) {
    submittedResponseKeys.delete(submittedResponseKeys.values().next().value);
  }
}

async function submitAssistantResponse(requestId, text) {
  const cleanRequestId = String(requestId || "").trim();
  const cleanText = String(text || "").trim();
  if (!cleanRequestId || !cleanText) return { duplicate: true };
  const key = responseSubmissionKey(cleanRequestId, cleanText);
  if (submittedResponseKeys.has(key) || pendingResponseKeys.has(key)) {
    return { duplicate: true };
  }
  pendingResponseKeys.add(key);
  try {
    const result = await chrome.runtime.sendMessage({
      type: "BRIDGAI_RESPONSE",
      requestId: cleanRequestId,
      provider: currentProvider.id,
      text: cleanText
    });
    if (result?.error) {
      throw new Error(result.error);
    }
    rememberSubmittedResponseKey(key);
    return result || {};
  } finally {
    pendingResponseKeys.delete(key);
  }
}

async function handleBridgeResponseAction(requestId, latest, bridgeResult) {
  if (bridgeResult?.error) {
    throw new Error(bridgeResult.error);
  }
  if (bridgeResult?.duplicate) return;
  if (bridgeResult?.action === "wait_for_zip") {
    const target = await waitForZipTarget(latest);
    if (!target) {
      throw new Error(`${providerName()} non ha mostrato uno ZIP scaricabile entro il tempo previsto.`);
    }
    if (target.kind === "link") {
      const zipResult = await chrome.runtime.sendMessage({
        type: "BRIDGAI_ZIP_LINK",
        requestId,
        provider: currentProvider.id,
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
}

async function watchPassiveDownloadDirective() {
  if (!currentRequestId || document.visibilityState === "hidden") return;
  const latest = assistantMessages().at(-1);
  const text = responseText(latest);
  if (!latest || !text || !downloadRequestDirective(text)) {
    passiveDirectiveText = "";
    passiveDirectiveStableCycles = 0;
    return;
  }
  if (text === passiveDirectiveText) passiveDirectiveStableCycles += 1;
  else {
    passiveDirectiveText = text;
    passiveDirectiveStableCycles = 0;
  }
  if (generationInProgress() || passiveDirectiveStableCycles < PASSIVE_RESPONSE_STABLE_CYCLES) return;
  const bridgeResult = await submitAssistantResponse(currentRequestId, text);
  await handleBridgeResponseAction(currentRequestId, latest, bridgeResult);
}

const DOWNLOAD_LEADING_MARKUP_PATTERN = /^(?:[>\-*\u2022]+\s*|\d+[.)]\s+)/;
const DOWNLOAD_WRAP_MARKS = ["**", "__", "`", "*", "_"];
const DOWNLOAD_HEADER_PATTERN = /^#scarica\s*:?\s*$/i;
const DOWNLOAD_INLINE_PATTERN = /^#scarica\s*:?[ \t]+(.+?)\s*$/i;

function unwrappedDirectiveLine(line) {
  let working = String(line || "").trim();
  working = working.replace(/^#{1,6}\s+(#scarica\b)/i, "$1");
  let changed = true;
  while (changed && working) {
    changed = false;
    for (const mark of DOWNLOAD_WRAP_MARKS) {
      if (working.length > mark.length * 2 && working.startsWith(mark) && working.endsWith(mark)) {
        working = working.slice(mark.length, -mark.length).trim();
        changed = true;
        break;
      }
    }
    if (changed) continue;
    const withoutMarkup = working.replace(DOWNLOAD_LEADING_MARKUP_PATTERN, "");
    if (withoutMarkup !== working) {
      working = withoutMarkup.trim();
      changed = true;
    }
  }
  return working;
}

function looksLikeListedDirectivePath(cleanedLine) {
  if (!cleanedLine) return false;
  if (cleanedLine.startsWith("#")) return false;
  if (/^https?:\/\//i.test(cleanedLine)) return false;
  return true;
}

function splitDirectivePaths(value) {
  return value
    .split(",")
    .map((entry) => entry.trim().replace(/^['"`*_\s]+|['"`*_\s]+$/g, ""))
    .filter(Boolean);
}

function validDirectivePaths(paths) {
  return paths.length > 0 && paths.every((value) => !/^(?:#|https?:\/\/)/i.test(value));
}

function downloadRequestDirective(text) {
  const lines = String(text || "").split(/\r?\n/);
  for (let index = 0; index < lines.length; index += 1) {
    const cleaned = unwrappedDirectiveLine(lines[index]);
    const inlineMatch = cleaned.match(DOWNLOAD_INLINE_PATTERN);
    if (inlineMatch) {
      const paths = splitDirectivePaths(inlineMatch[1]);
      if (validDirectivePaths(paths)) return { line: cleaned, paths };
      continue;
    }
    if (DOWNLOAD_HEADER_PATTERN.test(cleaned)) {
      const paths = [];
      let cursor = index + 1;
      while (cursor < lines.length) {
        const candidate = unwrappedDirectiveLine(lines[cursor]);
        if (!looksLikeListedDirectivePath(candidate)) break;
        paths.push(...splitDirectivePaths(candidate));
        cursor += 1;
      }
      if (validDirectivePaths(paths)) return { line: cleaned, paths };
    }
  }
  return null;
}

async function watchResponse(requestId, baseline, requireDownloadRequest = false) {
  const token = ++responseWatchToken;
  let stableText = "";
  let stableCycles = 0;
  for (let cycle = 0; cycle < 2400 && token === responseWatchToken; cycle += 1) {
    await sleep(500);
    const messages = assistantMessages();
    if (!isNewAssistantResponse(messages, baseline)) continue;
    const latest = messages.at(-1);
    const text = responseText(latest);
    if (!text) continue;
    if (text === stableText) stableCycles += 1;
    else {
      stableText = text;
      stableCycles = 0;
    }
    if (generationInProgress() || stableCycles < RESPONSE_STABLE_CYCLES) continue;
    if (requireDownloadRequest && !downloadRequestDirective(text)) continue;

    const bridgeResult = await submitAssistantResponse(requestId, text);
    await handleBridgeResponseAction(requestId, latest, bridgeResult);
    return;
  }
  if (token === responseWatchToken) {
    const detail = requireDownloadRequest ? " con una direttiva #scarica completa" : "";
    throw new Error(`${providerName()} non ha completato una risposta utilizzabile${detail} entro il tempo previsto.`);
  }
}

async function sendPrompt(requestId, prompt, requireDownloadRequest = true) {
  currentRequestId = requestId;
  passiveDirectiveText = "";
  passiveDirectiveStableCycles = 0;
  const baseline = assistantResponseBaseline();
  setComposerText(prompt);
  await sendComposer();
  void watchResponse(requestId, baseline, requireDownloadRequest).catch((error) => {
    console.error("BridgAI response automation:", error);
    chrome.runtime.sendMessage({
      type: "BRIDGAI_AUTOMATION_ERROR",
      requestId,
      message: error.message
    }).catch(() => undefined);
  });
}

function fileInput() {
  const inputs = providerApi
    .queryAll(document, ['input[type="file"]'])
    .filter((input) => !input.disabled);
  return inputs.find((input) => /(?:application\/zip|\.zip)/i.test(input.accept || "")) ||
    inputs.find((input) => composerRoots().some((root) => root !== document && root.contains(input))) ||
    inputs.find((input) => /\*/.test(input.accept || "")) ||
    inputs[0] ||
    null;
}

function attachmentAction() {
  const selected = providerApi.first(document, currentProvider.attachmentButtonSelectors, enabledControl);
  if (selected) return selected;
  const attachmentWords = /attach|allega|upload|carica|add (?:files?|content)|aggiungi (?:file|contenuto)/i;
  return [...document.querySelectorAll("button, [role=button]")]
    .find((button) => enabledControl(button) && attachmentWords.test(controlText(button))) || null;
}

function uploadMenuAction() {
  const uploadWords = /add files?|add files or photos|upload files?|allega|carica files?|aggiungi files?/i;
  return [...document.querySelectorAll('[role="menuitem"], [role="option"], button')]
    .find((element) => enabledControl(element) && uploadWords.test(controlText(element))) || null;
}

async function findFileInput() {
  let input = fileInput();
  if (input) return input;
  const attach = attachmentAction();
  attach?.click();
  let menuClicked = false;
  for (let attempt = 0; attempt < 50; attempt += 1) {
    await sleep(200);
    input = fileInput();
    if (input) return input;
    if (!menuClicked) {
      const menuAction = uploadMenuAction();
      if (menuAction && menuAction !== attach) {
        menuAction.click();
        menuClicked = true;
      }
    }
  }
  throw new Error(`Controllo allegati ${providerName()} non trovato.`);
}

function attachmentRegion() {
  const editor = composer();
  return (
    editor?.closest?.("form") ||
    editor?.closest?.("fieldset") ||
    editor?.parentElement?.parentElement?.parentElement ||
    editor?.parentElement?.parentElement ||
    document.body
  );
}

function attachmentIndicators(root = attachmentRegion()) {
  const genericSelectors = [
    '[data-testid*="attachment" i]',
    '[data-testid*="file" i]',
    '[data-test-id*="attachment" i]',
    '[aria-label*="attachment" i]',
    '[aria-label*="allegat" i]',
    'button[aria-label*="remove file" i]',
    'button[aria-label*="rimuovi file" i]'
  ];
  const local = providerApi.queryAll(root || document, [
    ...currentProvider.attachmentIndicatorSelectors,
    ...genericSelectors
  ]);
  return local.filter(visible);
}

function attachmentUploadInProgress(root = attachmentRegion()) {
  if (!root) return false;
  if (root.querySelector('[role="progressbar"], [data-state="loading"], [data-state="uploading"]')) {
    return true;
  }
  const text = String(root.innerText || root.textContent || "").toLowerCase();
  return /uploading|caricamento in corso|allegato in caricamento|processing file/.test(text);
}

function attachmentUploadFailed(root = attachmentRegion()) {
  const text = String(root?.innerText || root?.textContent || "").toLowerCase();
  return /upload failed|failed to upload|caricamento non riuscito|errore.*allegat|couldn.t upload/.test(text);
}

async function waitForAttachmentReady(filename, previousIndicatorCount, timeoutMilliseconds = 120000) {
  const expected = String(filename || "").trim().toLowerCase();
  const deadline = Date.now() + timeoutMilliseconds;
  let stableCycles = 0;
  while (Date.now() < deadline) {
    const root = attachmentRegion();
    if (attachmentUploadFailed(root)) {
      throw new Error(`${providerName()} ha segnalato un errore durante il caricamento del contesto.`);
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
  throw new Error(`${providerName()} non ha completato il caricamento del contesto entro il tempo previsto.`);
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
  assertMessageProvider(message);
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
  await sendPrompt(message.requestId, message.followupPrompt, false);
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "BRIDGAI_SEND_PROMPT") {
    Promise.resolve()
      .then(() => assertMessageProvider(message))
      .then(() => sendPrompt(message.requestId, message.prompt))
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

function requestImmediatePoll() {
  if (document.visibilityState !== "visible") return;
  chrome.runtime.sendMessage({ type: "BRIDGAI_POLL_NOW" }).catch(() => {});
}

setInterval(() => {
  requestImmediatePoll();
  if (passiveDirectiveWatchRunning) return;
  passiveDirectiveWatchRunning = true;
  void watchPassiveDownloadDirective().catch((error) => {
    console.error("BridgAI passive response automation:", error);
    chrome.runtime.sendMessage({
      type: "BRIDGAI_AUTOMATION_ERROR",
      requestId: currentRequestId,
      message: error.message
    }).catch(() => undefined);
  }).finally(() => {
    passiveDirectiveWatchRunning = false;
  });
}, CONTENT_HEARTBEAT_MS);

document.addEventListener("visibilitychange", requestImmediatePoll);
requestImmediatePoll();
})();
