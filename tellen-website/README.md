# Tellen Automation — website groundwork

This is the audited/rebuilt version of `tellen-premium-v4.zip`, plus a new
floating chat widget, a secure Node/Express backend (chat proxy + lead
capture), draft legal copy, and tests. It runs entirely locally for now —
nothing here is deployed or publicly hosted yet.

## What changed from the uploaded prototype

The approved visual direction is untouched: metallic silver/electric-blue
T mark, navy/black palette, executive-office skyline hero, "Work Smarter.
Not Harder." messaging, pricing tiers and copy are all the same.

**Fixed:**
- The prototype was a single 2.4MB `index.html` because its logo, hero
  photo, and about-section image were embedded as base64 — including the
  nav/footer logo (465KB) being reused, full-resolution and unresized, as
  the page `<link rel="icon">`. That's a real mobile-performance problem:
  every visitor downloaded ~1.8MB of duplicated image data before seeing
  anything. Images are now external, correctly sized per their actual
  display size, and a proper favicon/apple-touch-icon/512px icon set was
  generated from the same approved logo. Initial HTML+CSS+JS is now
  ~59KB; total first-load weight (incl. images) is ~170KB.
- CSS was split into an external, cacheable stylesheet instead of three
  stacked inline `<style>` blocks.
- Added SEO/social metadata (Open Graph, Twitter card, canonical link,
  JSON-LD `Organization`), a web manifest, and `loading="lazy"` /
  `fetchpriority` hints.
- The consultation form previously only displayed a local text block for
  you to copy into your own email ("preview mode — does not send"). It
  now calls a real backend endpoint and only shows a success message
  after the server confirms it received the submission.

**Added:**
- A floating "Try Tellen AI" chat widget (launcher, panel, welcome
  message, typing indicator, retry-on-error, reset, keyboard submit,
  mobile layout, session isolation via a per-tab session id, and an
  always-visible AI disclosure line).
- A secure server-side proxy (`POST /api/chat`) so no webhook URL,
  API key, or credential is ever present in the page's HTML/JS. It
  validates input, caps payload size, rate-limits, times out, and
  degrades to a clearly-labeled **mock** assistant if no n8n webhook is
  configured. It's now wired to the real **"AI Receptionist
  (Multi-Client)"** n8n workflow by default (see "n8n connection"
  below) — `N8N_CHAT_WEBHOOK_URL` and `N8N_CLIENT_ID` in `.env` are
  already filled in.
- A real lead-capture backend (`POST /api/consultation`) with
  server-side validation, a honeypot anti-spam field (same pattern your
  n8n onboarding workflow already uses), per-IP rate limiting, and a
  local durable store (`server/data/leads.jsonl`) so a submission is
  never silently lost even before a real email/CRM destination exists.
- Expanded the draft Privacy Notice and Terms (AI disclosure, human
  oversight, data retention, third-party processing) — still clearly
  marked as drafts pending attorney review, not final legal advice.
- 17 automated tests (`npm test`) covering validation, the mock chat
  flow, session isolation, the honeypot, and both rate limiters.

## Project layout

```
public/            the static site (served as-is)
  index.html
  css/styles.css
  js/main.js            nav, pricing calculator, legal dialog, lead form
  js/chat-widget.js      floating chat widget
  assets/                optimized images, favicons, manifest
server/            the Node/Express backend
  src/index.js            app entry — serves public/ AND the API
  src/routes/chat.js       POST /api/chat
  src/routes/consultation.js   POST /api/consultation
  src/lib/                mock chat, n8n client, validation, session store, logger
  test/                    npm test
  .env.example
assets/raw/        (dev-only) the original images extracted from the prototype
scripts/           (dev-only) the extraction/optimization scripts used once
```

## Running it locally (desktop and phone)

```bash
cd server
npm install
npm run dev        # or: npm start
```

This single server serves the site **and** the API from one port
(default 3000), so there's nothing else to run.

- Desktop: open `http://localhost:3000`
- Phone, same Wi-Fi: find this computer's LAN IP (e.g. `192.168.1.23`)
  and open `http://192.168.1.23:3000` on the phone. The terminal output
  on startup prints this for you.

By default both the chat and the consultation form run in **mock mode** —
no external credentials needed, nothing leaves your machine. The terminal
log and `GET /healthz` both say explicitly whether each is in mock mode.

## Running the tests

```bash
cd server
npm test
```

17/17 passing as of this build: input validation, the mock chat reply
flow, session isolation between two different `sessionId`s, the
honeypot silently dropping bot submissions without storing them, and
both rate limiters actually triggering a 429 past their configured max.

## Configuration

Copy `server/.env.example` to `server/.env` and fill in real values when
they exist. Everything is optional — anything left blank keeps that
piece in mock mode. Key variables:

