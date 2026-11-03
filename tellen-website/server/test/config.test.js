const test = require("node:test");
const assert = require("node:assert/strict");

const CONFIG_PATH = require.resolve("../src/config.js");

const ENV_KEYS = [
  "NODE_ENV",
  "LEAD_WEBHOOK_URL",
  "LEAD_WEBHOOK_SECRET",
  "LEAD_DESTINATION_EMAIL",
  "FORCE_MOCK_MODE",
];
const savedEnv = {};
for (const k of ENV_KEYS) savedEnv[k] = process.env[k];

function freshConfig(env) {
  for (const k of ENV_KEYS) {
    if (env[k] === undefined) delete process.env[k];
    else process.env[k] = env[k];
  }
  delete require.cache[CONFIG_PATH];
  return require("../src/config.js");
}

test.after(() => {
  for (const k of ENV_KEYS) {
    if (savedEnv[k] === undefined) delete process.env[k];
    else process.env[k] = savedEnv[k];
  }
  delete require.cache[CONFIG_PATH];
});

test("production + webhook URL set + no secret: forwarding disabled, falls back to local-only", () => {
  const config = freshConfig({
    NODE_ENV: "production",
    LEAD_WEBHOOK_URL: "https://n8n.example.com/webhook/leads",
    LEAD_WEBHOOK_SECRET: "",
    LEAD_DESTINATION_EMAIL: "",
  });
  assert.equal(config.leadWebhookUrl, "", "webhook URL should be cleared when no secret is configured");
  assert.equal(config.leadMockMode, true, "should fall back to mock/local-only mode");
});

test("production + non-HTTPS webhook URL + secret set: forwarding disabled (secret would be cleartext)", () => {
  const config = freshConfig({
    NODE_ENV: "production",
    LEAD_WEBHOOK_URL: "http://n8n.example.com/webhook/leads",
    LEAD_WEBHOOK_SECRET: "s3cret",
    LEAD_DESTINATION_EMAIL: "",
  });
  assert.equal(config.leadWebhookUrl, "", "non-HTTPS webhook URL should be cleared even with a secret set");
  assert.equal(config.leadMockMode, true);
});

test("production + HTTPS webhook URL + secret set: forwarding stays enabled", () => {
  const config = freshConfig({
    NODE_ENV: "production",
    LEAD_WEBHOOK_URL: "https://n8n.example.com/webhook/leads",
    LEAD_WEBHOOK_SECRET: "s3cret",
    LEAD_DESTINATION_EMAIL: "",
  });
  assert.equal(config.leadWebhookUrl, "https://n8n.example.com/webhook/leads");
  assert.equal(config.leadMockMode, false);
});

test("development + webhook URL set + no secret: guard does not apply outside production", () => {
  const config = freshConfig({
    NODE_ENV: "development",
    LEAD_WEBHOOK_URL: "https://n8n.example.com/webhook/leads",
    LEAD_WEBHOOK_SECRET: "",
    LEAD_DESTINATION_EMAIL: "",
  });
  assert.equal(config.leadWebhookUrl, "https://n8n.example.com/webhook/leads");
  assert.equal(config.leadMockMode, false);
});

test("FORCE_MOCK_MODE short-circuits the guard entirely", () => {
  const config = freshConfig({
    NODE_ENV: "production",
    LEAD_WEBHOOK_URL: "http://n8n.example.com/webhook/leads",
    LEAD_WEBHOOK_SECRET: "",
    LEAD_DESTINATION_EMAIL: "",
    FORCE_MOCK_MODE: "1",
  });
  // Mock mode forced on, so the insecure URL is left alone (it's never used)
  // and leadMockMode is true regardless.
  assert.equal(config.leadMockMode, true);
});
