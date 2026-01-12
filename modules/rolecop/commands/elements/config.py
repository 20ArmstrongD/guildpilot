from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# ---- Constants that are safe to import anytime ----
GANG_ROLE_NAME = "Gang Members"
STALLIONS_ROLE_NAME = "The Stallions"
BOTS_ROLE_NAME = "Bots"
EMOJI_APPROVE = "✅"
EMOJI_DENY = "❌"


@dataclass(frozen=True)
class RolecopConfig:
    token: str
    guild_id: int
    welcome_channel_id: int
    welcome_member_messages_path: Optional[str] = None
    welcome_bot_messages_path: Optional[str] = None


def load_env() -> None:
    """
    Load env vars from a local .env if present, otherwise rely on existing env.
    - No hard-coded absolute paths (CI + different machines will work).
    """
    load_dotenv()  # looks for .env in the current working directory or parents


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is not set. Add it to your .env or environment.")
    return value


def get_config() -> RolecopConfig:
    """
    Loads + validates required env vars at runtime.
    Call this from main() before starting the bot.
    """
    load_env()

    token = _require_env("DISCORD_BOT_TOKEN")
    guild_id = int(_require_env("GUILD_ID"))
    welcome_channel_id = int(_require_env("WELCOME_CHANNEL"))

    cfg = RolecopConfig(
        token=token,
        guild_id=guild_id,
        welcome_channel_id=welcome_channel_id,
        welcome_member_messages_path=os.getenv("WELCOME_MEMBER_MESSAGES"),
        welcome_bot_messages_path=os.getenv("WELCOME_BOT_MESSAGES"),
    )

    # Optional sanity logs (safe at runtime)
    logging.info(f"GUILD_ID={cfg.guild_id}, WELCOME_CHANNEL={cfg.welcome_channel_id}")
    logging.info(f"welc_msg_memb_path={cfg.welcome_member_messages_path}")
    logging.info(f"welc_msg_bot_path={cfg.welcome_bot_messages_path}")

    return cfg


def build_bot() -> commands.Bot:
    """
    Create the bot instance (safe to call in runtime code).
    """
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    return commands.Bot(command_prefix="!", intents=intents)
