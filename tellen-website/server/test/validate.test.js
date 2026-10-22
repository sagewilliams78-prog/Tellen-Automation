const test = require("node:test");
const assert = require("node:assert/strict");
const { validateChatInput, validateConsultationInput } = require("../src/lib/validate");

test("validateChatInput accepts a normal message", () => {
  const r = validateChatInput({ message: "hi there", sessionId: "abc" });
  assert.equal(r.valid, true);
});

test("validateChatInput rejects empty/missing message", () => {
  assert.equal(validateChatInput({}).valid, false);
  assert.equal(validateChatInput({ message: "" }).valid, false);
  assert.equal(validateChatInput({ message: "   " }).valid, false);
});

test("validateChatInput rejects a non-string sessionId", () => {
  const r = validateChatInput({ message: "hi", sessionId: 12345 });
  assert.equal(r.valid, false);
});

test("validateConsultationInput requires name and a well-formed email", () => {
  assert.equal(validateConsultationInput({ name: "A", email: "a@b.com" }).valid, true);
  assert.equal(validateConsultationInput({ name: "A", email: "not-an-email" }).valid, false);
  assert.equal(validateConsultationInput({ email: "a@b.com" }).valid, false);
  assert.equal(validateConsultationInput({ name: "A" }).valid, false);
});

test("validateConsultationInput enforces max lengths", () => {
  const longMessage = "x".repeat(1501);
  const r = validateConsultationInput({ name: "A", email: "a@b.com", message: longMessage });
  assert.equal(r.valid, false);
});

test("validateConsultationInput tolerates absent optional fields", () => {
  const r = validateConsultationInput({ name: "A", email: "a@b.com", company: "", service: "", message: "" });
  assert.equal(r.valid, true);
});
