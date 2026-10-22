const crypto = require("crypto");

/**
 * Privacy-conscious logger: never writes full message text, full email
 * addresses, or raw IPs to logs — only short redacted previews and a
 * one-way hash where an identifier is still useful for correlating
 * requests (e.g. spotting abuse) without storing the identifier itself.
 */

function hash(value) {
  if (!value) return "none";
  return crypto.createHash("sha256").update(String(value)).digest("hex").slice(0, 12);
}

function preview(text, max) {
  max = max || 40;
  if (!text) return "";
  const clean = String(text).replace(/\s+/g, " ").trim();
  return clean.length > max ? clean.slice(0, max) + "…" : clean;
}

function redactEmail(email) {
  if (!email || typeof email !== "string") return "none";
  const at = email.indexOf("@");
  if (at <= 0) return "invalid";
  return email.slice(0, 1) + "***@" + email.slice(at + 1);
}

function log(level, event, fields) {
  const entry = Object.assign(
    { ts: new Date().toISOString(), level, event },
    fields || {}
  );
  const line = JSON.stringify(entry);
  if (level === "error") console.error(line);
  else console.log(line);
}

module.exports = { log, hash, preview, redactEmail };
