require("dotenv").config();

function bool(v, def) {
  if (v === undefined || v === "") return def;
  return v === "1" || v.toLowerCase() === "true";
}

const config = {
  port: Number(process.env.PORT) || 3000,
  nodeEnv: process.env.NODE_ENV || "development",

  // --- n8n chat integration ---
  // N8N_CHAT_WEBHOOK_URL is the production URL of the "Customer Chat" trigger
  // in the "AI Receptionist (Multi-Client)" n8n workflow. N8N_CLIENT_ID picks
  // which row of that workflow's "clients" data table answers — it must match
  // a client_id with status "active" there. Leave the webhook URL blank to
  // fall back to mock mode (canned demo replies, no external calls).
  //
  // N8N_CHAT_API_KEY must match the literal secret configured in n8n's
  // "Verify Chat Secret" node on that same workflow once it's published —
  // that webhook URL is shared across every client's own deployed server,
  // and this is the only thing that stops a stranger from hitting it
  // directly. It's sent in the request body (metadata.api_key), not as a
  // header: the Chat Trigger node can't read raw HTTP headers at all.
  n8nChatWebhookUrl: process.env.N8N_CHAT_WEBHOOK_URL || "",
  n8nChatApiKey: process.env.N8N_CHAT_API_KEY || "",
  n8nClientId: process.env.N8N_CLIENT_ID || "tellen-automation",
  n8nTimeoutMs: Number(process.env.N8N_TIMEOUT_MS) || 15000,

  // --- lead / consultation destination (NOT yet provided — mock mode logs/stores locally) ---
  leadDestinationEmail: process.env.LEAD_DESTINATION_EMAIL || "",
  leadWebhookUrl: process.env.LEAD_WEBHOOK_URL || "",
  leadWebhookSecret: process.env.LEAD_WEBHOOK_SECRET || "",

  // --- CORS ---
  // In production this MUST be the real site origin(s), comma separated.
  // Left blank in development so the bundled frontend (served from the
  // same origin by this same server) works without extra config.
  allowedOrigins: (process.env.ALLOWED_ORIGINS || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),

  // --- rate limiting ---
  chatRateLimitWindowMs: Number(process.env.CHAT_RATE_LIMIT_WINDOW_MS) || 60_000,
  chatRateLimitMax: Number(process.env.CHAT_RATE_LIMIT_MAX) || 20,
  consultationRateLimitWindowMs: Number(process.env.CONSULTATION_RATE_LIMIT_WINDOW_MS) || 15 * 60_000,
  consultationRateLimitMax: Number(process.env.CONSULTATION_RATE_LIMIT_MAX) || 5,

  // --- misc ---
  mockModeForced: bool(process.env.FORCE_MOCK_MODE, false),
};

config.chatMockMode = config.mockModeForced || !config.n8nChatWebhookUrl;
config.leadMockMode = config.mockModeForced || (!config.leadDestinationEmail && !config.leadWebhookUrl);

// --- Fail-closed guard against the exact misconfiguration this secret was
// added to prevent: in production, never forward a lead over a webhook
// that is unauthenticated (no LEAD_WEBHOOK_SECRET) or not HTTPS (secret
// would travel in cleartext). Rather than silently sending it anyway (the
// old behavior) or crashing the whole site over one misconfigured env var,
// disable forwarding for this one endpoint and log loudly so the gap gets
// noticed and fixed — leads are still captured via the local JSONL fallback
// either way, so nothing is lost while it's disabled. ---
if (config.nodeEnv === "production" && config.leadWebhookUrl && !config.mockModeForced) {
  let reason = null;
  if (!config.leadWebhookSecret) {
    reason = "LEAD_WEBHOOK_URL is set without LEAD_WEBHOOK_SECRET";
  } else if (!config.leadWebhookUrl.startsWith("https://")) {
    reason = "LEAD_WEBHOOK_URL is not HTTPS, so the shared secret would travel in cleartext";
  }
  if (reason) {
    console.error(
      JSON.stringify({
        ts: new Date().toISOString(),
        level: "error",
        event: "lead_webhook_insecure_config",
        message: `${reason}. Lead forwarding disabled (leads still stored locally) until this is fixed.`,
      })
    );
    config.leadWebhookUrl = "";
    config.leadMockMode = config.mockModeForced || (!config.leadDestinationEmail && !config.leadWebhookUrl);
  }
}

module.exports = config;
