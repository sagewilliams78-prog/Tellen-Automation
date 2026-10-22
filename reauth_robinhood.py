#!/usr/bin/env python3
"""
Re-authorize the standalone bot's Robinhood connection.

Run this YOURSELF (python3 reauth_robinhood.py) -- it opens Robinhood's own
login page in your browser. You log in there, on Robinhood's real site,
with your own credentials and MFA. This script never sees your password;
it only ever sees the short-lived authorization code Robinhood redirects
back with, and exchanges that for a token the same way any OAuth client
does.

Endpoints below come straight from Robinhood's own public OAuth discovery
document (https://agent.robinhood.com/.well-known/oauth-authorization-server),
not guessed. client_id is the same one already in your existing
~/.sage_robinhood_auth.json (a public client -- no secret involved, this is
normal for this kind of OAuth setup, not a shortcut).

On success, writes a fresh token to ~/.sage_robinhood_auth.json in exactly
the shape sage_bot_v13.py's load_jwt() expects. Your OLD token stays where
it is until this succeeds -- nothing is overwritten until a real, valid
replacement is in hand.
"""
import base64
import hashlib
import json
import os
import secrets
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

AUTH_ENDPOINT = "https://robinhood.com/oauth"
TOKEN_ENDPOINT = "https://api.robinhood.com/oauth2/token/"
REDIRECT_URI = "http://localhost:3030/callback"
AUTH_FILE = os.path.expanduser("~/.sage_robinhood_auth.json")

# Reuse the existing registered client -- avoids registering a brand new
# one for no reason. Falls back to registering fresh only if the file is
# missing or unreadable.
def existing_client_id():
    try:
        with open(AUTH_FILE) as f:
            return json.load(f).get("client_info", {}).get("client_id")
    except Exception:
        return None

def register_client():
    req = urllib.request.Request(
        "https://agent.robinhood.com/oauth/trading/register",
        data=json.dumps({
            "redirect_uris": [REDIRECT_URI],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "client_name": "Robinhood Trading",
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
            body = b"<html><body>No authorization code received.</body></html>"
            self.send_response(400)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet

def main():
    client_id = existing_client_id()
    client_info = None
    if not client_id:
        print("No existing client_id found -- registering a new client with Robinhood...")
        client_info = register_client()
        client_id = client_info["client_id"]

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

    print(f"Opening your browser to Robinhood's login page:\n  {auth_url}\n")
    print("Log in there with your own Robinhood credentials. Waiting for the redirect...")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 3030), CallbackHandler)
    server.timeout = 900  # 15 minutes to complete login -- generous given a slow system
    server.handle_request()

    if "code" not in captured:
        print("❌ No authorization code received (timed out or was cancelled). Nothing was changed.")
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
        print(f"❌ Token exchange failed: {e.code} {e.read().decode()[:300]}")
        print("Nothing was changed -- your old (expired) token is still in place.")
        return

    out = {
        "client_info": client_info or json.load(open(AUTH_FILE)).get("client_info", {"client_id": client_id}),
        "tokens": tokens,
    }
    with open(AUTH_FILE, "w") as f:
        json.dump(out, f, indent=2)
    os.chmod(AUTH_FILE, 0o600)
    print(f"✅ Success. Fresh token written to {AUTH_FILE} (chmod 600).")
    print("Tell Claude it's done and it'll restart the bot and confirm.")

if __name__ == "__main__":
    main()
