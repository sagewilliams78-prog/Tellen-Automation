#!/usr/bin/env python3
"""
Refresh the standalone bot's Robinhood access token using the refresh_token
already on disk -- no browser, no login, no new authorization. This is the
standard OAuth refresh grant (grant_type=refresh_token), documented at
Robinhood's own OAuth discovery endpoint.

Run this YOURSELF, in your own terminal:
    python3 refresh_robinhood_token.py

It never prints the actual token values -- only whether it worked. Your old
token stays in place until a real, valid replacement is confirmed; nothing
is overwritten on failure.
"""
import json
import urllib.request
import urllib.parse
import urllib.error

AUTH_FILE = "/Users/sagewilliams/.sage_robinhood_auth.json"
TOKEN_ENDPOINT = "https://api.robinhood.com/oauth2/token/"


def main():
    with open(AUTH_FILE) as f:
        d = json.load(f)

    client_id = d["client_info"]["client_id"]
    refresh_token = d["tokens"]["refresh_token"]

    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    })
    req = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=body.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            new_tokens = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Failed: HTTP {e.code}")
        print(e.read().decode()[:500])
        print("\nNothing changed -- your old token is still in place.")
        return
    except Exception as e:
        print(f"Failed: {type(e).__name__}: {e}")
        print("\nNothing changed -- your old token is still in place.")
        return

    if not new_tokens.get("access_token"):
        print("Failed: response had no access_token.")
        print("Nothing changed -- your old token is still in place.")
        return

    out = {"client_info": d["client_info"], "tokens": new_tokens}
    with open(AUTH_FILE, "w") as f:
        json.dump(out, f, indent=2)
    import os
    os.chmod(AUTH_FILE, 0o600)
    print(f"Success. Fresh token written to {AUTH_FILE} (chmod 600).")
    print(f"expires_in: {new_tokens.get('expires_in')} seconds")
    print("Tell Claude it's done and it'll verify and restart the bot.")


if __name__ == "__main__":
    main()
