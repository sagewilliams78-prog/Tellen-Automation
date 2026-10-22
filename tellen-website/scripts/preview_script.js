(function () {
  "use strict";

  /* ---------- Mobile nav ---------- */
  var menu = document.getElementById("menu");
  var navlinks = document.getElementById("navlinks");
  menu.addEventListener("click", function () {
    var open = navlinks.classList.toggle("open");
    menu.setAttribute("aria-expanded", String(open));
  });
  navlinks.querySelectorAll("a").forEach(function (a) {
    a.addEventListener("click", function () {
      navlinks.classList.remove("open");
      menu.setAttribute("aria-expanded", "false");
    });
  });
  document.addEventListener("click", function (e) {
    if (!menu.contains(e.target) && !navlinks.contains(e.target)) {
      navlinks.classList.remove("open");
      menu.setAttribute("aria-expanded", "false");
    }
  });

  document.getElementById("year").textContent = new Date().getFullYear();

  document.querySelectorAll("[data-plan]").forEach(function (a) {
    a.addEventListener("click", function () {
      var svc = document.getElementById("service");
      if (svc) svc.value = a.dataset.plan;
    });
  });

  var notices = {
    privacy: "" +
      "<h2>Draft Privacy Notice</h2>" +
      "<p><strong>Not final legal advice — this is a working draft pending attorney review before launch.</strong></p>" +
      "<p><strong>What we collect.</strong> When you submit the consultation form we collect the name, business email, business name, selected service, and message you provide. When you use the \"Try Tellen AI\" chat we collect the messages you send and a randomly generated session id used only to keep your conversation separate from other visitors'.</p>" +
      "<p><strong>How it's used.</strong> Consultation submissions are used to respond to your inquiry and, once a real destination is configured, to route it to our business email or CRM. Chat messages are used to generate a reply and, while in mock mode, are not sent to any third party.</p>" +
      "<p><strong>Retention.</strong> Chat sessions are held only for the lifetime of the conversation and are cleared automatically after a period of inactivity. Consultation submissions are proposed to be retained for as long as reasonably needed to respond to the inquiry, then deleted or archived per a written retention schedule — not yet finalized.</p>" +
      "<p><strong>Third-party processing.</strong> Once connected, the AI reply engine (n8n workflow), and any scheduling, CRM, SMS, or telephony providers selected for your deployment, will process data you or your customers submit through those channels.</p>" +
      "<p><strong>Before this goes live</strong>, Tellen must publish its legal business name, contact address, finalized analytics/hosting providers, complete data categories and purposes, concrete retention periods, sharing practices, applicable user rights, and a method for privacy requests.</p>",
    terms: "" +
      "<h2>Draft Website Terms</h2>" +
      "<p><strong>Not final legal advice — this is a working draft pending attorney review before launch.</strong></p>" +
      "<p>This website provides general information about possible automation services. Content is illustrative and is not a binding offer, warranty, or promise of specific outcomes. Pricing shown is proposed and requires the business owner's written approval before being treated as final.</p>" +
      "<p>Service scope, pricing, implementation dates, third-party costs, support levels, security obligations, ownership of deliverables, and limitations of liability must be agreed in a separate written contract before work begins.</p>" +
      "<p><strong>AI disclosure &amp; human oversight.</strong> AI systems used on this site and in Tellen's deployments can generate inaccurate, incomplete, or inappropriate results. Sensitive or urgent requests should be escalated to a person; where legally required, AI-enabled calls or messages will be disclosed as such.</p>" +
      "<p><strong>No guarantees.</strong> No specific cost savings, revenue, uptime, or performance outcomes are guaranteed by anything on this site, including the investment estimate tool, which produces planning estimates only.</p>"
  };
  var dialog = document.getElementById("legalDialog");
  document.querySelectorAll("[data-legal]").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      document.getElementById("legalContent").innerHTML = notices[a.dataset.legal];
      dialog.showModal();
    });
  });
  document.getElementById("closeDialog").onclick = function () {
    dialog.close();
  };

  (function () {
    var p = document.getElementById("estPlan");
    var s = document.getElementById("estSms");
    var r = document.getElementById("estReports");
    if (!p) return;
    var fmt = function (n) {
      return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
    };
    function update() {
      var base = Number(p.value);
      var monthly = base + (s.checked ? 99 : 0) + (r.checked ? 149 : 0);
      var setup = base === 497 ? 750 : 1500;
      document.getElementById("estMonthly").textContent = fmt(monthly);
      document.getElementById("estSetup").textContent = fmt(setup);
      document.getElementById("estFirst").textContent = fmt(monthly + setup);
      document.getElementById("estCta").dataset.plan = base === 497 ? "Starter" : "Growth";
    }
    [p, s, r].forEach(function (el) { el.addEventListener("change", update); });
    update();
  })();

  /* ---------- Lead form: simulated locally (no backend on this preview) ---------- */
  (function () {
    var form = document.getElementById("leadForm");
    var status = document.getElementById("formStatus");
    if (!form) return;
    function setStatus(text, state) {
      status.textContent = text;
      if (state) status.setAttribute("data-state", state);
      else status.removeAttribute("data-state");
    }
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var data = Object.fromEntries(new FormData(form).entries());
      if (data.company_url) return; // honeypot, same as the real backend
      if (!data.name || !data.email) {
        setStatus("Please fill in your name and business email before submitting.", "error");
        return;
      }
      var btn = form.querySelector("button[type=submit]");
      btn.disabled = true;
      setStatus("Validating…");
      setTimeout(function () {
        btn.disabled = false;
        form.reset();
        var id = Math.random().toString(16).slice(2, 10);
        setStatus("Looks good — simulated confirmation id " + id + ". The real deployment stores and routes this from the server (see the delivered project).", "success");
      }, 500);
    });
  })();

  /* ---------- Try Tellen AI — same mock rules as the real backend, run client-side here ---------- */
  (function () {
    var launcher = document.getElementById("chatLauncher");
    var panel = document.getElementById("chatPanel");
    var body = document.getElementById("chatBody");
    var form = document.getElementById("chatForm");
    var input = document.getElementById("chatInput");
    var sendBtn = document.getElementById("chatSend");
    var resetBtn = document.getElementById("chatReset");
    var closeBtn = document.getElementById("chatClose");
    var statusEl = document.getElementById("chatStatus");
    var messageCount = 0;
    var sending = false;

    var RULES = [
      { test: /\b(hi|hello|hey|good (morning|afternoon|evening))\b/i, reply: "Hey there! I'm the Tellen AI demo assistant. I can tell you about our services, pricing, or how a real deployment would work for your business. What would you like to know?" },
      { test: /\bpric(e|ing)|cost|how much\b/i, reply: "Our proposed packages are Starter at $497/mo (+$750 setup) and Growth at $997/mo (+$1,500 setup), with Enterprise custom-quoted. Optional add-ons: SMS follow-up (+$99/mo) and advanced reporting (+$149/mo)." },
      { test: /\breceptionist|answer(ing)? (calls|phone)/i, reply: "An AI receptionist can greet callers or chatters, answer common questions, collect their details, and route urgent issues to a real person — with human escalation built in." },
      { test: /\bschedul|appointment|booking/i, reply: "Smart scheduling connects booking requests to the calendar or tools your team already uses, with reminders handled automatically." },
      { test: /\bfollow[- ]?up|lead\b/i, reply: "Lead follow-up automation captures inquiries as they come in and helps your team follow up consistently instead of leads going cold." },
      { test: /\bhvac|plumb|electric|propert(y|ies)|service business/i, reply: "We're starting with Southern California HVAC, plumbing, electrical, and property management teams, since those businesses lose the most to missed calls and slow follow-up." },
      { test: /\bhow (does|do) (it|this) work|how it works|process\b/i, reply: "Four steps: a consultation to learn your business, building and integrating the workflow, testing and optimizing before broader use, then ongoing support." },
      { test: /\bhuman|person|real person|talk to someone|oversight\b/i, reply: "Every Tellen deployment includes human escalation paths and oversight. This demo chat itself is AI, not a person." },
      { test: /\b(thanks|thank you|appreciate it)\b/i, reply: "You're welcome! Anything else about Tellen Automation, or want help preparing a consultation request?" }
    ];
    var FALLBACK = "I can speak to our services, pricing, and how deployments work — could you rephrase, or ask about one of those?";
    var WELCOME = "Hi, I'm the Tellen AI demo assistant. Ask me about pricing, services, or how it works. (This published preview runs the same canned demo rules the real site's mock backend uses — no server here.)";

    function mockReply(text) {
      for (var i = 0; i < RULES.length; i++) {
        if (RULES[i].test.test(text)) return RULES[i].reply;
      }
      if (messageCount === 1) return "Thanks for trying the demo! I'm a simple rule-based stand-in (the real n8n AI workflow isn't connected here). Try asking about pricing, services, or how it works.";
      return FALLBACK;
    }

    function addMessage(role, text) {
      var el = document.createElement("div");
      el.className = "chat-msg " + role;
      el.textContent = text;
      body.appendChild(el);
      body.scrollTop = body.scrollHeight;
    }
    function addTyping() {
      var el = document.createElement("div");
      el.className = "chat-typing";
      el.id = "chatTyping";
      el.innerHTML = "<span></span><span></span><span></span>";
      body.appendChild(el);
      body.scrollTop = body.scrollHeight;
    }
    function removeTyping() {
      var el = document.getElementById("chatTyping");
      if (el) el.remove();
    }

    function openPanel() {
      panel.hidden = false;
      launcher.hidden = true;
      launcher.setAttribute("aria-expanded", "true");
      if (body.children.length === 0) addMessage("bot", WELCOME);
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
      messageCount = 0;
      body.innerHTML = "";
      addMessage("bot", WELCOME);
      statusEl.textContent = "Online — demo";
    });

    function autoGrow() {
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 90) + "px";
    }
    input.addEventListener("input", autoGrow);

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var text = input.value.trim();
      if (!text || sending) return;
      sending = true;
      sendBtn.disabled = true;
      addMessage("user", text);
      messageCount += 1;
      input.value = "";
      autoGrow();
      statusEl.textContent = "Thinking…";
      addTyping();
      setTimeout(function () {
        removeTyping();
        addMessage("bot", mockReply(text));
        statusEl.textContent = "Online — demo";
        sending = false;
        sendBtn.disabled = false;
      }, 450 + Math.random() * 400);
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        form.requestSubmit();
      }
    });
  })();
})();
