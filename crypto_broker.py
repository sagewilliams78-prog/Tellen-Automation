#!/usr/bin/env python3
"""
EVA CRYPTO v1 -- Robinhood execution layer.

Robinhood is EXECUTION TRUTH. Positions, orders, buying power and tradable
prices all come from here; nothing in this system infers them.

Deliberately isolated from signal generation. This module never decides WHAT
to trade -- it reports broker state and, when explicitly told to, places an
order that the risk engine has already approved.

Two rules that are not negotiable:
  1. Never assume an order filled because the API call returned. Always
     re-read real broker state afterwards.
  2. Never blindly retry after an execution error -- the first order may have
     reached the broker. Query orders/positions first, then decide.
"""

import json
import uuid
from datetime import datetime, timezone

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from robinhood_oauth_v13 import build_robinhood_oauth

MCP_URL = "https://agent.robinhood.com/mcp/trading"


def _text(result):
    try:
        return " ".join(getattr(c, "text", "") for c in (result.content or [])
                        if getattr(c, "text", None))
    except Exception:
        return str(result)


def _json(result):
    try:
        return json.loads(_text(result))
    except (ValueError, TypeError):
        return {}


def _is_error(result):
    return bool(getattr(result, "isError", False))


class BrokerError(Exception):
    """A real broker failure. Callers must treat this as 'do not trade',
    never as 'assume flat'."""


