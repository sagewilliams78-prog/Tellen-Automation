const rateLimit = require("express-rate-limit");
const config = require("../config");

const chatLimiter = rateLimit({
  windowMs: config.chatRateLimitWindowMs,
  max: config.chatRateLimitMax,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "You're sending messages too quickly. Please wait a moment and try again." },
});

const consultationLimiter = rateLimit({
  windowMs: config.consultationRateLimitWindowMs,
  max: config.consultationRateLimitMax,
  standardHeaders: true,
  legacyHeaders: false,
  message: { success: false, error: "Too many requests from this network. Please try again later." },
});

module.exports = { chatLimiter, consultationLimiter };
