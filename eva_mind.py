#!/usr/bin/env python3
"""
Eva's Mind -- an Obsidian vault she writes to and reasons from.

WHAT THIS IS
------------
A linked markdown knowledge base at ~/EvaMind. Every setup Eva scores, every
trade she takes, and every session she runs becomes a note, and the notes link
to each other with [[wikilinks]]. Open the folder in Obsidian and the graph is
navigable: a factor links to the trades that tested it, a symbol links to the
sessions it appeared in, a lesson links to the evidence behind it.

WHY A VAULT AND NOT A DATABASE
-------------------------------
The point is not storage -- trading_log_v9.csv already stores. The point is
that reasoning has to be inspectable. Eva's earlier optimisations were
unverifiable because the only record was four rows of completed trades: there
was no way to ask "why did she skip this" or "which factor was actually
carrying the decision." Notes hold the reasoning next to the outcome, and
wikilinks make the connections traversable by a person, not just queryable by
a script.

THE DANGER THIS IS BUILT AGAINST
---------------------------------
"Learn over time" naturally means "adjust the weights from results." That is
curve-fitting wearing a friendlier name, and on 2026-09-02 fourteen separate
parameter sweeps produced nothing that survived three splits. With six factors
and a few dozen live trades, an auto-tuning Eva would fit noise inside a week
and the fit would be invisible.

So this vault ACCUMULATES and SURFACES. It computes how well each factor
actually predicted outcomes and writes that down honestly, including when the
answer is "not enough data" -- which it will be for a long time. A lesson is
marked ACTIONABLE only when MIN_SAMPLES_PER_BUCKET trades support it. Changing
a weight stays a human decision, made against evidence the vault makes legible.
"""

import os
import re
from collections import defaultdict
from datetime import datetime

VAULT = os.path.expanduser("~/EvaMind")

# A factor's win rate means nothing on six trades. Below this, a lesson is
# written as OBSERVATION, never ACTIONABLE. Chosen to be deliberately awkward:
# it should feel slow, because acting early is the failure mode.
MIN_SAMPLES_PER_BUCKET = 30

FACTOR_TITLES = {
    "reward_risk": "Reward to Risk",
    "zone_width": "Zone Width",
    "candle": "Candle Strength",
    "depth": "Depth Into Zone",
    "volume": "Volume Confirmation",
    "spread": "Spread Cost",
}

FACTOR_MEANING = {
    "reward_risk": (
        "Distance to target versus distance to stop, net of the round-trip "
        "spread. The old filter cascade never measured this at all, which is "
        "how a setup needing a 92% win rate reached the order queue."),
    "zone_width": (
        "How far the buy zone runs from yesterday's low down to the 5-day "
        "low. Was a hard 3% gate; as a score, a 2.96% zone loses two points "
        "instead of being silently disqualified."),
    "candle": (
        "Body size as a share of the bar's range. Was a binary bullish test, "
        "which discarded a doji sitting exactly on the low."),
    "depth": (
        "How far below the range low price actually traded. Buying near the "
        "floor is a different trade from buying at the ceiling; the cascade "
        "treated them as identical."),
    "volume": (
        "Bar volume against its 20-bar average -- evidence somebody else is "
        "defending the level. Tracked by v13 but never allowed to matter, "
        "because gating on it reduced P&L."),
    "spread": (
        "The round-trip cost of the symbol itself. IBRX at 0.127% consumes a "
        "0.4% target; NVDA at 0.005% does not. Cheap symbols were never given "
        "credit for being cheap."),
}


def _slug(s):
    return re.sub(r"[^A-Za-z0-9\- ]", "", str(s)).strip().replace(" ", "-")


def write_note(folder, name, body, front=None):
    """Write one note. Frontmatter stays minimal -- Obsidian reads it, and so
    does a person skimming the file in a terminal."""
    d = os.path.join(VAULT, folder) if folder else VAULT
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{_slug(name)}.md")
    parts = []
    if front:
        parts.append("---")
        for k, v in front.items():
            parts.append(f"{k}: {v}")
        parts.append("---\n")
    parts.append(body.rstrip() + "\n")
    with open(path, "w") as f:
        f.write("\n".join(parts))
    return path


def _bar(pct, width=28):
    n = int(round(pct / 100 * width))
    return "█" * n + "·" * (width - n)


