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
  n8nChatWebhookUrl: process.env.N8N_CHAT_WEBHOOK_URL || "",
  n8nChatApiKey: process.env.N8N_CHAT_API_KEY || "",
  n8nClientId: process.env.N8N_CLIENT_ID || "tellen-automation",
  n8nTimeoutMs: Number(process.env.N8N_TIMEOUT_MS) || 15000,

  // --- lead / consultation destination (NOT yet provided — mock mode logs/stores locally) ---
  leadDestinationEmail: process.env.LEAD_DESTINATION_EMAIL || "",
  leadWebhookUrl: process.env.LEAD_WEBHOOK_URL || "",

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

module.exports = config;
