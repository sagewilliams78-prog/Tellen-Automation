#!/usr/bin/env python3
"""
Re-authorize the standalone bot's Robinhood connection -- with a GENUINELY
NEW client registration this time, not the old one.

Every prior attempt (reauth_robinhood.py, 3 real tries) reused the SAME
client_id from the original ~/.sage_robinhood_auth.json, even though it
kept failing to reach a consent screen. This script skips that reuse
entirely and always registers a brand new client via Robinhood's own real
registration endpoint first, then runs the authorization flow against
THAT fresh registration. Different real experiment, not a repeat.

Run this YOURSELF, in your own terminal:
    python3 reauth_robinhood_v2.py

You log in on Robinhood's real site, with your own credentials and MFA.
This script never sees your password -- only the short-lived authorization
code Robinhood redirects back with, exchanged the same way any OAuth
client does. Your OLD token stays in place until a real, valid replacement
is confirmed.
"""
import base64
import hashlib
import json
import os
import secrets
import urllib.parse
import urllib.request
import urllib.error
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

AUTH_ENDPOINT = "https://robinhood.com/oauth"
TOKEN_ENDPOINT = "https://api.robinhood.com/oauth2/token/"
REGISTER_ENDPOINT = "https://agent.robinhood.com/oauth/trading/register"
REDIRECT_URI = "http://localhost:3031/callback"  # different port -- avoid any stale listener confusion
AUTH_FILE = os.path.expanduser("~/.sage_robinhood_auth.json")


def register_new_client():
    """Always register fresh -- never reuse the old, already-failing client_id."""
    req = urllib.request.Request(
        REGISTER_ENDPOINT,
        data=json.dumps({
            "redirect_uris": [REDIRECT_URI],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "client_name": "Robinhood Trading (v2)",
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


captured = {}


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        if "code" in params:
            captured["code"] = params["code"][0]
            body = b"<html><body>Authorized. You can close this tab and return to the terminal.</body></html>"
            self.send_response(200)
        else:
            captured["raw_query"] = qs
            body = b"<html><body>No authorization code received.</body></html>"
            self.send_response(400)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def main():
    print("Registering a brand NEW client with Robinhood (not reusing the old one)...")
    try:
        client_info = register_new_client()
    except urllib.error.HTTPError as e:
        print(f"Registration failed: HTTP {e.code}")
        print(e.read().decode()[:500])
        return
    client_id = client_info["client_id"]
    print(f"New client registered. (client_id not printed -- treat it as sensitive.)")

    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "scope": "internal",
    }
    auth_url = f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"

    print(f"\nOpening your browser to Robinhood's login page:\n  {auth_url}\n")
    print("Log in there with your own Robinhood credentials. Waiting for the redirect...")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 3031), CallbackHandler)
    server.timeout = 900
    server.handle_request()

    if "code" not in captured:
        print("No authorization code received (timed out, or landed elsewhere).")
        if "raw_query" in captured:
            print(f"Raw callback query received instead: {captured['raw_query']}")
        print("Nothing was changed.")
        return

    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": captured["code"],
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "code_verifier": verifier,
    })
    req = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=body.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            tokens = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Token exchange failed: HTTP {e.code}")
        print(e.read().decode()[:500])
        print("Nothing was changed -- your old (expired) token is still in place.")
        return

    out = {"client_info": client_info, "tokens": tokens}
    with open(AUTH_FILE, "w") as f:
        json.dump(out, f, indent=2)
    os.chmod(AUTH_FILE, 0o600)
    print(f"\nSuccess. Fresh token from a NEW client written to {AUTH_FILE} (chmod 600).")
    print("Tell Claude it's done and it'll verify and restart the bot.")


if __name__ == "__main__":
    main()
