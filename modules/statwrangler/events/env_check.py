import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv



# Explicitly load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env", override=False)

# print("\n\n",PROJECT_ROOT)

@dataclass(frozen=True)
class EnvConfig:
    discord_token: str

def get_env_vars() -> EnvConfig:
    def require(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"Missing required env var: {name}")
        return value

    return EnvConfig(
        discord_token=require("DISCORD_TOKEN")
    )
