const test = require("node:test");
const assert = require("node:assert/strict");
const request = require("supertest");

process.env.FORCE_MOCK_MODE = "1";
const app = require("../src/index.js");

test("POST /api/chat returns a mock reply for a valid message", async () => {
  const res = await request(app)
    .post("/api/chat")
    .send({ message: "hello", sessionId: "chat-test-" + Date.now() });
  assert.equal(res.status, 200);
  assert.equal(typeof res.body.reply, "string");
  assert.ok(res.body.reply.length > 0);
  assert.equal(res.body.mock, true);
});

test("POST /api/chat 400s when message is missing", async () => {
  const res = await request(app)
    .post("/api/chat")
    .send({ sessionId: "chat-test-missing" });
  assert.equal(res.status, 400);
  assert.match(res.body.error, /message is required/);
});

test("POST /api/chat 400s when message exceeds the payload limit", async () => {
  const res = await request(app)
    .post("/api/chat")
    .send({ message: "x".repeat(2000), sessionId: "chat-test-oversize" });
  assert.equal(res.status, 400);
});

test("POST /api/chat 400s on malformed JSON", async () => {
  const res = await request(app)
    .post("/api/chat")
    .set("Content-Type", "application/json")
    .send("{not valid json");
  assert.equal(res.status, 400);
  assert.match(res.body.error, /valid JSON/);
});

test("session isolation: two sessionIds get independent first-message framing", async () => {
  const a = "chat-iso-a-" + Date.now();
  const b = "chat-iso-b-" + Date.now();

  const a1 = await request(app).post("/api/chat").send({ message: "xyzzy unmatched text", sessionId: a });
  const b1 = await request(app).post("/api/chat").send({ message: "xyzzy unmatched text", sessionId: b });

  // Both are first messages in their own session, so both should get the
  // "first message" framing, independently of each other.
  assert.match(a1.body.reply, /simple rule-based stand-in/);
  assert.match(b1.body.reply, /simple rule-based stand-in/);

  const a2 = await request(app).post("/api/chat").send({ message: "xyzzy unmatched text", sessionId: a });
  // Second message in session a should NOT repeat the first-message framing.
  assert.doesNotMatch(a2.body.reply, /simple rule-based stand-in/);
});

test("POST /api/chat is rate-limited after the configured max per window", async () => {
  const sessionId = "chat-rate-" + Date.now();
  let sawLimit = false;
  for (let i = 0; i < 25; i++) {
    const res = await request(app).post("/api/chat").send({ message: "ping " + i, sessionId });
    if (res.status === 429) {
      sawLimit = true;
      break;
    }
  }
  assert.ok(sawLimit, "expected a 429 after exceeding the chat rate limit");
});
