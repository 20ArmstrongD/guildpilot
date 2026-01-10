import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Explicitly load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True)
class EnvConfig:
    discord_token: str
    discord_channel_id: int
    twitch_client_id: str
    twitch_client_secret: str
    timezone: str = "America/Chicago"
    poll_seconds: int = 60


def get_env_vars() -> EnvConfig:
    def require(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"Missing required env var: {name}")
        return value

    return EnvConfig(
        discord_token=require("DISCORD_TOKEN"),
        discord_channel_id=int(require("DISCORD_CHANNEL_ID")),
        twitch_client_id=require("TWITCH_CLIENT_ID"),
        twitch_client_secret=require("TWITCH_CLIENT_SECRET"),
        timezone=os.getenv("TIMEZONE", "America/Chicago"),
        poll_seconds=int(os.getenv("POLL_SECONDS", "60")),
    )


# if __name__ == "__main__":
#     config = get_env_vars()
#     print("Discord token loaded:", bool(config.discord_token), str(config.discord_channel_id))
