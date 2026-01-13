import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True)
class EnvConfig:
    discord_token: str
    openai_api_key: str
    openai_org: str | None = None


def get_env_vars() -> EnvConfig:
    def require(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"Missing required env var: {name}")
        return value

    return EnvConfig(
        discord_token=require("DISCORD_TOKEN"),
        openai_api_key=require("OPENAI_API_KEY"),
        openai_org=os.getenv("OPENAI_ORG"),
    )



# if __name__ == "__main__":
#     config = get_env_vars()
