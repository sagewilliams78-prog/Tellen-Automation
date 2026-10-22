const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const request = require("supertest");

process.env.FORCE_MOCK_MODE = "1";
const app = require("../src/index.js");

const LEADS_FILE = path.join(__dirname, "..", "data", "leads.jsonl");

function countLeadLines() {
  if (!fs.existsSync(LEADS_FILE)) return 0;
  return fs.readFileSync(LEADS_FILE, "utf8").split("\n").filter(Boolean).length;
}

test("POST /api/consultation accepts a valid submission and stores it", async () => {
  const before = countLeadLines();
  const res = await request(app).post("/api/consultation").send({
    name: "Automated Test",
    email: "automated-test@example.com",
    company: "Test Co",
    service: "Starter",
    message: "Testing the lead capture endpoint.",
  });
  assert.equal(res.status, 200);
  assert.equal(res.body.success, true);
  assert.equal(typeof res.body.id, "string");
  assert.equal(countLeadLines(), before + 1);

  const lastLine = fs.readFileSync(LEADS_FILE, "utf8").trim().split("\n").pop();
  const record = JSON.parse(lastLine);
  assert.equal(record.email, "automated-test@example.com");
  assert.equal(record.id, res.body.id);
});

test("POST /api/consultation 400s on an invalid email and does not store it", async () => {
  const before = countLeadLines();
  const res = await request(app).post("/api/consultation").send({
    name: "Bad Email",
    email: "not-an-email",
  });
  assert.equal(res.status, 400);
  assert.equal(res.body.success, false);
  assert.equal(countLeadLines(), before);
});

test("POST /api/consultation 400s when name is missing", async () => {
  const res = await request(app).post("/api/consultation").send({
    email: "noname@example.com",
  });
  assert.equal(res.status, 400);
  assert.equal(res.body.success, false);
});

test("honeypot field silently drops bot submissions without storing them", async () => {
  const before = countLeadLines();
  const res = await request(app).post("/api/consultation").send({
    name: "Bot",
    email: "bot@example.com",
    company_url: "http://spam.example", // a real visitor never fills this
  });
  assert.equal(res.status, 200);
  assert.equal(res.body.success, true);
  // Outwardly looks like success (so the bot doesn't learn to adapt), but
  // nothing was actually stored.
  assert.equal(countLeadLines(), before);
});

test("POST /api/consultation is rate-limited after the configured max per window", async () => {
  let sawLimit = false;
  for (let i = 0; i < 10; i++) {
    const res = await request(app).post("/api/consultation").send({
      name: "Rate Test " + i,
      email: "rate-test-" + i + "@example.com",
    });
    if (res.status === 429) {
      sawLimit = true;
      assert.equal(res.body.success, false);
      break;
    }
  }
  assert.ok(sawLimit, "expected a 429 after exceeding the consultation rate limit");
});
