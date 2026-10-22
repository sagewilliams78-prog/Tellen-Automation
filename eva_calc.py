#!/usr/bin/env python3
"""
Real strategy math, callable from the command line -- built for the
scheduled-task version of Eva (eva-live-scan) so that invocation NEVER
re-derives stop/target/sizing/zone math itself. It calls this, which
imports the exact same functions sage_bot_v13.py has always used
(zone_of, compute_stop, compute_target, zone_width_ok, size_position).
One source of truth for the strategy's real math, not a parallel copy
that could quietly drift from it.

sage_bot_v13.py is safe to import: everything below module scope is
inside `if __name__ == "__main__":`, and the one top-level side effect
(load_secrets()) just reads the bot's own already-valid local secrets
file -- no network call, no side effect beyond that.

Usage:
    python3 eva_calc.py zone_of '{"price": 10.5, "lv": {"rh": 11, "rl": 10, "sh": 11.5, "sl": 9.5}}'
    python3 eva_calc.py compute_stop '{"entry": 10.5, "sl": 9.5}'
    python3 eva_calc.py compute_target '{"lv": {"rh": 11, "rl": 10}}'
    python3 eva_calc.py zone_width_ok '{"lv": {"rl": 10, "sl": 9.5}}'
    python3 eva_calc.py size_position '{"sym": "AMD", "price": 471.74, "stop": 460.0, "frac_ok": {"AMD": true}}'

Each prints one line of JSON: {"ok": true, "result": ...} or {"ok": false, "error": "..."}.
"""
import json
import sys

sys.path.insert(0, "/Users/sagewilliams/Desktop/Sages trading bot")
import sage_bot_v13 as eva  # noqa: E402  (path insert must come first)

FUNCS = {
    "zone_of": lambda a: eva.zone_of(a["price"], a["lv"]),
    "compute_stop": lambda a: eva.compute_stop(a["entry"], a["sl"]),
    "compute_target": lambda a: eva.compute_target(a["lv"]),
    "zone_width_ok": lambda a: eva.zone_width_ok(a["lv"]),
    "size_position": lambda a: eva.size_position(a["sym"], a["price"], a["stop"], a["frac_ok"]),
}


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in FUNCS:
        print(json.dumps({"ok": False, "error": f"usage: eva_calc.py <{'|'.join(FUNCS)}> '<json args>'"}))
        sys.exit(1)
    name, raw_args = sys.argv[1], sys.argv[2]
    try:
        args = json.loads(raw_args)
        result = FUNCS[name](args)
        print(json.dumps({"ok": True, "result": result}))
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