# --------------------------------------------------------------- factor notes
def factor_note(factor, buckets, overall_wr):
    """buckets: {points 0-5: {"n": int, "wins": int, "pnl": float}}

    The heart of the vault. For each score band this asks the only question
    that matters: did trades scoring high on this factor actually do better
    than trades scoring low? If not, the factor is decoration and the weight
    is unjustified -- and the note says so plainly.
    """
    title = FACTOR_TITLES.get(factor, factor)
    total = sum(b["n"] for b in buckets.values())
    lines = [f"# {title}", "", FACTOR_MEANING.get(factor, ""), "",
             f"Part of [[Eva Scoring Model]]. Scored 0-5, equal weight with the "
             f"other five factors.", "",
             "## Did this factor predict anything?", ""]

    if total == 0:
        lines += ["No scored trades recorded yet.", ""]
        return "\n".join(lines)

    lines += ["| Points | Trades | Win rate | Avg P&L | |",
              "|---|---|---|---|---|"]
    ordered = sorted(buckets.items())
    for pts, b in ordered:
        if not b["n"]:
            continue
        wr = b["wins"] / b["n"] * 100
        avg = b["pnl"] / b["n"]
        lines.append(f"| {pts} | {b['n']} | {wr:.0f}% | ${avg:+.3f} | `{_bar(wr)}` |")
    lines.append("")

    # Does the factor separate outcomes monotonically? A real factor should
    # produce better results at higher scores. A jagged profile is noise.
    scored = [(p, b) for p, b in ordered if b["n"] >= 5]
    verdict = "NOT ENOUGH DATA"
    detail = ""
    if len(scored) >= 3:
        lo = [b for p, b in scored if p <= 2]
        hi = [b for p, b in scored if p >= 4]
        if lo and hi:
            lo_n = sum(b["n"] for b in lo); hi_n = sum(b["n"] for b in hi)
            lo_wr = sum(b["wins"] for b in lo) / lo_n * 100
            hi_wr = sum(b["wins"] for b in hi) / hi_n * 100
            lo_avg = sum(b["pnl"] for b in lo) / lo_n
            hi_avg = sum(b["pnl"] for b in hi) / hi_n
            gap = hi_wr - lo_wr
            enough = min(lo_n, hi_n) >= MIN_SAMPLES_PER_BUCKET
            detail = (f"Low band (0-2): {lo_n} trades, {lo_wr:.0f}% win, "
                      f"${lo_avg:+.3f} avg.\n"
                      f"High band (4-5): {hi_n} trades, {hi_wr:.0f}% win, "
                      f"${hi_avg:+.3f} avg.\n\n"
                      f"Separation: **{gap:+.0f} points of win rate**, "
                      f"**${hi_avg-lo_avg:+.3f} of average P&L**.")
            if not enough:
                verdict = (f"OBSERVATION ONLY -- needs {MIN_SAMPLES_PER_BUCKET} "
                           f"trades per band, has {min(lo_n, hi_n)}")
            elif gap >= 5 and hi_avg > lo_avg:
                verdict = "PREDICTIVE -- high scores really do trade better"
            elif gap <= -5 or hi_avg < lo_avg:
                verdict = ("INVERTED -- high scores trade WORSE. The weight is "
                           "not justified and this factor should be questioned.")
            else:
                verdict = ("NO SIGNAL -- scoring high on this changes nothing "
                           "measurable. Decoration, not information.")

    lines += [f"**Verdict: {verdict}**", "", detail, "",
              "## What would change this", "",
              f"This note is rewritten every time [[Eva Mind Review]] runs. "
              f"A verdict only becomes actionable at "
              f"{MIN_SAMPLES_PER_BUCKET}+ trades per band, because a win rate "
              f"on a dozen trades is noise wearing a number.", ""]
    return "\n".join(lines)


# -------------------------------------------------------------- session notes
def session_note(date, stats, notable=None):
    lines = [f"# Session {date}", "",
             f"- Setups scored: **{stats.get('scored', 0)}**",
             f"- Cleared threshold: **{stats.get('passed', 0)}**",
             f"- Trades taken: **{stats.get('trades', 0)}**",
             f"- Net P&L: **${stats.get('pnl', 0):+.2f}**", ""]
    if stats.get("scored"):
        lines += [f"- Median score: {stats.get('median_score', 0)}/30", ""]
    if notable:
        lines += ["## Worth remembering", ""] + [f"- {x}" for x in notable] + [""]
    lines += ["Links: [[Index]] · [[Eva Scoring Model]]", ""]
    return "\n".join(lines)


