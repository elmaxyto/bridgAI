const BRIDGAI_PENDING_DOWNLOAD_KEY = "bridgaiPendingZipDownload";
const BRIDGAI_PENDING_DOWNLOAD_LIFETIME = 3 * 60 * 1000;
const BRIDGAI_DOWNLOAD_NOTIFY_ATTEMPTS = 3;
const BRIDGAI_DOWNLOAD_START_TOLERANCE = 5000;

self.BridgAIDownloadTracking = {
  create({
    getConfig,
    bridgeBaseUrl,
    jsonRequest,
    normalizedFilename,
    downloadFilename,
    reportError
  }) {
    let notifying = false;

    async function loadPending() {
      const stored = await chrome.storage.session.get(BRIDGAI_PENDING_DOWNLOAD_KEY);
      const pending = stored[BRIDGAI_PENDING_DOWNLOAD_KEY];
      if (!pending || Number(pending.expiresAt || 0) < Date.now()) {
        await chrome.storage.session.remove(BRIDGAI_PENDING_DOWNLOAD_KEY);
        return null;
      }
      return pending;
    }

    async function savePending(pending) {
      await chrome.storage.session.set({ [BRIDGAI_PENDING_DOWNLOAD_KEY]: pending });
      return pending;
    }

    async function clear(requestId = "") {
      const pending = await loadPending();
      if (!pending || (requestId && pending.requestId !== requestId)) return;
      await chrome.storage.session.remove(BRIDGAI_PENDING_DOWNLOAD_KEY);
    }

    async function expect(requestId, filename = "") {
      if (!requestId) return null;
      const now = Date.now();
      return savePending({
        requestId,
        filename: normalizedFilename(filename),
        downloadId: null,
        attempts: 0,
        armedAt: now,
        expiresAt: now + BRIDGAI_PENDING_DOWNLOAD_LIFETIME
      });
    }

    async function track(downloadId, requestId, filename = "") {
      const existing = await loadPending();
      const pending = existing?.requestId === requestId
        ? existing
        : await expect(requestId, filename);
      if (!pending) return null;
      pending.downloadId = downloadId;
      if (filename) pending.filename = normalizedFilename(filename);
      pending.expiresAt = Date.now() + BRIDGAI_PENDING_DOWNLOAD_LIFETIME;
      return savePending(pending);
    }

    function trustedDownloadSource(item) {
      const candidates = [item.url, item.finalUrl, item.referrer]
        .map((value) => String(value || "").trim())
        .filter(Boolean);
      return candidates.some((value) => {
        try {
          return self.BridgAIWebAIProviders.trustedDownloadUrl(value);
        } catch (_error) {
          return false;
        }
      });
    }

    function startedAfterExpectation(item, pending) {
      const startedAt = Date.parse(String(item.startTime || ""));
      if (!Number.isFinite(startedAt)) return true;
      return startedAt >= Number(pending.armedAt || 0) - BRIDGAI_DOWNLOAD_START_TOLERANCE;
    }

    function isExpectedDownload(item, pending) {
      if (pending.downloadId !== null) return Number(item.id) === Number(pending.downloadId);
      if (!startedAfterExpectation(item, pending) || !trustedDownloadSource(item)) return false;

      const expected = normalizedFilename(pending.filename);
      const actual = normalizedFilename(item.filename);
      if (expected !== "bridgai_update.zip" && actual === expected) return true;

      const details = [item.url, item.finalUrl, item.referrer, item.filename]
        .map((value) => String(value || ""))
        .join(" ");
      return /\.zip(?:\b|[?#])/i.test(details) ||
        String(item.mime || "").toLowerCase() === "application/zip";
    }

    async function created(item) {
      const pending = await loadPending();
      if (!pending || !isExpectedDownload(item, pending)) return;
      await track(item.id, pending.requestId, item.filename || pending.filename);
    }

    async function determineFilename(item, suggest) {
      const pending = await loadPending();
      if (!pending || !isExpectedDownload(item, pending)) {
        suggest();
        return;
      }
      const current = await getConfig();
      const filename = downloadFilename(
        current,
        item.filename || pending.filename || "bridgai_update.zip"
      );
      suggest({ filename, conflictAction: "uniquify" });
    }

    function localBridge(current) {
      const hostname = new URL(bridgeBaseUrl(current)).hostname.toLowerCase();
      return hostname === "127.0.0.1" || hostname === "localhost" || hostname === "::1";
    }

    async function notify(item, pending) {
      const current = await getConfig();
      if (!localBridge(current)) {
        throw new Error(
          "Il download locale di fallback non può essere trasferito a un server BridgAI remoto."
        );
      }
      if (!item.filename) {
        throw new Error("Chrome non ha comunicato il percorso dello ZIP scaricato.");
      }
      const payload = await jsonRequest("/api/extension/download-complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_id: pending.requestId,
          path: item.filename,
          filename: pending.filename,
          download_id: item.id
        })
      });
      if (["update_ready", "result_ready"].includes(payload.action)) {
        await clear(pending.requestId);
      }
    }

    async function failPending(pending, message) {
      await clear(pending.requestId);
      if (typeof reportError === "function") {
        await reportError(pending.requestId, message).catch(() => undefined);
      }
    }

    async function retry() {
      if (notifying) return;
      const pending = await loadPending();
      if (!pending || pending.downloadId === null) return;
      const matches = await chrome.downloads.search({ id: pending.downloadId });
      const item = matches[0];
      if (!item || item.state === "in_progress") return;
      if (item.state === "interrupted") {
        await failPending(pending, "Chrome ha interrotto il download dello ZIP finale.");
        return;
      }
      notifying = true;
      try {
        await notify(item, pending);
      } catch (error) {
        pending.attempts = Number(pending.attempts || 0) + 1;
        if (pending.attempts >= BRIDGAI_DOWNLOAD_NOTIFY_ATTEMPTS) {
          await failPending(pending, error.message);
        } else {
          await savePending(pending);
        }
        console.debug("BridgAI download completion:", error.message);
      } finally {
        notifying = false;
      }
    }

    chrome.downloads.onDeterminingFilename.addListener((item, suggest) => {
      void determineFilename(item, suggest).catch((error) => {
        console.debug("BridgAI download filename:", error.message);
        suggest();
      });
      return true;
    });
    chrome.downloads.onCreated.addListener((item) => {
      void created(item).catch((error) => console.debug("BridgAI download created:", error.message));
    });
    chrome.downloads.onChanged.addListener((delta) => {
      if (["complete", "interrupted"].includes(delta.state?.current)) {
        void retry().catch((error) => console.debug("BridgAI download changed:", error.message));
      }
    });

    return { expect, track, clear, retry };
  }
};