| Variable | Purpose |
|---|---|
| `N8N_CHAT_WEBHOOK_URL`, `N8N_CHAT_API_KEY` | Real chat backend. Blank = mock replies. |
| `LEAD_DESTINATION_EMAIL`, `LEAD_WEBHOOK_URL` | Where consultation submissions go. Blank = stored locally only. |
| `ALLOWED_ORIGINS` | Only needed if the site is ever hosted on a different origin than this API. |
| `CHAT_RATE_LIMIT_*`, `CONSULTATION_RATE_LIMIT_*` | Abuse limits, tuned conservatively for a low-traffic launch. |
| `FORCE_MOCK_MODE` | Keep mock replies even if real credentials are set — useful for demos. |

## n8n connection

The chat widget is wired to the "Customer Chat" trigger in your real
**"AI Receptionist (Multi-Client)"** n8n workflow (`sagesworld.app.n8n.cloud`)
— the same multi-tenant workflow your real clients (e.g. Fresh Cuts
Barbershop) use. A `tellen-automation` row was added to that workflow's
`clients` data table (services/pricing copy, Mon–Fri 9am–5pm Pacific
consultation hours, 30-minute slots, calendar/notifications on
`sagewilliams78@gmail.com`, a 500-messages/month cap so the public widget
can't run up usage unbounded, and no phone number given out). `.env` is
already set with the real webhook URL and `N8N_CLIENT_ID=tellen-automation`.

**What's been verified:** the client resolves correctly and the real AI
agent answers with accurate pricing/services — confirmed via a direct test
execution against the live workflow (n8n execution #184), not just code
review. **What hasn't:** an actual raw HTTP round-trip from this server to
`sagesworld.app.n8n.cloud` — the sandbox this was built in doesn't have
network access to that host, so `server/src/lib/n8nClient.js` was written
to defensively handle both of n8n's possible response shapes (a single
`{"output": ...}` JSON object, or n8n's streaming newline-delimited chunk
format) rather than being proven against the wire format. Test it for real
once this runs somewhere with normal internet access — open the chat
widget and ask it something. If it comes back with "The AI service
returned an unexpected response," tell me and I'll adjust the parser; a
guaranteed-reliable fallback is flipping the "Customer Chat" trigger's
response mode from streaming to "last node" in the n8n editor, which
would make replies non-streaming but removes all ambiguity (note: this
is a shared trigger, so it would also change how replies arrive for
Fresh Cuts Barbershop's widget, not just Tellen's).

A full consultation-booking round trip (confirming a time and having the
AI actually create a calendar event) was deliberately **not** tested here,
to avoid creating a stray real event on `sagewilliams78@gmail.com`'s
calendar — worth doing one real end-to-end booking test yourself before
launch.

## Launch blockers — do not treat the integration as live until these are resolved

1. **Hosting & domain.** This runs on `localhost` only right now. Pick a
   Node-capable host, set a real domain, and update the hardcoded
   `https://www.tellenautomation.com/` placeholders in `index.html`
   (canonical, Open Graph, JSON-LD) to the real domain. Once you have a
   real domain, consider setting the `allowed_domain` column on the
   `tellen-automation` clients-table row — the column exists but isn't
   currently enforced anywhere in the workflow, so today the chat is
   reachable by anyone who has (or guesses) the webhook URL and the
   `client_id`, same as the existing Fresh Cuts Barbershop client. Not a
   new issue introduced here, just worth knowing.
2. **Business email or CRM destination** for consultation leads. Right
   now they're validated, rate-limited, and durably stored in
   `server/data/leads.jsonl` — but nothing is emailed or pushed to a CRM
   yet. Set `LEAD_WEBHOOK_URL` (or extend `routes/consultation.js`
   directly) once you know where leads should actually go.
3. **Pricing approval.** $497/$997 Starter/Growth + setup fees and the
   $99/$149 add-ons are the proposed rates from the brief, already
   reflected consistently in the pricing cards, the fine print, and the
   estimate calculator (verified by an independent arithmetic check) —
   but they still need your sign-off as binding numbers.
4. **Legal review.** The Privacy Notice, Terms, and AI-disclosure copy in
   the footer dialog and `#disclosures` section are drafts written to be
   honest about current limitations — they are explicitly not final
   legal advice and say so in the UI itself.
5. **Security review of production config** before going live: set
   `NODE_ENV=production`, set `ALLOWED_ORIGINS` if the frontend and API
   ever split across origins, and consider moving `server/data/leads.jsonl`
   to a real database before meaningful volume arrives.

## Honest status

Local site runs end-to-end on phone and desktop. Chat widget works fully
in mock mode (verified by real HTTP requests, not just code review), and
is now wired to the real n8n "AI Receptionist" workflow by default.
Consultation form validates, rate-limits, stores, and only reports
success after a real backend confirmation. Pricing calculator math
verified independently. 17 automated tests pass (unaffected by the n8n
change — they force mock mode). **The n8n connection is verified at the
workflow level (a direct test execution against the live workflow
returned a correct, accurate reply) but not yet over a real HTTP request
from this server** — see "n8n connection" above for exactly what that
means and how to finish verifying it once this is deployed somewhere
with normal internet access.
