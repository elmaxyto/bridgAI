(function initializeBridgAIProviders(globalScope) {
  const PROVIDERS = Object.freeze({
    chatgpt: Object.freeze({
      id: "chatgpt",
      label: "ChatGPT",
      url: "https://chatgpt.com/",
      matches: Object.freeze(["https://chatgpt.com/*"]),
      hosts: Object.freeze(["chatgpt.com"]),
      trustedDownloadHosts: Object.freeze(["chatgpt.com", ".oaiusercontent.com"]),
      assistantSelectors: Object.freeze([
        '[data-message-author-role="assistant"]'
      ]),
      composerSelectors: Object.freeze([
        "#prompt-textarea",
        'textarea[data-id="root"]',
        '[contenteditable="true"][data-lexical-editor="true"]',
        "form textarea"
      ]),
      sendButtonSelectors: Object.freeze([
        '[data-testid="send-button"]',
        'button[aria-label*="send" i]',
        'button[aria-label*="invia" i]'
      ]),
      stopButtonSelectors: Object.freeze([
        '[data-testid="stop-button"]',
        '[data-testid*="stop-generating"]'
      ]),
      streamingSelectors: Object.freeze([
        '[data-message-author-role="assistant"][data-message-streaming="true"]',
        '[data-testid*="streaming" i]'
      ]),
      attachmentButtonSelectors: Object.freeze([
        'button[aria-label*="attach" i]',
        'button[aria-label*="allega" i]',
        'button[aria-label*="upload" i]'
      ]),
      attachmentIndicatorSelectors: Object.freeze([
        '[data-testid*="attachment" i]',
        '[data-testid*="file" i]'
      ])
    }),
    claude: Object.freeze({
      id: "claude",
      label: "Claude",
      url: "https://claude.ai/new",
      matches: Object.freeze(["https://claude.ai/*"]),
      hosts: Object.freeze(["claude.ai"]),
      trustedDownloadHosts: Object.freeze([
        "claude.ai",
        ".claude.ai",
        ".anthropic.com"
      ]),
      assistantSelectors: Object.freeze([
        '[data-testid="assistant-message"]',
        '[data-testid^="assistant-message"]',
        '[data-is-streaming]',
        '[class*="font-claude-response"]',
        '[class*="font-claude-message"]'
      ]),
      composerSelectors: Object.freeze([
        '[contenteditable="true"][data-testid="chat-input"]',
        'div.ProseMirror[contenteditable="true"]',
        'fieldset [contenteditable="true"]',
        'form [contenteditable="true"]',
        "form textarea"
      ]),
      sendButtonSelectors: Object.freeze([
        '[data-testid="send-button"]',
        'button[aria-label*="send message" i]',
        'button[aria-label*="send" i]',
        'button[type="submit"]'
      ]),
      stopButtonSelectors: Object.freeze([
        'button[aria-label*="stop response" i]',
        'button[aria-label*="stop" i]',
        '[data-testid*="stop" i]'
      ]),
      streamingSelectors: Object.freeze([
        '[data-is-streaming="true"]',
        '[data-state="streaming"]'
      ]),
      attachmentButtonSelectors: Object.freeze([
        'button[aria-label*="add files" i]',
        'button[aria-label*="attach" i]',
        'button[aria-label*="upload" i]',
        'button[aria-label="Add content"]'
      ]),
      attachmentIndicatorSelectors: Object.freeze([
        '[data-testid*="attachment" i]',
        '[data-testid*="file" i]',
        '[aria-label*="remove file" i]'
      ])
    }),
    gemini: Object.freeze({
      id: "gemini",
      label: "Gemini",
      url: "https://gemini.google.com/app",
      matches: Object.freeze(["https://gemini.google.com/*"]),
      hosts: Object.freeze(["gemini.google.com"]),
      trustedDownloadHosts: Object.freeze([
        "gemini.google.com",
        ".googleusercontent.com"
      ]),
      assistantSelectors: Object.freeze([
        "model-response",
        '[data-test-id="model-response"]',
        '[data-testid="model-response"]'
      ]),
      composerSelectors: Object.freeze([
        'rich-textarea [contenteditable="true"]',
        '.ql-editor[contenteditable="true"]',
        '[contenteditable="true"][aria-label*="prompt" i]',
        'textarea[aria-label*="prompt" i]',
        "form textarea"
      ]),
      sendButtonSelectors: Object.freeze([
        'button[aria-label*="send message" i]',
        'button[aria-label*="send" i]',
        'button[mattooltip*="send" i]',
        "button.send-button"
      ]),
      stopButtonSelectors: Object.freeze([
        'button[aria-label*="stop response" i]',
        'button[aria-label*="stop" i]',
        'button[mattooltip*="stop" i]'
      ]),
      streamingSelectors: Object.freeze([
        'model-response[is-streaming]',
        'model-response[data-is-streaming="true"]',
        '[data-state="streaming"]'
      ]),
      attachmentButtonSelectors: Object.freeze([
        'button[aria-label*="upload" i]',
        'button[aria-label*="add file" i]',
        'button[aria-label*="open upload" i]',
        'button[mattooltip*="upload" i]'
      ]),
      attachmentIndicatorSelectors: Object.freeze([
        '[data-test-id*="attachment" i]',
        '[data-testid*="attachment" i]',
        '[class*="attachment"]'
      ])
    })
  });

  const DEFAULT_PROVIDER = "chatgpt";

  function normalize(value) {
    const candidate = String(value || "").trim().toLowerCase();
    if (!candidate || candidate === "custom") return DEFAULT_PROVIDER;
    if (!Object.prototype.hasOwnProperty.call(PROVIDERS, candidate)) {
      throw new Error(`Provider AI Web non supportato: ${candidate}.`);
    }
    return candidate;
  }

  function requireKnown(value) {
    const candidate = String(value || "").trim().toLowerCase();
    if (!candidate || candidate === "custom") {
      throw new Error("La richiesta BridgAI non specifica un provider AI Web supportato.");
    }
    if (!Object.prototype.hasOwnProperty.call(PROVIDERS, candidate)) {
      throw new Error(`Provider AI Web non supportato: ${candidate}.`);
    }
    return candidate;
  }

  function get(value) {
    return PROVIDERS[normalize(value)];
  }

  function fromLocation(locationValue = globalScope.location) {
    const hostname = String(locationValue?.hostname || "").toLowerCase();
    const provider = Object.values(PROVIDERS).find((item) => item.hosts.includes(hostname));
    if (!provider) throw new Error(`Pagina AI Web non supportata: ${hostname || "origine sconosciuta"}.`);
    return provider;
  }

  function queryAll(root, selectors) {
    const found = [];
    for (const selector of selectors || []) {
      try {
        for (const element of root.querySelectorAll(selector)) {
          if (!found.includes(element)) found.push(element);
        }
      } catch (_error) {
        // Ignore a selector unsupported by an older Chromium build.
      }
    }
    return found;
  }

  function first(root, selectors, predicate = null) {
    const candidates = queryAll(root, selectors);
    if (typeof predicate === "function") {
      return candidates.find(predicate) || null;
    }
    return candidates[0] || null;
  }

  function downloadHostname(value) {
    const url = new URL(String(value || ""));
    if (url.protocol === "blob:") {
      return new URL(url.pathname).hostname.toLowerCase();
    }
    return url.hostname.toLowerCase();
  }

  function trustedHost(provider, hostname) {
    return provider.trustedDownloadHosts.some((trusted) =>
      trusted.startsWith(".") ? hostname.endsWith(trusted) : hostname === trusted
    );
  }

  function trustedDownloadUrlFor(providerValue, value) {
    try {
      const provider = get(requireKnown(providerValue));
      return trustedHost(provider, downloadHostname(value));
    } catch (_error) {
      return false;
    }
  }

  function trustedDownloadUrl(value) {
    try {
      const hostname = downloadHostname(value);
      return Object.values(PROVIDERS).some((provider) => trustedHost(provider, hostname));
    } catch (_error) {
      return false;
    }
  }

  globalScope.BridgAIWebAIProviders = Object.freeze({
    DEFAULT_PROVIDER,
    ids: Object.freeze(Object.keys(PROVIDERS)),
    normalize,
    requireKnown,
    get,
    fromLocation,
    queryAll,
    first,
    trustedDownloadUrlFor,
    trustedDownloadUrl
  });
})(globalThis);
