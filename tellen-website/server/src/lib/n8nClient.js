const config = require("../config");
const { log, hash } = require("./logger");

/**
 * Calls the real n8n chat webhook — the "Customer Chat" trigger in the
 * "AI Receptionist (Multi-Client)" workflow. That trigger is n8n's native
 * Chat Trigger node, not a generic custom webhook, so the request/response
 * shape below matches ITS protocol (confirmed against the live workflow):
 *
 *   Request body:  { action: "sendMessage", chatInput, sessionId, metadata: { client_id, api_key } }
 *   Response:      either a single JSON object ({ output: "..." }, non-streaming),
 *                  or a chunked newline-delimited stream of
 *                  { type: "begin" | "item" | "end", content?: "..." } objects
 *                  (the node's configured "streaming" response mode).
 *
 * api_key travels inside metadata, in the BODY, not as an Authorization
 * header: the Chat Trigger node has no way to read raw HTTP headers, so a
 * header here would be silently ignored server-side (confirmed against the
 * node's own parameter schema — it only supports basicAuth/n8nUserAuth/none,
 * none of which this client was using anyway). This is the whole point of
 * the field: the shared chat webhook URL is public to every client's own
 * deployed server, so n8n checks this value in a "Verify Chat Secret" node
 * right after the trigger and routes anything that doesn't match to a
 * rejection reply, instead of running the agent for an unverified caller.
 *
 * This client handles both response shapes defensively, because the exact
 * wire format of the streaming mode could not be verified from this
 * environment (the n8n host is outside this sandbox's network allowlist —
 * confirmed via the agent proxy as a policy denial, not an n8n error). It
 * was verified against the live workflow through n8n's own execution API
 * instead (manual test run, execution 184: resolves the "tellen-automation"
 * client correctly and returns a real agent reply). Test the live HTTP path
 * once this runs somewhere with network access to sagesworld.app.n8n.cloud.
 *
 * Never fabricates a reply: any shape we don't recognize is treated as an
 * upstream error, not papered over with a generic response.
 */
async function callN8nChat(message, sessionId) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), config.n8nTimeoutMs);

  try {
    const res = await fetch(config.n8nChatWebhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "sendMessage",
        chatInput: message,
        sessionId,
        metadata: { client_id: config.n8nClientId, api_key: config.n8nChatApiKey },
      }),
      signal: controller.signal,
    });

    if (!res.ok) {
      log("error", "n8n_chat_upstream_error", { status: res.status, sessionHash: hash(sessionId) });
      return { ok: false, status: 502, error: "The AI service returned an error. Please try again." };
    }

    const raw = await res.text();
    const reply = extractReply(raw);

    if (reply === null) {
      log("error", "n8n_chat_unexpected_shape", { sessionHash: hash(sessionId), bodyPreview: raw.slice(0, 120) });
      return { ok: false, status: 502, error: "The AI service returned an unexpected response." };
    }

    return { ok: true, reply };
  } catch (err) {
    const timedOut = err && err.name === "AbortError";
    log("error", "n8n_chat_request_failed", { sessionHash: hash(sessionId), timedOut, message: err && err.message });
    return {
      ok: false,
      status: timedOut ? 504 : 502,
      error: timedOut ? "The AI service took too long to respond." : "Couldn't reach the AI service.",
    };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Pulls the assistant's reply text out of either response shape the Chat
 * Trigger node can send. Returns null (never a guessed/empty string) when
 * the body doesn't match a known shape, so the caller treats it as a real
 * upstream error instead of silently returning nothing useful.
 */
function extractReply(raw) {
  const text = (raw || "").trim();
  if (!text) return null;

  // Shape 1: a single JSON object/array (non-streaming "lastNode" mode).
  try {
    const parsed = JSON.parse(text);
    const fromSingle = replyFromObject(parsed);
    if (fromSingle !== null) return fromSingle;
    if (Array.isArray(parsed)) {
      for (const item of parsed) {
        const fromItem = replyFromObject(item);
        if (fromItem !== null) return fromItem;
      }
    }
  } catch (_) {
    // Not a single JSON document — fall through to streaming parse below.
  }

  // Shape 2: newline-delimited JSON chunks (streaming mode): concatenate
  // every "item" chunk's content until an "end" chunk (or end of body).
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  let combined = "";
  let sawItem = false;
  for (const line of lines) {
    const payload = line.startsWith("data:") ? line.slice(5).trim() : line;
    if (!payload || payload === "[DONE]") continue;
    let chunk;
    try {
      chunk = JSON.parse(payload);
    } catch (_) {
      continue;
    }
    if (chunk && chunk.type === "item" && typeof chunk.content === "string") {
      combined += chunk.content;
      sawItem = true;
    } else if (chunk && typeof chunk === "object") {
      const fromChunk = replyFromObject(chunk);
      if (fromChunk !== null) {
        combined += fromChunk;
        sawItem = true;
      }
    }
  }

  return sawItem ? combined : null;
}

function replyFromObject(obj) {
  if (!obj || typeof obj !== "object") return null;
  if (typeof obj.output === "string") return obj.output;
  if (typeof obj.reply === "string") return obj.reply;
  if (typeof obj.text === "string") return obj.text;
  if (obj.json && typeof obj.json.output === "string") return obj.json.output;
  return null;
}

module.exports = { callN8nChat };
