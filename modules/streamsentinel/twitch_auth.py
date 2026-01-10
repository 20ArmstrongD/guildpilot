import os
import time
import requests
from dotenv import load_dotenv

_TOKEN_CACHE = {"token": None, "exp": 0}

def _now() -> float:
    return time.time()

def get_twitch_oauth_token() -> str | None:
    """
    Returns an app access token for Twitch, caching it until ~5 minutes before expiry.
    Requires TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET in env or .env.
    """
    load_dotenv()
    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("[twitch_auth] Missing TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET")
        return None

    # If cached token valid, reuse
    if _TOKEN_CACHE["token"] and _now() < _TOKEN_CACHE["exp"] - 300:
        return _TOKEN_CACHE["token"]

    url = "https://id.twitch.tv/oauth2/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials"
    }
    try:
        resp = requests.post(url, data=data, timeout=20)
        resp.raise_for_status()
        j = resp.json()
        token = j.get("access_token")
        expires_in = j.get("expires_in", 0)
        if token:
            _TOKEN_CACHE["token"] = token
            _TOKEN_CACHE["exp"] = _now() + int(expires_in or 0)
            return token
    except requests.RequestException as e:
        print(f"[twitch_auth] Failed to obtain token: {e}")

    return None

def twitch_headers() -> dict | None:
    """Return Helix headers with Client-ID and Bearer token, or None if unavailable."""
    from dotenv import load_dotenv
    load_dotenv()
    client_id = os.getenv("TWITCH_CLIENT_ID")
    token = get_twitch_oauth_token()
    if not client_id or not token:
        return None
    return {
        "Client-ID": client_id,
        "Authorization": f"Bearer {token}",
    }