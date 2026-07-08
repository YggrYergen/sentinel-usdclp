// SENTINEL Chat section — model/effort/web-search/thinking controls with
// mutual exclusivity in ONE request-builder function, POST /chat, GET /models.
(function () {
  "use strict";

  let currentInstrument = "usdclp";
  let modelsCatalog = null;

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

  function appendMessage(list, role, text) {
    const li = document.createElement("li");
    li.className = `chat-msg chat-${role}`;
    li.textContent = `${role === "user" ? "You" : "SENTINEL"}: ${text}`;
    list.appendChild(li);
    list.scrollTop = list.scrollHeight;
  }

  async function sendMessage(input, list, controls) {
    const question = input.value.trim();
    if (!question) return;
    appendMessage(list, "user", question);
    input.value = "";
    const req = buildChatRequest(question, controls);
    try {
      const resp = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      });
      const body = await resp.json();
      appendMessage(list, "assistant", body.content || body.error || "(no response)");
    } catch (e) {
      appendMessage(list, "assistant", "(request failed)");
    }
  }

  async function buildChatSection() {
    const section = document.getElementById("section-chat");
    section.innerHTML = "";
    modelsCatalog = modelsCatalog || (await loadModels());

    const header = document.createElement("div");
    header.style.cssText = "display:flex;gap:0.5rem;align-items:center;margin-bottom:0.6rem;flex-wrap:wrap;";

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
      get model() { return modelSelect.value; },
      get effort() { return effortSelect.value; },
      get webSearch() { return webSearchToggle.checked; },
      get thinking() { return thinkingToggle.checked; },
    };

    sendBtn.addEventListener("click", () => sendMessage(input, list, controls));
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") sendMessage(input, list, controls); });

    inputRow.appendChild(input);
    inputRow.appendChild(sendBtn);

    section.appendChild(header);
    section.appendChild(list);
    section.appendChild(inputRow);
  }

  window.addEventListener("sentinel:section", (evt) => {
    if (evt.detail === "chat") buildChatSection();
  });
  document.addEventListener("DOMContentLoaded", buildChatSection);

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.buildChatRequest = buildChatRequest;
})();
