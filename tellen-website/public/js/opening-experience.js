/**
 * Opening Experience orchestrator.
 *
 * Decides, once, whether to run the cinematic scroll-driven 3D sequence
 * or stay on the static accessible baseline (default markup), then wires
 * up whichever mode is active: nav, hero CTAs, service dialogs, and —
 * only in enhanced mode — the Three.js core + GSAP ScrollTrigger
 * choreography and the floating hotspots.
 *
 * The static baseline is not a degraded experience bolted on for
 * compliance: it is real HTML that works with zero JS, so it is also
 * what ships if this script fails to load at all.
 */
(function () {
  "use strict";

  const wrap = document.getElementById("tcStageWrap");
  if (!wrap) return; // redesign markup not present — nothing to do

  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function detectWebGL() {
    try {
      const c = document.createElement("canvas");
      return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
    } catch (e) {
      return false;
    }
  }
  const hasWebGL = detectWebGL();
  const enhanced = !prefersReduced && hasWebGL;

  /* ---------------- Service dialog (shared, both modes) ---------------- */
  const dialog = document.getElementById("tcServiceDialog");
  const dialogTitle = document.getElementById("tcDialogTitle");
  const dialogKicker = document.getElementById("tcDialogKicker");
  const dialogBody = document.getElementById("tcDialogBody");
  const dialogClose = document.getElementById("tcDialogClose");
  let dialogReturnFocus = null;

  const SERVICE_CONTENT = {
    receptionist: {
      kicker: "01 · Receptionist",
      title: "Always answers. Knows when to hand off.",
      body:
        '<div class="tc-waveform" aria-hidden="true">' +
        Array.from({ length: 18 })
          .map(() => '<span style="height:' + (20 + Math.round(Math.random() * 80)) + '%"></span>')
          .join("") +
        "</div>" +
        '<p class="tc-dialog-kicker" style="margin-top:0">Sample conversation</p>' +
        '<div class="tc-sample-convo">' +
        '<div class="bubble caller">Hi, do you have anything open tomorrow afternoon?</div>' +
        '<div class="bubble ai">Yes — I have 1:30 and 3:00 open tomorrow. Which works better, and what\'s the visit for?</div>' +
        '<div class="bubble caller">3:00, for a routine inspection.</div>' +
        '<div class="bubble ai">You\'re booked for 3:00 tomorrow. I\'ll text a confirmation and reminder beforehand.</div>' +
        "</div>" +
        "<p>This is the same engine answering chat and phone calls live on this site right now — not a scripted demo.</p>",
      actions: [{ label: "Chat with Tellen now →", action: "open-chat" }],
    },
    scheduling: {
      kicker: "02 · Scheduling",
      title: "Books straight onto a real calendar.",
      body:
        '<span class="tc-illustrative-badge">Illustrative — not a live booking</span>' +
        '<p>Sample slot picker for a Tuesday afternoon:</p>' +
        '<div class="tc-slot-grid" id="tcSlotGrid" role="group" aria-label="Sample appointment slots">' +
        ["1:00", "1:30", "2:00", "2:30", "3:00", "3:30"]
          .map((t) => '<button type="button" aria-pressed="false">' + t + "</button>")
          .join("") +
        "</div>" +
        "<p>In a live deployment, selecting a slot writes directly to the business's own Google Calendar through the same workflow used for real client bookings today.</p>",
      actions: [{ label: "Start a real booking conversation →", action: "open-chat" }],
    },
    followup: {
      kicker: "03 · Follow-up",
      title: "Nothing goes cold.",
      body:
        '<span class="tc-illustrative-badge">Illustrative example — not account data</span>' +
        '<div class="tc-lead-steps">' +
        '<div class="step done"><span class="dot">1</span><div><strong>Inquiry received</strong><span>Website chat, 9:42am — asked about after-hours service.</span></div></div>' +
        '<div class="step done"><span class="dot">2</span><div><strong>Follow-up prepared</strong><span>No response in 2 hours — a check-in message is queued automatically.</span></div></div>' +
        '<div class="step"><span class="dot">3</span><div><strong>Appointment scheduled</strong><span>Follow-up reply converts the inquiry into a booked visit.</span></div></div>' +
        "</div>" +
        "<p>Real client deployments run this exact sequence hourly against actual leads — this panel just can't show your data on a public page.</p>",
      actions: [{ label: "See how Lead Follow-Up runs today →", action: "open-contact" }],
    },
  };

  function openServiceDialog(key, triggerEl) {
    const content = SERVICE_CONTENT[key];
    if (!content || typeof dialog.showModal !== "function") return;
    dialogReturnFocus = triggerEl || document.activeElement;
    dialogKicker.textContent = content.kicker;
    dialogTitle.textContent = content.title;
    dialogBody.innerHTML =
      content.body +
      '<div class="tc-dialog-actions">' +
      content.actions
        .map((a) => '<button type="button" class="tc-btn tc-btn-primary" data-dialog-action="' + a.action + '">' + a.label + "</button>")
        .join("") +
      "</div>";
    dialog.showModal();
    dialogClose.focus();

    const slotGrid = document.getElementById("tcSlotGrid");
    if (slotGrid) {
      slotGrid.querySelectorAll("button").forEach((btn) => {
        btn.addEventListener("click", () => {
          slotGrid.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", "false"));
          btn.setAttribute("aria-pressed", "true");
        });
      });
    }
    dialogBody.querySelectorAll("[data-dialog-action]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const action = btn.getAttribute("data-dialog-action");
        dialog.close();
        if (action === "open-chat") {
          const launcher = document.getElementById("chatLauncher");
          if (launcher) launcher.click();
        } else if (action === "open-contact") {
          document.getElementById("contact")?.scrollIntoView({ behavior: prefersReduced ? "auto" : "smooth" });
        }
      });
    });
  }

  dialogClose.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    if (dialogReturnFocus && typeof dialogReturnFocus.focus === "function") dialogReturnFocus.focus();
    if (enhanced) exitFocusedSegment();
    updateBackOverviewVisibility();
  });
  dialog.addEventListener("click", (e) => {
    const rect = dialog.getBoundingClientRect();
    const inside =
      e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom;
    if (!inside) dialog.close();
  });

  document.querySelectorAll(".tc-service-tile").forEach((btn) => {
    btn.addEventListener("click", () => openServiceDialog(btn.dataset.service, btn));
  });

  /* ---------------- Hero / nav actions common to both modes ---------------- */
  function goToContact() {
    document.getElementById("contact")?.scrollIntoView({ behavior: prefersReduced ? "auto" : "smooth" });
  }
  function tryReceptionist() {
    document.getElementById("chatLauncher")?.click();
  }
  document.getElementById("tcTryReceptionist")?.addEventListener("click", tryReceptionist);
  document.getElementById("tcFinalTry")?.addEventListener("click", tryReceptionist);
  document.getElementById("tcFinalBook")?.addEventListener("click", goToContact);
  document.getElementById("tcBookDemo")?.addEventListener("click", goToContact);

  function updateBackOverviewVisibility() {
    const back = document.getElementById("tcBackOverview");
    if (back) back.classList.toggle("tc-visible", dialog.open);
  }

  /* ================================================================
     STATIC MODE — stop here. No canvas, no ScrollTrigger, no pinning.
     ================================================================ */
  if (!enhanced) {
    document.querySelectorAll('[data-tc-nav="systems"]').forEach((el) =>
      el.addEventListener("click", () => document.querySelector(".tc-static-services")?.scrollIntoView({ behavior: "auto" }))
    );
    document.querySelectorAll('[data-tc-nav="experience"]').forEach((el) => el.addEventListener("click", goToContact));
    return;
  }

  /* ================================================================
     ENHANCED MODE — Three.js core + GSAP ScrollTrigger choreography.
     ================================================================ */
  wrap.classList.add("tc-enhanced");

  const canvasHost = document.getElementById("tcCanvasHost");
  const canvas = document.getElementById("tcCanvas");
  const hotspotEls = [0, 1, 2].map((i) => document.getElementById("tcHotspot" + i));
  const legendBtns = document.querySelectorAll("#tcHotspotLegend button");
  const labelApproach = document.getElementById("tcLabelApproach");
  const labelExplore = document.getElementById("tcLabelExplore");
  const labelConnect = document.getElementById("tcLabelConnect");
  const finalActions = document.getElementById("tcFinalActions");
  const heroCopy = document.querySelector(".tc-hero-copy");
  const progressTicks = document.querySelectorAll("#tcProgressRail .tick");

  const STAGES = {
    reveal: [0, 0.12],
    approach: [0.12, 0.38],
    explore: [0.38, 0.68],
    connect: [0.68, 0.86],
    next: [0.86, 1.0],
  };

  // Camera keyframes at each stage boundary: [x, y, z] position + look target.
  const CAM_KEYFRAMES = [
    { p: 0, pos: [2.6, 1.3, 4.4], target: [0, 0.1, 0] },
    { p: 0.12, pos: [2.3, 1.1, 3.9], target: [0, 0.1, 0] },
    { p: 0.38, pos: [1.55, 0.55, 2.5], target: [0, 0, 0] },
    { p: 0.68, pos: [1.15, 0.3, 2.05], target: [0, 0, 0] },
    { p: 0.86, pos: [2.0, 0.9, 3.6], target: [0, 0, 0] },
    { p: 1.0, pos: [2.5, 1.05, 4.3], target: [0, 0.05, 0] },
  ];

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }
  function cameraForProgress(p) {
    let lo = CAM_KEYFRAMES[0];
    let hi = CAM_KEYFRAMES[CAM_KEYFRAMES.length - 1];
    for (let i = 0; i < CAM_KEYFRAMES.length - 1; i++) {
      if (p >= CAM_KEYFRAMES[i].p && p <= CAM_KEYFRAMES[i + 1].p) {
        lo = CAM_KEYFRAMES[i];
        hi = CAM_KEYFRAMES[i + 1];
        break;
      }
    }
    const span = hi.p - lo.p || 1;
    const t = Math.min(1, Math.max(0, (p - lo.p) / span));
    return {
      pos: { x: lerp(lo.pos[0], hi.pos[0], t), y: lerp(lo.pos[1], hi.pos[1], t), z: lerp(lo.pos[2], hi.pos[2], t) },
      target: { x: lerp(lo.target[0], hi.target[0], t), y: lerp(lo.target[1], hi.target[1], t), z: lerp(lo.target[2], hi.target[2], t) },
    };
  }
  function separationForProgress(p) {
    if (p <= STAGES.approach[0]) return 0;
    if (p <= STAGES.approach[1]) return (p - STAGES.approach[0]) / (STAGES.approach[1] - STAGES.approach[0]);
    if (p <= STAGES.explore[1]) return 1;
    if (p <= STAGES.connect[1]) return lerp(1, 0.42, (p - STAGES.connect[0]) / (STAGES.connect[1] - STAGES.connect[0]));
    return lerp(0.42, 0.3, (p - STAGES.next[0]) / (STAGES.next[1] - STAGES.next[0]));
  }
  function connectForProgress(p) {
    if (p < STAGES.connect[0]) return 0;
    if (p > STAGES.next[1] - 0.02) return 0.6;
    return Math.min(1, (p - STAGES.connect[0]) / 0.06);
  }
  function stageForProgress(p) {
    for (const [name, [s, e]] of Object.entries(STAGES)) if (p >= s && p <= e) return name;
    return "next";
  }

  let core = null;
  let lastProgress = 0;
  let focusedSegment = null;

  function applyFrame(p) {
    lastProgress = p;
    const stage = stageForProgress(p);
    const { pos, target } = cameraForProgress(p);
    if (focusedSegment === null) core?.setCamera(pos, target);
    core?.setSeparation(separationForProgress(p));
    core?.setConnect(connectForProgress(p));

    // On phones the hero copy runs full-width (the desktop layout keeps
    // it docked in a left column clear of the ring; see cinematic.css's
    // 760px breakpoint), so once the ring grows past the opening "reveal"
    // framing it sits directly behind the text. Fading the copy out past
    // that point is a no-op on desktop (the rule below is mobile-only)
    // and mirrors how the other stage-specific UI here is already
    // toggled via tc-visible.
    heroCopy?.classList.toggle("tc-hero-copy-hidden", stage !== "reveal");
    labelApproach.classList.toggle("tc-visible", stage === "approach");
    labelExplore.classList.toggle("tc-visible", stage === "explore" && focusedSegment === null);
    labelConnect.classList.toggle("tc-visible", stage === "connect");
    finalActions.classList.toggle("tc-visible", stage === "next");

    const inExplore = stage === "explore" || stage === "connect";
    hotspotEls.forEach((el) => {
      el.classList.toggle("tc-active-stage", inExplore && focusedSegment === null);
      el.tabIndex = inExplore ? 0 : -1;
    });
    document.getElementById("tcHotspotLegend").classList.toggle("tc-visible", inExplore);
    legendBtns.forEach((b) => (b.tabIndex = inExplore ? 0 : -1));

    progressTicks.forEach((tick) => tick.classList.toggle("tc-on", tick.dataset.stage === stage));
  }

  function enterFocusedSegment(index, serviceKey, triggerEl) {
    focusedSegment = index;
    const angle = (index / 3) * Math.PI * 2 + Math.PI / 3;
    const dist = 2.0;
    core?.setCamera(
      { x: Math.cos(angle) * dist, y: 0.25, z: Math.sin(angle) * dist },
      { x: Math.cos(angle) * 0.9, y: 0, z: Math.sin(angle) * 0.9 }
    );
    openServiceDialog(serviceKey, triggerEl);
    updateBackOverviewVisibility();
  }
  function exitFocusedSegment() {
    focusedSegment = null;
    applyFrame(lastProgress);
  }

  hotspotEls.forEach((el, i) => {
    el.addEventListener("click", () => enterFocusedSegment(i, el.dataset.service, el));
  });
  legendBtns.forEach((btn, i) => {
    btn.addEventListener("click", () => enterFocusedSegment(i, btn.dataset.service, btn));
  });
  document.getElementById("tcBackOverview")?.addEventListener("click", () => {
    if (dialog.open) dialog.close();
    else exitFocusedSegment();
  });

  // Nav: move scroll position to a meaningful point in the sequence.
  function scrollToProgress(target) {
    const st = ScrollTrigger.getById("tc-main");
    if (!st) return;
    const y = st.start + (st.end - st.start) * target;
    window.scrollTo({ top: y, behavior: "smooth" });
  }
  document.querySelectorAll('[data-tc-nav="systems"]').forEach((el) => el.addEventListener("click", () => scrollToProgress(0.4)));
  document.querySelectorAll('[data-tc-nav="experience"]').forEach((el) => el.addEventListener("click", () => scrollToProgress(0.95)));

  /* ---------------- Boot Three.js + ScrollTrigger (deferred) ---------------- */
  function boot() {
    import("./tellen-core.js")
      .then((mod) => {
        core = mod.create(canvas, { reducedQuality: window.matchMedia("(max-width: 760px)").matches });
        gsap.registerPlugin(ScrollTrigger);
        ScrollTrigger.create({
          id: "tc-main",
          trigger: wrap,
          start: "top top",
          end: "bottom bottom",
          scrub: true,
          onUpdate(self) {
            if (focusedSegment === null) applyFrame(self.progress);
          },
        });
        applyFrame(0);

        window.addEventListener("resize", () => {
          core.resize();
          ScrollTrigger.refresh();
        });

        const io = new IntersectionObserver(
          (entries) => entries.forEach((e) => (e.isIntersecting ? core.resume() : core.pause())),
          { threshold: 0 }
        );
        io.observe(canvasHost);
        document.addEventListener("visibilitychange", () => {
          if (document.hidden) core.pause();
          else if (canvasHost.getBoundingClientRect().bottom > 0) core.resume();
        });

        (function syncHotspots() {
          requestAnimationFrame(syncHotspots);
          if (!core) return;
          const positions = core.getHotspotScreenPositions();
          positions.forEach((pt, i) => {
            const el = hotspotEls[i];
            el.style.left = pt.x + "px";
            el.style.top = pt.y + "px";
          });
        })();
      })
      .catch((err) => {
        // Three.js failed to load/initialize (e.g. GPU blocklisted) —
        // fall back to the static accessible layout rather than leaving
        // a half-built scene on screen.
        console.error("Tellen Core failed to initialize; falling back to static layout.", err);
        wrap.classList.remove("tc-enhanced");
      });
  }

  if ("requestIdleCallback" in window) requestIdleCallback(boot, { timeout: 1500 });
  else window.addEventListener("load", boot);
})();
