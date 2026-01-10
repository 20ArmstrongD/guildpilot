import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass
class EnvConfig:
    discord_token: str
    discord_channel_id: int
    twitch_client_id: str
    twitch_client_secret: str
    timezone: str = "America/Chicago"
    poll_seconds: int = 60

def get_env_vars() -> EnvConfig | None:
    load_dotenv()

    discord_token = os.getenv("DISCORD_TOKEN")
    channel_id = os.getenv("DISCORD_CHANNEL_ID")
    twitch_client_id = os.getenv("TWITCH_CLIENT_ID")
    twitch_client_secret = os.getenv("TWITCH_CLIENT_SECRET")
    timezone = os.getenv("TIMEZONE", "America/Chicago")
    poll_seconds = int(os.getenv("POLL_SECONDS", "60"))

    missing = []
    if not discord_token: missing.append("DISCORD_TOKEN")
    if not channel_id: missing.append("DISCORD_CHANNEL_ID")
    if not twitch_client_id: missing.append("TWITCH_CLIENT_ID")
    if not twitch_client_secret: missing.append("TWITCH_CLIENT_SECRET")

    if missing:
        print(f"[env_check] Missing required env vars: {', '.join(missing)}")
        return None

    try:
        channel_id_int = int(channel_id)
    except ValueError:
        print("[env_check] DISCORD_CHANNEL_ID must be an integer.")
        return None

    return EnvConfig(
        discord_token=discord_token,
        discord_channel_id=channel_id_int,
        twitch_client_id=twitch_client_id,
        twitch_client_secret=twitch_client_secret,
        timezone=timezone,
        poll_seconds=poll_seconds,
    )