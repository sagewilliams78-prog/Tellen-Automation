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

  /* ---------- Scroll-reveal ---------- */
  (function () {
    var targets = document.querySelectorAll(".reveal, .reveal-item");
    if (!targets.length) return;
    if (!("IntersectionObserver" in window) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      targets.forEach(function (el) { el.classList.add("in-view"); });
      return;
    }
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("in-view");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -8% 0px" }
    );
    targets.forEach(function (el) { io.observe(el); });
  })();

  /* ---------- Footer year ---------- */
  document.getElementById("year").textContent = new Date().getFullYear();

  /* ---------- Pricing card -> contact form service select ---------- */
  document.querySelectorAll("[data-plan]").forEach(function (a) {
    a.addEventListener("click", function () {
      var svc = document.getElementById("service");
      if (svc) svc.value = a.dataset.plan;
    });
  });

  /* ---------- Legal dialog (draft notices — pending attorney review) ---------- */
  var notices = {
    privacy: "" +
      "<h2>Draft Privacy Notice</h2>" +
      "<p><strong>Not final legal advice — this is a working draft pending attorney review before launch.</strong></p>" +
      "<p><strong>What we collect.</strong> When you submit the consultation form we collect the name, business email, business name, selected service, and message you provide. When you use the \"Try Tellen AI\" chat we collect the messages you send and a randomly generated session id used only to keep your conversation separate from other visitors'.</p>" +
      "<p><strong>How it's used.</strong> Consultation submissions are used to respond to your inquiry and, once a real destination is configured, to route it to our business email or CRM. Chat messages are used to generate a reply and, while in mock mode, are not sent to any third party.</p>" +
      "<p><strong>Retention.</strong> Chat sessions are held in server memory only for the lifetime of the conversation and are cleared automatically after a period of inactivity. Consultation submissions are proposed to be retained for as long as reasonably needed to respond to the inquiry, then deleted or archived per a written retention schedule — not yet finalized.</p>" +
      "<p><strong>Third-party processing.</strong> Once connected, the AI reply engine (n8n workflow), and any scheduling, CRM, SMS, or telephony providers selected for your deployment, will process data you or your customers submit through those channels. Each vendor's own privacy terms apply in addition to this notice.</p>" +
      "<p><strong>Before this goes live</strong>, Tellen must publish its legal business name, contact address, finalized analytics/hosting providers, complete data categories and purposes, concrete retention periods, sharing practices, applicable user rights, and a method for privacy requests.</p>" +
      "<p>AI-enabled customer deployments built for Tellen's clients require their own privacy disclosures, vendor agreements, access controls, retention practices, and any applicable consent requirements — separate from this marketing site.</p>",
    terms: "" +
      "<h2>Draft Website Terms</h2>" +
      "<p><strong>Not final legal advice — this is a working draft pending attorney review before launch.</strong></p>" +
      "<p>This website provides general information about possible automation services. Content is illustrative and is not a binding offer, warranty, or promise of specific outcomes. Pricing shown is proposed and requires the business owner's written approval before being treated as final.</p>" +
      "<p>Service scope, pricing, implementation dates, third-party costs, support levels, security obligations, ownership of deliverables, and limitations of liability must be agreed in a separate written contract before work begins.</p>" +
      "<p><strong>AI disclosure &amp; human oversight.</strong> AI systems used on this site and in Tellen's deployments can generate inaccurate, incomplete, or inappropriate results. Clients and site visitors remain responsible for reviewing critical outputs. Sensitive or urgent requests should be escalated to a person; where legally required, AI-enabled calls or messages will be disclosed as such.</p>" +
      "<p><strong>No guarantees.</strong> No specific cost savings, revenue, uptime, or performance outcomes are guaranteed by anything on this site, including the investment estimate tool, which produces planning estimates only.</p>" +
      "<p>Clients remain responsible for lawful use of their data and communications, including obtaining any consents required for AI-assisted customer contact in their jurisdiction. These draft terms require legal review before publication.</p>"
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

  /* ---------- Investment estimate calculator ---------- */
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
    [p, s, r].forEach(function (el) {
      el.addEventListener("change", update);
    });
    update();
  })();

  /* ---------- Consultation / lead form -> real backend ---------- */
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
      var btn = form.querySelector("button[type=submit]");
      var data = Object.fromEntries(new FormData(form).entries());

      if (!data.name || !data.email) {
        setStatus("Please fill in your name and business email before submitting.", "error");
        return;
      }

      btn.disabled = true;
      setStatus("Sending your request…");

      fetch("/api/consultation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      })
        .then(function (res) {
          return res.json().then(function (body) {
            return { ok: res.ok, body: body };
          });
        })
        .then(function (result) {
          btn.disabled = false;
          if (result.ok && result.body && result.body.success) {
            form.reset();
            setStatus("Request received — confirmation id " + result.body.id + ". We'll follow up by email shortly.", "success");
          } else {
            var msg = (result.body && result.body.error) || "We couldn't submit that just now. Please try again in a moment.";
            setStatus(msg, "error");
          }
        })
        .catch(function () {
          btn.disabled = false;
          setStatus("We couldn't reach the server. Check your connection and try again — nothing was sent.", "error");
        });
    });
  })();
})();
