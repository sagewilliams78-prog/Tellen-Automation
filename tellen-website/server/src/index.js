const express = require("express");
const helmet = require("helmet");
const path = require("path");
const config = require("./config");
const { log } = require("./lib/logger");
const chatRoute = require("./routes/chat");
const consultationRoute = require("./routes/consultation");

const app = express();
app.disable("x-powered-by");
app.set("trust proxy", 1); // so req.ip is correct behind a reverse proxy/load balancer

// --- Security headers. CSP is scoped to what this single-origin site
// actually needs: inline <script type="application/ld+json"> plus the
// two first-party JS files, no third-party scripts at all. ---
app.use(
  helmet({
    contentSecurityPolicy: {
      directives: {
        defaultSrc: ["'self'"],
        scriptSrc: ["'self'"],
        styleSrc: ["'self'"],
        imgSrc: ["'self'", "data:"],
        connectSrc: ["'self'"],
        objectSrc: ["'none'"],
        baseUri: ["'self'"],
        frameAncestors: ["'self'"],
      },
    },
    crossOriginEmbedderPolicy: false,
  })
);

// --- CORS: only matters if the frontend is ever served from a different
// origin than this API (e.g. a static host + this server as a separate
// API host). When ALLOWED_ORIGINS is unset (the default local/dev setup,
// where this same server serves the frontend from /public) this is a
// no-op same-origin request and no CORS header is needed at all. ---
app.use((req, res, next) => {
  const origin = req.headers.origin;
  if (config.allowedOrigins.length > 0 && origin && config.allowedOrigins.includes(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
    res.setHeader("Vary", "Origin");
    res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  }
  if (req.method === "OPTIONS") return res.sendStatus(204);
  next();
});

// --- Body parsing with a hard payload size limit (defense against huge
// POST bodies; both API payloads are small by design). ---
app.use(express.json({ limit: "30kb" }));

// Friendly 400 instead of a stack trace when the client sends broken JSON.
app.use((err, req, res, next) => {
  if (err && err.type === "entity.parse.failed") {
    return res.status(400).json({ error: "Request body must be valid JSON." });
  }
  if (err && err.type === "entity.too.large") {
    return res.status(413).json({ error: "Request body too large." });
  }
  next(err);
});

app.get("/healthz", (req, res) => {
  res.json({
    ok: true,
    chatMockMode: config.chatMockMode,
    leadMockMode: config.leadMockMode,
  });
});

app.use("/api", chatRoute);
app.use("/api", consultationRoute);

// --- Static site ---
const PUBLIC_DIR = path.join(__dirname, "..", "..", "public");
app.use(
  express.static(PUBLIC_DIR, {
    extensions: ["html"],
    setHeaders(res, filePath) {
      // Hashless filenames here, so keep caching conservative; images can
      // cache longer since they're content-stable within a deploy.
      if (/\.(png|jpg|jpeg|webp|svg)$/i.test(filePath)) {
        res.setHeader("Cache-Control", "public, max-age=86400");
      } else {
        res.setHeader("Cache-Control", "no-cache");
      }
    },
  })
);

// --- 404 for unmatched API routes (after static, before generic error handler) ---
app.use("/api", (req, res) => {
  res.status(404).json({ error: "Not found." });
});

// --- Generic error handler (last resort; never leak stack traces to clients) ---
app.use((err, req, res, next) => {
  log("error", "unhandled_error", { message: err && err.message, path: req.path });
  res.status(500).json({ error: "Something went wrong." });
});

if (require.main === module) {
  app.listen(config.port, () => {
    log("info", "server_started", {
      port: config.port,
      nodeEnv: config.nodeEnv,
      chatMockMode: config.chatMockMode,
      leadMockMode: config.leadMockMode,
    });
    /* eslint-disable no-console */
    console.log(`\nTellen Automation server listening on http://localhost:${config.port}`);
    console.log(`  Chat API:          ${config.chatMockMode ? "MOCK mode (no N8N_CHAT_WEBHOOK_URL set)" : "LIVE -> " + config.n8nChatWebhookUrl}`);
    console.log(`  Consultation API:  ${config.leadMockMode ? "MOCK mode (stored locally only, no LEAD_WEBHOOK_URL/LEAD_DESTINATION_EMAIL set)" : "forwarding configured"}`);
    console.log(`  On your phone (same Wi-Fi): http://<this-computer's-LAN-IP>:${config.port}\n`);
  });
}

module.exports = app;
