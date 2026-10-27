const test = require("node:test");
const assert = require("node:assert/strict");

const CONFIG_PATH = require.resolve("../src/config.js");
const CONSULTATION_PATH = require.resolve("../src/routes/consultation.js");

function freshForwarder(env) {
  for (const [k, v] of Object.entries(env)) process.env[k] = v;
  delete require.cache[CONFIG_PATH];
  delete require.cache[CONSULTATION_PATH];
  return require("../src/routes/consultation.js").forwardToLeadWebhook;
}

test("forwardToLeadWebhook sends X-Tellen-Secret when a secret is configured", async (t) => {
  let seenHeaders = null;
  const originalFetch = global.fetch;
  global.fetch = async (url, opts) => {
    seenHeaders = opts.headers;
    return { ok: true };
  };
  t.after(() => {
    global.fetch = originalFetch;
  });

  const forward = freshForwarder({
    NODE_ENV: "development",
    LEAD_WEBHOOK_URL: "https://n8n.example.com/webhook/leads",
    LEAD_WEBHOOK_SECRET: "top-secret-value",
    LEAD_DESTINATION_EMAIL: "",
    FORCE_MOCK_MODE: "0",
  });

  const ok = await forward({ id: "test-1" });
  assert.equal(ok, true);
  assert.equal(seenHeaders["X-Tellen-Secret"], "top-secret-value");
});

test("forwardToLeadWebhook omits the header when no secret is configured", async (t) => {
  let seenHeaders = null;
  const originalFetch = global.fetch;
  global.fetch = async (url, opts) => {
    seenHeaders = opts.headers;
    return { ok: true };
  };
  t.after(() => {
    global.fetch = originalFetch;
  });

  const forward = freshForwarder({
    NODE_ENV: "development", // dev so config.js's prod guard doesn't also clear the URL
    LEAD_WEBHOOK_URL: "https://n8n.example.com/webhook/leads",
    LEAD_WEBHOOK_SECRET: "",
    LEAD_DESTINATION_EMAIL: "",
    FORCE_MOCK_MODE: "0",
  });

  await forward({ id: "test-2" });
  assert.equal("X-Tellen-Secret" in seenHeaders, false);
});
