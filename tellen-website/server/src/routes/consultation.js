const express = require("express");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const config = require("../config");
const { validateConsultationInput } = require("../lib/validate");
const { log, hash, redactEmail, preview } = require("../lib/logger");
const { consultationLimiter } = require("../middleware/rateLimit");

const router = express.Router();

const DATA_DIR = path.join(__dirname, "..", "..", "data");
const LEADS_FILE = path.join(DATA_DIR, "leads.jsonl");

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

/** Local durable fallback so a submission is never silently lost, even
 *  when (or especially when) no real email/CRM destination is wired up yet. */
function storeLeadLocally(record) {
  ensureDataDir();
  fs.appendFileSync(LEADS_FILE, JSON.stringify(record) + "\n", "utf8");
}

async function forwardToLeadWebhook(record) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const headers = { "Content-Type": "application/json" };
    if (config.leadWebhookSecret) headers["X-Tellen-Secret"] = config.leadWebhookSecret;
    const res = await fetch(config.leadWebhookUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(record),
      signal: controller.signal,
    });
    return res.ok;
  } catch (err) {
    log("error", "lead_webhook_forward_failed", { message: err && err.message });
    return false;
  } finally {
    clearTimeout(timer);
  }
}

router.post("/consultation", consultationLimiter, async (req, res) => {
  const body = req.body || {};

  // Honeypot: a hidden field real visitors never see or fill. If it has
  // anything in it, the submitter is almost certainly a bot — accept the
  // request outwardly (so the bot doesn't learn to probe further) but
  // drop it without storing or forwarding it.
  if (typeof body.company_url === "string" && body.company_url.trim() !== "") {
    log("info", "consultation_honeypot_triggered", { ipHash: hash(req.ip) });
    return res.json({ success: true, id: crypto.randomUUID() });
  }

  const { valid, errors } = validateConsultationInput(body);
  if (!valid) {
    return res.status(400).json({ success: false, error: errors.join(" ") });
  }

  const id = crypto.randomUUID();
  const record = {
    id,
    receivedAt: new Date().toISOString(),
    name: String(body.name).trim(),
    email: String(body.email).trim(),
    company: body.company ? String(body.company).trim() : "",
    service: body.service ? String(body.service).trim() : "",
    message: body.message ? String(body.message).trim() : "",
    source: "tellen-automation-site",
  };

  try {
    storeLeadLocally(record);
  } catch (err) {
    log("error", "consultation_local_store_failed", { id, message: err && err.message });
    return res.status(500).json({ success: false, error: "Couldn't save your request right now. Please try again shortly." });
  }

  let delivered = false;
  if (!config.leadMockMode && config.leadWebhookUrl) {
    delivered = await forwardToLeadWebhook(record);
  }

  log("info", "consultation_received", {
    id,
    ipHash: hash(req.ip),
    emailRedacted: redactEmail(record.email),
    service: record.service,
    messagePreview: preview(record.message),
    mock: config.leadMockMode,
    delivered,
  });

  return res.json({
    success: true,
    id,
    mock: config.leadMockMode,
    delivered,
  });
});

module.exports = router;
