const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function isNonEmptyString(v, maxLen) {
  return typeof v === "string" && v.trim().length > 0 && v.length <= (maxLen || 10000);
}

/** Validates a chat message body: { message, sessionId }. */
function validateChatInput(body) {
  const errors = [];
  if (!body || typeof body !== "object") {
    return { valid: false, errors: ["Request body must be a JSON object."] };
  }
  if (!isNonEmptyString(body.message, 1000)) {
    errors.push("message is required and must be a non-empty string of at most 1000 characters.");
  }
  if (body.sessionId !== undefined && body.sessionId !== null) {
    if (typeof body.sessionId !== "string" || body.sessionId.length > 128) {
      errors.push("sessionId must be a string of at most 128 characters.");
    }
  }
  return { valid: errors.length === 0, errors };
}

/** Validates a consultation/lead submission. */
function validateConsultationInput(body) {
  const errors = [];
  if (!body || typeof body !== "object") {
    return { valid: false, errors: ["Request body must be a JSON object."] };
  }
  if (!isNonEmptyString(body.name, 120)) {
    errors.push("name is required (max 120 characters).");
  }
  if (!isNonEmptyString(body.email, 200) || !EMAIL_RE.test(String(body.email).trim())) {
    errors.push("A valid business email is required.");
  }
  if (body.company !== undefined && body.company !== null && body.company !== "") {
    if (typeof body.company !== "string" || body.company.length > 150) {
      errors.push("company must be a string of at most 150 characters.");
    }
  }
  if (body.service !== undefined && body.service !== null && body.service !== "") {
    if (typeof body.service !== "string" || body.service.length > 80) {
      errors.push("service must be a string of at most 80 characters.");
    }
  }
  if (body.message !== undefined && body.message !== null && body.message !== "") {
    if (typeof body.message !== "string" || body.message.length > 1500) {
      errors.push("message must be at most 1500 characters.");
    }
  }
  return { valid: errors.length === 0, errors };
}

module.exports = { validateChatInput, validateConsultationInput, EMAIL_RE };
