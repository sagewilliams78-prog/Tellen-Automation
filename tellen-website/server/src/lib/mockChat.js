/**
 * Rule-based mock chat reply generator.
 *
 * This stands in for the real n8n AI workflow until its webhook URL,
 * auth, and response schema are provided (see README "Launch blockers").
 * It is NOT an AI model — it's a small set of keyword-matched canned
 * replies so the widget and proxy can be fully exercised end to end.
 * Every reply is honest about being a demo.
 */

const RULES = [
  {
    test: /\b(hi|hello|hey|good (morning|afternoon|evening))\b/i,
    reply: "Hey there! I'm the Tellen AI demo assistant. I can tell you about our services, pricing, or how a real deployment would work for your business. What would you like to know?",
  },
  {
    test: /\bpric(e|ing)|cost|how much\b/i,
    reply: "Our proposed packages are Starter at $497/mo (+$750 setup) and Growth at $997/mo (+$1,500 setup), with Enterprise custom-quoted. Optional add-ons: SMS follow-up (+$99/mo) and advanced reporting (+$149/mo). You can play with the estimate calculator further down the page — these are proposed rates pending written agreement.",
  },
  {
    test: /\breceptionist|answer(ing)? (calls|phone)/i,
    reply: "An AI receptionist can greet callers or chatters, answer common questions, collect their details, and route urgent issues to a real person. It's configured around your actual services and hours, with human escalation built in.",
  },
  {
    test: /\bschedul|appointment|booking/i,
    reply: "Smart scheduling connects booking requests to the calendar or tools your team already uses, with reminders handled automatically. We'd confirm the exact calendar/CRM during setup.",
  },
  {
    test: /\bfollow[- ]?up|lead\b/i,
    reply: "Lead follow-up automation captures inquiries as they come in and helps your team follow up consistently instead of leads going cold. It pairs well with the AI receptionist and scheduling pieces.",
  },
  {
    test: /\bhvac|plumb|electric|propert(y|ies)|service business/i,
    reply: "We're starting with Southern California HVAC, plumbing, electrical, and property management teams, since those businesses lose the most to missed calls and slow follow-up. A real deployment is tailored to your exact workflow.",
  },
  {
    test: /\bhow (does|do) (it|this) work|how it works|process\b/i,
    reply: "Four steps: a consultation to learn your business, building and integrating the workflow with your approved tools, testing and optimizing before broader use, then ongoing support and improvement.",
  },
  {
    test: /\bhuman|person|real person|talk to someone|oversight\b/i,
    reply: "Good question — every Tellen deployment includes human escalation paths and oversight. This demo chat itself is AI, not a person; for anything urgent, use the consultation form and a real person will follow up.",
  },
  {
    test: /\b(thanks|thank you|appreciate it)\b/i,
    reply: "You're welcome! Anything else you'd like to know about Tellen Automation, or would you like help preparing a consultation request?",
  },
];

const FALLBACK = "I can speak to our services, pricing, and how deployments work — could you rephrase, or ask about one of those? For anything specific to your business, the consultation form below connects you with a real person.";

function generateMockReply(message, session) {
  const text = String(message || "");
  for (const rule of RULES) {
    if (rule.test.test(text)) return rule.reply;
  }
  if (session && session.messageCount === 1) {
    return "Thanks for trying the demo! I'm a simple rule-based stand-in right now (the real n8n AI workflow isn't connected yet). Try asking about pricing, services, or how it works.";
  }
  return FALLBACK;
}

module.exports = { generateMockReply };