class CryptoBroker:
    """One MCP session's worth of broker access.

    Used as an async context manager so the connection is always closed:

        async with CryptoBroker(cfg) as b:
            q = await b.quotes(["BTC-USD"])
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.account = cfg["account"]["rhs_account_number"]
        self._session = None
        self._stack = []

    async def __aenter__(self):
        oauth = build_robinhood_oauth()
        hc = httpx2.AsyncClient(auth=oauth, follow_redirects=True,
                               timeout=httpx2.Timeout(30.0, read=60.0))
        self._stack.append(hc)
        await hc.__aenter__()

        stream = streamable_http_client(MCP_URL, http_client=hc,
                                        terminate_on_close=False)
        self._stack.append(stream)
        rs, ws = await stream.__aenter__()

        session = ClientSession(rs, ws)
        self._stack.append(session)
        await session.__aenter__()
        await session.initialize()
        self._session = session
        return self

    async def __aexit__(self, *exc):
        for ctx in reversed(self._stack):
            try:
                await ctx.__aexit__(*exc)
            except Exception:
                pass
        self._stack.clear()
        self._session = None
        return False

    async def _call(self, name, args):
        if self._session is None:
            raise BrokerError("broker session not open")
        res = await self._session.call_tool(name, args)
        if _is_error(res):
            raise BrokerError(f"{name}: {_text(res)[:300]}")
        return _json(res)

    # ------------------------------------------------------------ reads

    async def tools(self):
        resp = await self._session.list_tools()
        return {t.name for t in resp.tools}

    async def quotes(self, pairs):
        """Real bid/ask/mark plus computed spread, keyed by hyphenated pair.

        Robinhood returns symbols UNHYPHENATED ('BTCUSD'); the rest of this
        system uses the canonical 'BTC-USD', so normalise once, here.
        """
        payload = await self._call("get_crypto_quotes", {
            "symbols": list(pairs),
            "rhs_account_number": self.account,
        })
        out = {}
        for q in payload.get("data", {}).get("results", []) or []:
            raw = (q.get("symbol") or "").upper()
            pair = next((p for p in pairs
                         if p.replace("-", "").upper() == raw), raw)
            try:
                bid = float(q.get("bid_price") or 0)
                ask = float(q.get("ask_price") or 0)
                mark = float(q.get("mark_price") or 0)
            except (TypeError, ValueError):
                continue
            if not mark and bid and ask:
                mark = (bid + ask) / 2
            if not (bid and ask and mark):
                continue
            out[pair] = {
                "bid": bid, "ask": ask, "mark": mark,
                "spread_pct": (ask - bid) / mark * 100,
                "open_price": float(q.get("open_price") or 0) or None,
                "updated_at": q.get("updated_at"),
            }
        return out

    async def positions(self):
        """Real crypto positions with true average cost from the broker's own
        cost basis -- never an assumed fill price."""
        payload = await self._call("get_crypto_positions", {
            "rhs_account_number": self.account,
        })
        data = payload.get("data", {})
        rows = data.get("results") or data.get("positions") or []
        out = {}
        for p in rows:
            cur = p.get("currency") or {}
            code = (cur.get("code") or p.get("currency_code")
                    or p.get("asset_code") or "").upper()
            if not code:
                continue
            qty = None
            for k in ("quantity_transferable", "quantity", "total_quantity"):
                if p.get(k) is not None:
                    try:
                        qty = float(p[k])
                        break
                    except (TypeError, ValueError):
                        continue
            if not qty:
                continue

            tq = tc = 0.0
            for cb in p.get("cost_bases", []) or []:
                for qk, ck in (("direct_quantity", "direct_cost_basis"),
                               ("intraday_quantity", "intraday_cost_basis")):
                    try:
                        tq += float(cb.get(qk) or 0)
                        tc += float(cb.get(ck) or 0)
                    except (TypeError, ValueError):
                        pass

            out[f"{code}-USD"] = {
                "pair": f"{code}-USD",
                "asset": code,
                "quantity": qty,
                "avg_cost": (tc / tq) if tq > 0 else None,
                "cost_basis_usd": round(tc, 2) if tq > 0 else None,
            }
        return out

    async def open_orders(self, pair=None, side=None):
        args = {"rhs_account_number": self.account, "state_group": "open"}
        if pair:
            args["symbol"] = pair
        if side:
            args["side"] = side
        payload = await self._call("get_crypto_orders", args)
        return payload.get("data", {}).get("results", []) or []

    async def recent_orders(self, pair=None, limit_note=None):
        args = {"rhs_account_number": self.account}
        if pair:
            args["symbol"] = pair
        payload = await self._call("get_crypto_orders", args)
        return payload.get("data", {}).get("results", []) or []

    async def buying_power(self):
        payload = await self._call("get_portfolio", {
            "account_number": self.cfg["account"]["rhs_account_number"],
        })
        bp = payload.get("data", {}).get("buying_power", {})
        try:
            return float(bp.get("buying_power"))
        except (TypeError, ValueError):
            return None

    # ----------------------------------------------------------- writes

    async def preview(self, pair, side, *, quantity=None, dollar_amount=None,
                      limit_price=None):
        """Simulate the order. Always called before placing -- it resolves the
        real estimated cost and surfaces validation errors while nothing is
        at stake."""
        args = {
            "rhs_account_number": self.account,
            "symbol": pair,
            "side": side,
            "type": "limit" if limit_price else "market",
        }
        if limit_price:
            args["limit_price"] = f"{limit_price:.8f}".rstrip("0").rstrip(".")
        if quantity is not None:
            args["quantity"] = f"{quantity:.8f}"
        if dollar_amount is not None:
            args["dollar_amount"] = f"{dollar_amount:.2f}"
        return await self._call("preview_crypto_order", args)

    async def place(self, pair, side, *, quantity=None, dollar_amount=None,
                    limit_price=None, ref_id=None):
        """Place a REAL order. Only ever called after preview succeeds and the
        risk engine approved. ref_id makes retries idempotent at the gateway."""
        args = {
            "rhs_account_number": self.account,
            "symbol": pair,
            "side": side,
            "type": "limit" if limit_price else "market",
            "ref_id": ref_id or str(uuid.uuid4()),
        }
        if limit_price:
            args["limit_price"] = f"{limit_price:.8f}".rstrip("0").rstrip(".")
        if quantity is not None:
            args["quantity"] = f"{quantity:.8f}"
        if dollar_amount is not None:
            args["dollar_amount"] = f"{dollar_amount:.2f}"
        return await self._call("place_crypto_order", args)

    async def cancel(self, order_id):
        return await self._call("cancel_crypto_order", {
            "rhs_account_number": self.account,
            "order_id": order_id,
        })

    async def snapshot(self, pairs):
        """One consistent read of everything the pipeline needs."""
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "quotes": await self.quotes(pairs),
            "positions": await self.positions(),
            "buying_power": await self.buying_power(),
            "open_orders": await self.open_orders(),
        }


if __name__ == "__main__":
    import asyncio
    import crypto_data

    async def main():
        cfg = crypto_data.load_config()
        pairs = list(cfg["universe"])
        async with CryptoBroker(cfg) as b:
            names = await b.tools()
            required = {"get_crypto_quotes", "get_crypto_positions",
                        "preview_crypto_order", "place_crypto_order"}
            print("crypto tools present:", sorted(required & names))
            print("trade capable      :", required.issubset(names))

            snap = await b.snapshot(pairs)
            print(f"\nbuying power: ${snap['buying_power']}")
            print(f"open orders : {len(snap['open_orders'])}")
            print(f"positions   : {snap['positions'] or 'flat'}")
            print()
            for pair, q in snap["quotes"].items():
                print(f"  {pair:<10} mark ${q['mark']:<14,.6f} "
                      f"spread {q['spread_pct']:.2f}%")

    asyncio.run(main())