# --------------------------------------------------------------- symbol notes
def symbol_note(sym, rec):
    n = rec["n"]
    wr = rec["wins"] / n * 100 if n else 0
    lines = [f"# {sym}", "",
             f"- Scored setups: **{n}**",
             f"- Taken: **{rec['taken']}**",
             f"- Win rate when taken: **{wr:.0f}%**",
             f"- Net P&L: **${rec['pnl']:+.2f}**",
             f"- Average score: **{rec['score_sum']/n:.1f}/30**" if n else "",
             f"- Spread: **{rec['spread']:.3f}%**", "",
             "## Why Eva does or doesn't like this symbol", ""]
    if rec["spread"] > 0.07:
        lines.append(f"- Expensive to trade. At {rec['spread']:.3f}% round trip, "
                     f"a 0.4% target loses a third of its edge to cost alone.")
    if n and rec["score_sum"] / n < 15:
        lines.append("- Scores poorly on average -- its setups tend to be "
                     "structurally weak, not just unlucky.")
    if rec["taken"] and rec["pnl"] < 0:
        lines.append("- Has cost money on balance so far.")
    lines += ["", "Links: [[Index]] · [[Eva Scoring Model]]", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------- index
def rebuild_index(factors, symbols, sessions, headline):
    lines = ["# Eva's Mind", "",
             "What Eva has actually learned, kept as linked notes rather than "
             "log lines, so the reasoning stays inspectable.", "",
             f"*Last rebuilt {datetime.now():%Y-%m-%d %H:%M}*", "",
             "## The headline", "", headline, "",
             "## The scoring model", "", "- [[Eva Scoring Model]]", "",
             "## Factors", ""]
    for f in factors:
        lines.append(f"- [[{FACTOR_TITLES.get(f, f)}]]")
    lines += ["", "## Symbols", ""]
    for s in sorted(symbols):
        lines.append(f"- [[{s}]]")
    lines += ["", "## Sessions", ""]
    for d in sorted(sessions, reverse=True)[:40]:
        lines.append(f"- [[Session {d}]]")
    lines += ["", "## How to read this", "",
              "A factor note answers one question: did setups scoring high on "
              "that factor actually trade better? Verdicts are OBSERVATION "
              f"until {MIN_SAMPLES_PER_BUCKET} trades support each band. "
              "Nothing here changes how Eva trades on its own -- adjusting a "
              "weight is a human decision, deliberately.", ""]
    return "\n".join(lines)


def model_note():
    return """# Eva Scoring Model

Six factors, equal weight, 0-5 each, 30 maximum. Entry threshold **21**.

- [[Reward to Risk]]
- [[Zone Width]]
- [[Candle Strength]]
- [[Depth Into Zone]]
- [[Volume Confirmation]]
- [[Spread Cost]]

## Why scoring replaced filters

The old design AND-ed its filters, so they compounded and none could see any
other:

```
141,960 bars -> 36,368 in buy zone -> 11,687 past the 3% width gate
             -> 5,308 past the bullish-candle gate
```

3.7% survived, and 45% of survivors still had reward-to-risk below 0.50. The
cascade selected FEW setups, not GOOD ones. On 2026-09-02 it made both errors
at once: TSLA rejected at 2.96% zone width after 37 buy-zone visits, XOM
accepted at 4.25% with a reward-to-risk of 0.09.

## Measured

96 sessions, 20 symbols, $250, real spreads and slot limits:

| | filter cascade | score >= 21 |
|---|---|---|
| net P&L | $15.81 | **$48.21** |
| profit factor | 1.19 | **1.61** |
| green days | 42% | **52%** |
| worst day | -$9.96 | **-$7.59** |

Thresholds 21, 22 and 23 all beat the cascade on profit and green days across
all three train/test splits -- a plateau rather than a spike.

## What is not proven

One dataset, one rallying market, never a downtrend. A bug in that same
simulator produced a fake 315% return the same day it was built; it was caught
because 315% is absurd, and a 3x result is not absurd enough to trip the same
alarm. The weights were fixed on trading reasoning before any result was seen
and have not been tuned since -- if the model only works after adjusting them,
it does not work.
"""
