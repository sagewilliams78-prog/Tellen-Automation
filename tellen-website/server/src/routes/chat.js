const express = require("express");
const config = require("../config");
const { validateChatInput } = require("../lib/validate");
const { recordTurn, getSession } = require("../lib/sessionStore");
const { generateMockReply } = require("../lib/mockChat");
const { callN8nChat } = require("../lib/n8nClient");
const { log, hash, preview } = require("../lib/logger");
const { chatLimiter } = require("../middleware/rateLimit");

const router = express.Router();

router.post("/chat", chatLimiter, async (req, res) => {
  const { valid, errors } = validateChatInput(req.body);
  if (!valid) {
    return res.status(400).json({ error: errors.join(" ") });
  }

  const message = req.body.message.trim();
  const sessionId = req.body.sessionId || "anon-" + req.ip;

  recordTurn(sessionId, "user", message);
  const session = getSession(sessionId);

  log("info", "chat_message_received", {
    sessionHash: hash(sessionId),
    ipHash: hash(req.ip),
    preview: preview(message),
    mock: config.chatMockMode,
  });

  if (config.chatMockMode) {
    const reply = generateMockReply(message, session);
    recordTurn(sessionId, "bot", reply);
    return res.json({ reply, mock: true });
  }

  const result = await callN8nChat(message, sessionId);
  if (!result.ok) {
    return res.status(result.status || 502).json({ error: result.error });
  }
  recordTurn(sessionId, "bot", result.reply);
  return res.json({ reply: result.reply });
});

module.exports = router;
