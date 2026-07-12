// SENTINEL Chat section — model/effort/web-search/thinking controls with
// mutual exclusivity in ONE request-builder function, POST /chat, GET /models.
//
// Task A9 (CT-6 frontend, Wave A lane B) adds on top of the above: a model
// picker sourced from GET /api/llm/models (marks the `default:true` entry
// selected), an inline passcode unlock for `gated:true` models (POST
// /api/llm/unlock — the passcode itself is NEVER known client-side, only
// typed by the user and forwarded), and a usage meter (GET /api/llm/usage)
// refreshed after every /chat message. All llm/* + /chat fetches use
// `credentials: "same-origin"` so the httponly `sentinel_session` cookie the
// server sets rides along automatically.
(function () {
  "use strict";

  let currentInstrument = "usdclp";
  let modelsCatalog = null;
  let llmModelsCatalog = [];
  let selectedLlmModelId = null;
  let unlockedModelIds = new Set();

  function buildChatRequest(question, controls) {
    // Mutual exclusivity: enabling web_search disables thinking and vice
    // versa (spec §4.1) — enforced HERE, the single request-builder.
    const req = {
      question,
      instrument: currentInstrument,
      model: controls.model,
      effort: controls.effort,
    };
    if (controls.webSearch) {
      req.web_search = true;
      req.thinking = false;
    } else if (controls.thinking) {
      req.thinking = true;
      req.web_search = false;
    } else {
      req.web_search = false;
      req.thinking = false;
    }
    return req;
  }

  async function loadModels() {
    try {
      const resp = await fetch("/models");
      if (resp.status !== 200) return null;
      return await resp.json();
    } catch (e) {
      return null;
    }
  }

  // ---- CT-6: /api/llm/models, /api/llm/unlock, /api/llm/usage ----

  async function loadLlmModels() {
    try {
      const resp = await fetch("/api/llm/models", { credentials: "same-origin" });
      if (resp.status !== 200) return [];
      return await resp.json();
    } catch (e) {
      return [];
    }
  }

  async function postUnlock(code) {
    try {
      const resp = await fetch("/api/llm/unlock", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      return await resp.json();
    } catch (e) {
      return { ok: false };
    }
  }

  async function loadLlmUsage() {
    try {
      const resp = await fetch("/api/llm/usage", { credentials: "same-origin" });
      if (resp.status !== 200) return null;
      return await resp.json();
    } catch (e) {
      return null;
    }
  }

  function renderUsageMeter(meterEl, usage) {
    if (!usage) return;
    const inTok = usage.session_tokens_in ?? 0;
    const outTok = usage.session_tokens_out ?? 0;
    const usd = usage.est_usd ?? 0;
    meterEl.textContent = `tokens in: ${inTok} · tokens out: ${outTok} · est. cost: $${Number(usd).toFixed(4)}`;
  }

  async function refreshUsageMeter(meterEl) {
    const usage = await loadLlmUsage();
    renderUsageMeter(meterEl, usage);
  }

  function triggerShake(el) {
    el.classList.remove("shake-error");
    // Force reflow so re-adding the class restarts the animation on repeat failures.
    void el.offsetWidth;
    el.classList.add("shake-error");
  }

  function buildUnlockPrompt(modelId, onUnlocked) {
    const wrap = document.createElement("div");
    wrap.className = "llm-unlock-prompt";

    const label = document.createElement("span");
    label.className = "llm-unlock-label";
    label.textContent = "Passcode:";

    const codeInput = document.createElement("input");
    codeInput.type = "password";
    codeInput.className = "llm-unlock-input";
    codeInput.placeholder = "gated model — enter passcode";

    const unlockBtn = document.createElement("button");
    unlockBtn.type = "button";
    unlockBtn.className = "llm-unlock-btn";
    unlockBtn.textContent = "Unlock";

    const errorEl = document.createElement("span");
    errorEl.className = "llm-unlock-error";

    async function tryUnlock() {
      const code = codeInput.value;
      const result = await postUnlock(code);
      if (result && result.ok) {
        unlockedModelIds.add(modelId);
        errorEl.textContent = "";
        wrap.remove();
        onUnlocked();
      } else {
        errorEl.textContent = "incorrect passcode";
        triggerShake(codeInput);
      }
    }

    unlockBtn.addEventListener("click", tryUnlock);
    codeInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") tryUnlock();
    });

    wrap.appendChild(label);
    wrap.appendChild(codeInput);
    wrap.appendChild(unlockBtn);
    wrap.appendChild(errorEl);
    return wrap;
  }

  function appendMessage(list, role, text) {
    const li = document.createElement("li");
    li.className = `chat-msg chat-${role}`;
    li.textContent = `${role === "user" ? "You" : "SENTINEL"}: ${text}`;
    list.appendChild(li);
    list.scrollTop = list.scrollHeight;
  }

  async function sendMessage(input, list, controls, meterEl, onGatedLocked) {
    const question = input.value.trim();
    if (!question) return;
    appendMessage(list, "user", question);
    input.value = "";
    const req = buildChatRequest(question, controls);
    try {
      const resp = await fetch("/chat", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      });
      const body = await resp.json();
      if (resp.status === 403 && body && body.error === "gated_model_locked") {
        // Server re-confirmed the gate (e.g. session expired mid-flight) —
        // fall back to the same inline unlock prompt without crashing.
        appendMessage(list, "assistant", "(model locked — enter passcode to unlock)");
        if (onGatedLocked) onGatedLocked();
        return;
      }
      appendMessage(list, "assistant", body.content || body.error || "(no response)");
    } catch (e) {
      appendMessage(list, "assistant", "(request failed)");
    } finally {
      if (meterEl) refreshUsageMeter(meterEl);
    }
  }

  async function buildChatSection() {
    const section = document.getElementById("section-chat");
    section.innerHTML = "";
    modelsCatalog = modelsCatalog || (await loadModels());
    llmModelsCatalog = await loadLlmModels();

    const header = document.createElement("div");
    header.style.cssText = "display:flex;gap:0.5rem;align-items:center;margin-bottom:0.6rem;flex-wrap:wrap;";

    // ---- CT-6 model picker (GET /api/llm/models) ----
    const llmSelect = document.createElement("select");
    llmSelect.className = "llm-model-select";
    llmModelsCatalog.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = m.gated ? `${m.label} (gated)` : m.label;
      opt.dataset.gated = m.gated ? "1" : "";
      if (m.default) {
        opt.selected = true;
        selectedLlmModelId = m.id;
      }
      llmSelect.appendChild(opt);
    });
    if (!selectedLlmModelId && llmModelsCatalog.length) {
      selectedLlmModelId = llmModelsCatalog[0].id;
    }

    const unlockSlot = document.createElement("div");
    unlockSlot.className = "llm-unlock-slot";

    function modelById(id) {
      return llmModelsCatalog.find((m) => m.id === id) || null;
    }

    function showUnlockPromptFor(modelId) {
      unlockSlot.innerHTML = "";
      unlockSlot.appendChild(
        buildUnlockPrompt(modelId, () => {
          unlockSlot.innerHTML = "";
        })
      );
    }

    llmSelect.addEventListener("change", () => {
      const modelId = llmSelect.value;
      selectedLlmModelId = modelId;
      const model = modelById(modelId);
      unlockSlot.innerHTML = "";
      if (model && model.gated && !unlockedModelIds.has(modelId)) {
        showUnlockPromptFor(modelId);
      }
    });

    const modelSelect = document.createElement("select");
    (modelsCatalog?.models || [{ key: "sonnet", label: "Claude Sonnet" }]).forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.key;
      opt.textContent = m.label;
      modelSelect.appendChild(opt);
    });

    const effortSelect = document.createElement("select");
    (modelsCatalog?.effort_levels || ["low", "medium", "high"]).forEach((lvl) => {
      const opt = document.createElement("option");
      opt.value = lvl;
      opt.textContent = lvl;
      if (lvl === "medium") opt.selected = true;
      effortSelect.appendChild(opt);
    });

    const webSearchToggle = document.createElement("input");
    webSearchToggle.type = "checkbox";
    webSearchToggle.disabled = !(modelsCatalog?.web_search_available);
    const webSearchLabel = document.createElement("label");
    webSearchLabel.textContent = " web-search";
    webSearchLabel.prepend(webSearchToggle);

    const thinkingToggle = document.createElement("input");
    thinkingToggle.type = "checkbox";
    thinkingToggle.disabled = !(modelsCatalog?.thinking_available);
    const thinkingLabel = document.createElement("label");
    thinkingLabel.textContent = " extended-thinking";
    thinkingLabel.prepend(thinkingToggle);

    // Mutual exclusivity in the UI itself (mirrors buildChatRequest's logic).
    webSearchToggle.addEventListener("change", () => {
      if (webSearchToggle.checked) { thinkingToggle.checked = false; }
    });
    thinkingToggle.addEventListener("change", () => {
      if (thinkingToggle.checked) { webSearchToggle.checked = false; }
    });

    header.appendChild(llmSelect);
    header.appendChild(modelSelect);
    header.appendChild(effortSelect);
    header.appendChild(webSearchLabel);
    header.appendChild(thinkingLabel);
    if (!(modelsCatalog?.web_search_available) || !(modelsCatalog?.thinking_available)) {
      const note = document.createElement("span");
      note.className = "chip";
      note.textContent = "streaming/web-search/thinking: gated (P5 not fully wired)";
      header.appendChild(note);
    }

    const meterEl = document.createElement("div");
    meterEl.className = "llm-usage-meter";
    meterEl.textContent = "tokens in: 0 · tokens out: 0 · est. cost: $0.0000";

    const list = document.createElement("ul");
    list.id = "chat-history";
    list.style.cssText = "list-style:none;margin:0;padding:0;height:60vh;overflow-y:auto;border:1px solid var(--fx-border);border-radius:8px;padding:0.6rem;";

    const inputRow = document.createElement("div");
    inputRow.style.cssText = "display:flex;gap:0.4rem;margin-top:0.6rem;";
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Ask about the live snapshot…";
    input.style.cssText = "flex:1;background:var(--fx-bg);color:var(--fx-text);border:1px solid var(--fx-border);border-radius:6px;padding:0.4rem 0.6rem;";
    const sendBtn = document.createElement("button");
    sendBtn.textContent = "Send";
    sendBtn.style.cssText = "background:transparent;color:var(--fx-accent);border:1px solid var(--fx-accent);border-radius:6px;padding:0.4rem 0.9rem;cursor:pointer;";

    const controls = {
      get model() { return selectedLlmModelId || modelSelect.value; },
      get effort() { return effortSelect.value; },
      get webSearch() { return webSearchToggle.checked; },
      get thinking() { return thinkingToggle.checked; },
    };

    function onGatedLocked() {
      if (selectedLlmModelId) showUnlockPromptFor(selectedLlmModelId);
    }

    sendBtn.addEventListener("click", () => sendMessage(input, list, controls, meterEl, onGatedLocked));
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") sendMessage(input, list, controls, meterEl, onGatedLocked);
    });

    inputRow.appendChild(input);
    inputRow.appendChild(sendBtn);

    section.appendChild(header);
    section.appendChild(unlockSlot);
    section.appendChild(meterEl);
    section.appendChild(list);
    section.appendChild(inputRow);

    refreshUsageMeter(meterEl);
  }

  window.addEventListener("sentinel:section", (evt) => {
    if (evt.detail === "chat") buildChatSection();
  });
  document.addEventListener("DOMContentLoaded", buildChatSection);

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.buildChatRequest = buildChatRequest;
})();
