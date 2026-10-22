#!/usr/bin/env python3

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
STATE_FILE = BASE / "_scheduled_state" / "crypto-status.json"
RULES_FILE = BASE / "crypto_rules.json"
TZ = ZoneInfo("America/Los_Angeles")


def _load(path, fallback):
    try:
        return json.loads(path.read_text())
    except Exception:
        return fallback


def build_crypto_status():
    state = _load(STATE_FILE, {})
    rules = _load(RULES_FILE, {})

    return {
        "generated_at": datetime.now(TZ).isoformat(),
        "desk": "Eva Crypto Desk",
        "asset": "BTC",
        "pair": "BTC-USD",
        "market": "24/7",
        "state": state,
        "rules": rules,
    }


def crypto_html():
    return r'''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eva Crypto Desk</title>
<style>
body{
  margin:0;
  background:#07090f;
  color:#e8edf7;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
}
.shell{
  max-width:1180px;
  margin:0 auto;
  padding:28px;
}
.top{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:20px;
}
h1{
  margin:0;
  font-size:30px;
}
.sub{
  opacity:.68;
  margin-top:5px;
}
.grid{
  display:grid;
  grid-template-columns:1.25fr .75fr;
  gap:18px;
  margin-top:22px;
}
.card{
  background:#0d111b;
  border:1px solid #252c39;
  border-radius:14px;
  padding:18px;
}
.price{
  font-size:42px;
  font-weight:800;
  margin:8px 0;
}
.row{
  display:grid;
  grid-template-columns:repeat(4,1fr);
  gap:10px;
  margin-top:16px;
}
.metric{
  background:#090c13;
  border:1px solid #202736;
  border-radius:10px;
  padding:12px;
}
.label{
  opacity:.55;
  font-size:11px;
  text-transform:uppercase;
}
.value{
  margin-top:5px;
  font-size:18px;
  font-weight:700;
}
.good{color:#8fe3a1}
.warn{color:#ffd37a}
.bad{color:#ff8d8d}
.spritebox{
  min-height:320px;
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  text-align:center;
  background:
    linear-gradient(rgba(255,255,255,.02) 1px,transparent 1px),
    linear-gradient(90deg,rgba(255,255,255,.02) 1px,transparent 1px),
    #090c13;
  background-size:20px 20px;
}
.sprite{
  width:220px;
  max-height:260px;
  object-fit:contain;
  image-rendering:pixelated;
}
.rules{
  line-height:1.7;
  font-size:13px;
}
.tools{
  margin-top:12px;
  font-size:12px;
  line-height:1.7;
}
a{color:#a8c7ff}
@media(max-width:850px){
  .grid{grid-template-columns:1fr}
  .row{grid-template-columns:1fr 1fr}
}
</style>
</head>
<body>
<div class="shell">
  <div class="top">
    <div>
      <h1>₿ EVA CRYPTO DESK</h1>
      <div class="sub">BTC-USD • 24/7 monitoring • Robinhood MCP capability watch</div>
    </div>
    <a href="/">← Trading HQ</a>
  </div>

  <div class="grid">
    <div>
      <div class="card">
        <div class="label">Bitcoin</div>
        <div id="price" class="price">Loading...</div>
        <div id="status" class="sub">Waiting for BTC telemetry</div>

        <div class="row">
          <div class="metric">
            <div class="label">24H High</div>
            <div id="high" class="value">--</div>
          </div>
          <div class="metric">
            <div class="label">24H Low</div>
            <div id="low" class="value">--</div>
          </div>
          <div class="metric">
            <div class="label">RSI 14</div>
            <div id="rsi" class="value">--</div>
          </div>
          <div class="metric">
            <div class="label">Trend</div>
            <div id="trend" class="value">--</div>
          </div>
        </div>
      </div>

      <div class="card rules" style="margin-top:18px">
        <b>Eva Crypto Rules</b><br>
        • BTC is isolated from the equity strategy.<br>
        • 5-minute candles drive the desk telemetry.<br>
        • EMA20 / EMA50 track trend direction.<br>
        • RSI14 tracks momentum and extension.<br>
        • Rolling 24-hour high/low provides range context.<br>
        • Every future live crypto order must be previewed first.<br>
        • No doubling down or increasing size to recover losses.
      </div>

      <div class="card tools">
        <b>Robinhood MCP Crypto</b>
        <div id="mcp">Checking...</div>
        <div id="tools"></div>
      </div>
    </div>

    <div class="card spritebox">
      <svg
        width="220"
        height="250"
        viewBox="0 0 220 250"
        shape-rendering="crispEdges"
        aria-label="Eva crypto sprite"
      >
        <rect x="70" y="18" width="80" height="12" fill="#202a42"/>
        <rect x="55" y="30" width="110" height="70" fill="#283551"/>
        <rect x="43" y="45" width="12" height="40" fill="#00d5ff"/>
        <rect x="165" y="45" width="12" height="40" fill="#00d5ff"/>

        <rect x="70" y="48" width="25" height="18" fill="#07090f"/>
        <rect x="125" y="48" width="25" height="18" fill="#07090f"/>

        <rect x="77" y="53" width="12" height="8" fill="#00ff9d"/>
        <rect x="132" y="53" width="12" height="8" fill="#00ff9d"/>

        <rect x="90" y="78" width="40" height="8" fill="#00d5ff"/>

        <rect x="62" y="105" width="96" height="85" fill="#141c2d"/>
        <rect x="82" y="118" width="56" height="45" fill="#090d17"/>
        <rect x="91" y="126" width="38" height="29" fill="#f7931a"/>

        <text
          x="110"
          y="149"
          text-anchor="middle"
          font-size="25"
          font-family="monospace"
          font-weight="bold"
          fill="#ffffff"
        >₿</text>

        <rect x="38" y="115" width="24" height="70" fill="#202a42"/>
        <rect x="158" y="115" width="24" height="70" fill="#202a42"/>

        <rect x="73" y="190" width="28" height="45" fill="#202a42"/>
        <rect x="119" y="190" width="28" height="45" fill="#202a42"/>

        <rect x="63" y="232" width="43" height="10" fill="#00d5ff"/>
        <rect x="114" y="232" width="43" height="10" fill="#00d5ff"/>
      </svg>
      <h2>Eva • Crypto Trader</h2>
      <div class="sub">Bitcoin desk operator</div>
      <div id="setup" style="margin-top:16px;font-weight:800">SCANNING</div>
    </div>
  </div>
</div>

<script>
const money = n => {
  if(n === null || n === undefined) return "--";
  return "$" + Number(n).toLocaleString(undefined,{
    minimumFractionDigits:2,
    maximumFractionDigits:2
  });
};

async function refresh(){
  try{
    const r = await fetch("/api/crypto",{cache:"no-store"});
    const d = await r.json();
    const s = d.state || {};

    document.getElementById("price").textContent = money(s.price);
    document.getElementById("high").textContent = money(s.high_24h);
    document.getElementById("low").textContent = money(s.low_24h);
    document.getElementById("rsi").textContent =
      s.rsi14 == null ? "--" : Number(s.rsi14).toFixed(1);

    document.getElementById("trend").textContent = s.trend || "--";
    document.getElementById("setup").textContent = s.setup || "SCANNING";

    document.getElementById("status").textContent =
      s.updated_at ? "Updated " + s.updated_at : "Waiting for telemetry";

    document.getElementById("mcp").textContent =
      s.mcp_connected ? "✅ Connected" : "⚠️ Not confirmed";

    document.getElementById("tools").textContent =
      (s.crypto_tools || []).join(" • ");

  }catch(e){
    document.getElementById("status").textContent =
      "Crypto telemetry unavailable: " + e;
  }
}

refresh();
setInterval(refresh,15000);
</script>
</body>
</html>'''
