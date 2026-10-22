(function () {
  "use strict";

  var launcher = document.getElementById("chatLauncher");
  var panel = document.getElementById("chatPanel");
  var body = document.getElementById("chatBody");
  var form = document.getElementById("chatForm");
  var input = document.getElementById("chatInput");
  var sendBtn = document.getElementById("chatSend");
  var resetBtn = document.getElementById("chatReset");
  var closeBtn = document.getElementById("chatClose");
  var statusEl = document.getElementById("chatStatus");

  var SESSION_KEY = "tellen_chat_session_id";
  var HISTORY_KEY = "tellen_chat_history";
  var sending = false;

  function newSessionId() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return "sess-" + Date.now() + "-" + Math.random().toString(16).slice(2);
  }

  function getSessionId() {
    var id = sessionStorage.getItem(SESSION_KEY);
    if (!id) {
      id = newSessionId();
      sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
  }

  function loadHistory() {
    try {
      return JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]");
    } catch (_) {
      return [];
    }
  }

  function saveHistory(history) {
    try {
      // Keep the stored history bounded so sessionStorage can't grow unbounded.
      sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(-40)));
    } catch (_) { /* storage unavailable — conversation still works, just won't persist across reload */ }
  }

  var WELCOME = "Hi, I'm the Tellen AI demo assistant. Ask me about pricing, services, or how an AI receptionist would work for your business. This is a demo — for a real deployment we'll walk through your exact workflow.";

  function addMessage(role, text, opts) {
    opts = opts || {};
    var el = document.createElement("div");
    el.className = "chat-msg " + role;
    el.textContent = text;
    if (opts.retry) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "retry-btn";
      btn.textContent = "Retry";
      btn.addEventListener("click", opts.retry);
      el.appendChild(document.createElement("br"));
      el.appendChild(btn);
    }
    body.appendChild(el);
    body.scrollTop = body.scrollHeight;
    return el;
  }

  function addTyping() {
    var el = document.createElement("div");
    el.className = "chat-typing";
    el.id = "chatTyping";
    el.innerHTML = "<span></span><span></span><span></span>";
    body.appendChild(el);
    body.scrollTop = body.scrollHeight;
    return el;
  }

  function removeTyping() {
    var el = document.getElementById("chatTyping");
    if (el) el.remove();
  }

  function renderHistory() {
    body.innerHTML = "";
    var history = loadHistory();
    if (history.length === 0) {
      addMessage("bot", WELCOME);
    } else {
      history.forEach(function (m) {
        addMessage(m.role, m.text);
      });
    }
  }

  function openPanel() {
    panel.hidden = false;
    launcher.hidden = true;
    launcher.setAttribute("aria-expanded", "true");
    renderHistory();
    input.focus();
  }

  function closePanel() {
    panel.hidden = true;
    launcher.hidden = false;
    launcher.setAttribute("aria-expanded", "false");
  }

  launcher.addEventListener("click", openPanel);
  closeBtn.addEventListener("click", closePanel);

  resetBtn.addEventListener("click", function () {
    sessionStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(HISTORY_KEY);
    getSessionId();
    body.innerHTML = "";
    addMessage("bot", WELCOME);
    statusEl.textContent = "Online — demo";
  });

  function autoGrow() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 90) + "px";
  }
  input.addEventListener("input", autoGrow);

  function sendMessage(text) {
    if (sending) return;
    sending = true;
    sendBtn.disabled = true;
    statusEl.textContent = "Thinking…";

    var history = loadHistory();
    history.push({ role: "user", text: text });
    saveHistory(history);

    var typing = addTyping();

    var controller = new AbortController();
    var timeout = setTimeout(function () { controller.abort(); }, 20000);

    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, sessionId: getSessionId() }),
      signal: controller.signal
    })
      .then(function (res) {
        clearTimeout(timeout);
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (result) {
        removeTyping();
        sending = false;
        sendBtn.disabled = false;
        statusEl.textContent = "Online — demo";
        if (result.ok && result.data && typeof result.data.reply === "string") {
          addMessage("bot", result.data.reply);
          var h = loadHistory();
          h.push({ role: "bot", text: result.data.reply });
          saveHistory(h);
        } else {
          var errMsg = (result.data && result.data.error) || "Something went wrong on our end.";
          addMessage("error", errMsg, { retry: function () { sendMessage(text); } });
        }
      })
      .catch(function (err) {
        clearTimeout(timeout);
        removeTyping();
        sending = false;
        sendBtn.disabled = false;
        statusEl.textContent = "Connection issue";
        var msg = err && err.name === "AbortError"
          ? "That took too long to respond. Please try again."
          : "Couldn't reach the chat service. Check your connection and try again.";
        addMessage("error", msg, { retry: function () { sendMessage(text); } });
      });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text || sending) return;
    addMessage("user", text);
    input.value = "";
    autoGrow();
    sendMessage(text);
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
})();
