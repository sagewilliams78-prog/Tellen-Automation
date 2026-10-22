#!/usr/bin/env python3

import asyncio
from datetime import datetime, timedelta, timezone

import httpx2

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from robinhood_oauth_v13 import build_robinhood_oauth
from sage_bot_v13 import (
    MCP_URL,
    WATCHLIST,
    get_buying_power,
    get_broker_positions,
)


async def main():

    print("=" * 70)
    print("EVA v13 - READ ONLY BROKER DIAGNOSTIC")
    print("=" * 70)
    print("NO ORDERS CAN BE PLACED BY THIS TEST")
    print()

    oauth = build_robinhood_oauth()

    async with httpx2.AsyncClient(
        auth=oauth,
        follow_redirects=True,
        timeout=httpx2.Timeout(
            30.0,
            read=300.0,
        ),
    ) as hc:

        async with streamable_http_client(
            MCP_URL,
            http_client=hc,
            terminate_on_close=False,
        ) as (rs, ws):

            async with ClientSession(rs, ws) as session:

                await session.initialize()

                print("✅ MCP CONNECTION")

                # 1. Account visibility
                accounts = await session.call_tool(
                    "get_accounts",
                    {},
                )

                if getattr(accounts, "isError", False):
                    print("❌ ACCOUNT ACCESS")
                    return

                print("✅ ACCOUNT ACCESS")

                # 2. Buying power
                bp = await get_buying_power(session)

                if bp is None:
                    print("❌ BUYING POWER READ")
                else:
                    print("✅ BUYING POWER READ")

                # 3. Broker positions
                positions = await get_broker_positions(session)

                if positions is None:
                    print("❌ POSITION READ")
                else:
                    print(
                        f"✅ POSITION READ ({len(positions)} position(s))"
                    )

                # 4. Robinhood historical candles
                end = datetime.now(timezone.utc)
                start = end - timedelta(days=7)

                symbol = WATCHLIST[0]

                historicals = await session.call_tool(
                    "get_equity_historicals",
                    {
                        "symbols": [symbol],
                        "start_time": start.strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        "end_time": end.strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        "interval": "day",
                        "bounds": "regular",
                    },
                )

                if getattr(historicals, "isError", False):
                    print("❌ HISTORICAL DATA")
                else:
                    print("✅ HISTORICAL DATA")

                print()
                print("=" * 70)

                if (
                    bp is not None
                    and positions is not None
                    and not getattr(
                        accounts,
                        "isError",
                        False,
                    )
                    and not getattr(
                        historicals,
                        "isError",
                        False,
                    )
                ):
                    print("✅ EVA v13 BROKER DIAGNOSTIC PASSED")
                else:
                    print("⚠️ EVA v13 DIAGNOSTIC NEEDS ATTENTION")

                print("=" * 70)
                print()
                print("NO ORDERS WERE SUBMITTED.")


if __name__ == "__main__":
    asyncio.run(main())
