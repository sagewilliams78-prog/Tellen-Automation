import json
import os
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pydantic import AnyUrl

from mcp.client.auth import (
    AuthorizationCodeResult,
    OAuthClientProvider,
    TokenStorage,
)

from mcp.shared.auth import (
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken,
)


MCP_URL = "https://agent.robinhood.com/mcp/trading"

TOKEN_FILE = Path.home() / ".sage_robinhood_oauth.json"

REDIRECT_URI = "http://127.0.0.1:8765/callback"


class FileTokenStorage(TokenStorage):

    def __init__(self):
        self.tokens = None
        self.client_info = None
        self._load()

    def _load(self):

        if not TOKEN_FILE.exists():
            return

        try:
            data = json.loads(TOKEN_FILE.read_text())

            if data.get("tokens"):
                self.tokens = OAuthToken.model_validate(
                    data["tokens"]
                )

            if data.get("client_info"):
                self.client_info = (
                    OAuthClientInformationFull.model_validate(
                        data["client_info"]
                    )
                )

            print("✓ Saved Robinhood OAuth credentials loaded")

        except Exception as e:
            print(
                f"⚠️ Could not load Robinhood OAuth credentials: {e}"
            )

    def _save(self):

        data = {
            "tokens": (
                self.tokens.model_dump(mode="json")
                if self.tokens
                else None
            ),

            "client_info": (
                self.client_info.model_dump(mode="json")
                if self.client_info
                else None
            ),
        }

        TOKEN_FILE.write_text(
            json.dumps(data, indent=2)
        )

        os.chmod(
            TOKEN_FILE,
            0o600
        )

    async def get_tokens(self):
        return self.tokens

    async def set_tokens(self, tokens):
        self.tokens = tokens
        self._save()
        print("✓ Robinhood OAuth tokens updated")

    async def get_client_info(self):
        return self.client_info

    async def set_client_info(self, client_info):
        self.client_info = client_info
        self._save()


async def open_browser(auth_url: str):

    print()
    print("🔐 Robinhood authorization required.")
    print()

    webbrowser.open(auth_url)

    print(
        "If Safari did not open automatically, "
        "open this URL manually:"
    )

    print()
    print(auth_url)
    print()


async def wait_for_callback():

    print()
    print(
        "After approving Robinhood, copy the COMPLETE "
        "callback URL from Safari."
    )

    print(
        "Do not share the callback URL or authorization code."
    )

    print()

    callback_url = input(
        "Paste callback URL here: "
    ).strip()

    params = parse_qs(
        urlparse(callback_url).query
    )

    if "error" in params:
        raise RuntimeError(
            f"Robinhood OAuth error: {params}"
        )

    if "code" not in params:
        raise RuntimeError(
            "No authorization code found in callback URL."
        )

    return AuthorizationCodeResult(
        code=params["code"][0],
        state=params.get("state", [None])[0],
        iss=params.get("iss", [None])[0],
    )


def build_robinhood_oauth():

    return OAuthClientProvider(

        server_url=MCP_URL,

        client_metadata=OAuthClientMetadata(

            client_name="Sage Bot v13",

            redirect_uris=[
                AnyUrl(REDIRECT_URI)
            ],

            grant_types=[
                "authorization_code",
                "refresh_token",
            ],

            response_types=[
                "code"
            ],

            scope="internal",
        ),

        storage=FileTokenStorage(),

        redirect_handler=open_browser,

        callback_handler=wait_for_callback,
    )
