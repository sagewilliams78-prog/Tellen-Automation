"""
Custom icon set replacing the generic unicode glyphs (☎ ▦ ϟ ⚙ ♧ ▤ ◇ ✧) with
hand-built SVGs matching the site's line weight and the logo's faceted,
geometric character. Each is 24x24, stroke-based, sized via `width/height:
1em` so the existing .ico font-size/color/drop-shadow rules keep working
unchanged.
"""

SW = 'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"'

PHONE = f'<svg viewBox="0 0 24 24" {SW}><path d="M4.5 4.5h2.8l1.1 3.9-1.8 1.6a12.3 12.3 0 0 0 5.9 5.9l1.6-1.8 3.9 1.1v2.8c0 .7-.6 1.2-1.3 1.1C10.4 18.4 5.6 13.6 4 7.3a1.2 1.2 0 0 1 1.1-1.3Z"/></svg>'

CALENDAR = f'<svg viewBox="0 0 24 24" {SW}><rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17"/><path d="M8 3v3M16 3v3"/><path d="m8.5 14 2 2 4-4.5"/></svg>'

FOLLOWUP = f'<svg viewBox="0 0 24 24" {SW}><path d="M4.5 12.2a7.5 7.5 0 1 1 3.1 6.1L4 19l.9-3.4a7.4 7.4 0 0 1-.4-3.4Z"/><path d="M9 12.5 11.5 10l2 2L17 8.5"/><path d="M14.3 8.5h2.7v2.7"/></svg>'

AUTOMATION = f'<svg viewBox="0 0 24 24" {SW}><path d="M12 15.3a3.3 3.3 0 1 0 0-6.6 3.3 3.3 0 0 0 0 6.6Z"/><path d="M19.3 13.6c-.2.6 0 1.3.5 1.7l.1.1a1.8 1.8 0 1 1-2.6 2.6l-.1-.1a1.6 1.6 0 0 0-1.7-.3 1.6 1.6 0 0 0-1 1.5v.2a1.8 1.8 0 1 1-3.6 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a1.8 1.8 0 1 1-2.6-2.6l.1-.1a1.6 1.6 0 0 0 .3-1.7 1.6 1.6 0 0 0-1.5-1h-.2a1.8 1.8 0 0 1 0-3.6h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a1.8 1.8 0 1 1 2.6-2.6l.1.1a1.6 1.6 0 0 0 1.7.3h.1a1.6 1.6 0 0 0 1-1.5V3a1.8 1.8 0 1 1 3.6 0v.1a1.6 1.6 0 0 0 1 1.5c.6.2 1.3 0 1.7-.3l.1-.1a1.8 1.8 0 1 1 2.6 2.6l-.1.1a1.6 1.6 0 0 0-.3 1.7v.1c.2.6.8 1 1.5 1h.2a1.8 1.8 0 0 1 0 3.6h-.1a1.6 1.6 0 0 0-1.5 1Z"/></svg>'

VOICE = f'<svg viewBox="0 0 24 24" {SW}><path d="M4.5 12.3a7.5 7.5 0 1 1 3.2 6.1L4 19.2l.9-3.6a7.3 7.3 0 0 1-.4-3.3Z"/><path d="M9 13v-2.3M12.2 14v-4.3M15.4 13v-2.3"/></svg>'

AGENT = f'<svg viewBox="0 0 24 24" {SW}><path d="M12 3 4.5 12 12 21l7.5-9L12 3Z"/><path d="M12 3v18M4.5 12h15"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/></svg>'

TARGET = f'<svg viewBox="0 0 24 24" {SW}><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4.3"/><circle cx="12" cy="12" r="0.9" fill="currentColor" stroke="none"/></svg>'

CHIP = f'<svg viewBox="0 0 24 24" {SW}><rect x="7" y="7" width="10" height="10" rx="1.5"/><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6.5 6.5l-2-2M17.5 6.5l2-2M6.5 17.5l-2 2M17.5 17.5l2 2"/></svg>'

EYE = f'<svg viewBox="0 0 24 24" {SW}><path d="M2.5 12S6 5.8 12 5.8 21.5 12 21.5 12 18 18.2 12 18.2 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/></svg>'

REPLACEMENTS = [
    ('<span class="ico" aria-hidden="true">☎</span><div><strong>AI Receptionist</strong><small>Help respond around the clock</small></div>',
     f'<span class="ico" aria-hidden="true">{PHONE}</span><div><strong>AI Receptionist</strong><small>Help respond around the clock</small></div>'),
    ('<span class="ico" aria-hidden="true">▦</span><div><strong>Smart Scheduling</strong><small>Streamline appointment booking</small></div>',
     f'<span class="ico" aria-hidden="true">{CALENDAR}</span><div><strong>Smart Scheduling</strong><small>Streamline appointment booking</small></div>'),
    ('<span class="ico" aria-hidden="true">ϟ</span><div><strong>Lead Follow-Up</strong><small>Keep conversations moving</small></div>',
     f'<span class="ico" aria-hidden="true">{FOLLOWUP}</span><div><strong>Lead Follow-Up</strong><small>Keep conversations moving</small></div>'),
    ('<span class="ico" aria-hidden="true">⚙</span><div><strong>Custom Automations</strong><small>Built around your business</small></div>',
     f'<span class="ico" aria-hidden="true">{AUTOMATION}</span><div><strong>Custom Automations</strong><small>Built around your business</small></div>'),

    ('<div class="ico" aria-hidden="true">☎</div><h3>AI Receptionist</h3>',
     f'<div class="ico" aria-hidden="true">{PHONE}</div><h3>AI Receptionist</h3>'),
    ('<div class="ico" aria-hidden="true">▦</div><h3>Appointment Scheduling</h3>',
     f'<div class="ico" aria-hidden="true">{CALENDAR}</div><h3>Appointment Scheduling</h3>'),
    ('<div class="ico" aria-hidden="true">♧</div><h3>Lead Follow-Up</h3>',
     f'<div class="ico" aria-hidden="true">{FOLLOWUP}</div><h3>Lead Follow-Up</h3>'),
    ('<div class="ico" aria-hidden="true">⚙</div><h3>Business Automation</h3>',
     f'<div class="ico" aria-hidden="true">{AUTOMATION}</div><h3>Business Automation</h3>'),
    ('<div class="ico" aria-hidden="true">▤</div><h3>Voice &amp; Chat AI</h3>',
     f'<div class="ico" aria-hidden="true">{VOICE}</div><h3>Voice &amp; Chat AI</h3>'),
    ('<div class="ico" aria-hidden="true">◇</div><h3>Custom AI Agents</h3>',
     f'<div class="ico" aria-hidden="true">{AGENT}</div><h3>Custom AI Agents</h3>'),

    ('<span class="ico" aria-hidden="true">✧</span><div><strong>Mission-Focused</strong>',
     f'<span class="ico" aria-hidden="true">{TARGET}</span><div><strong>Mission-Focused</strong>'),
    ('<span class="ico" aria-hidden="true">⚙</span><div><strong>Practical Technology</strong>',
     f'<span class="ico" aria-hidden="true">{CHIP}</span><div><strong>Practical Technology</strong>'),
    ('<span class="ico" aria-hidden="true">♧</span><div><strong>Human Oversight</strong>',
     f'<span class="ico" aria-hidden="true">{EYE}</span><div><strong>Human Oversight</strong>'),
]
