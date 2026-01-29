from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import discord
from discord.ext import commands

# guild_tracker.py -> guilds -> core -> modules -> PROJECT
PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_DEV_REGISTRY = PROJECT_ROOT / "modules" / "core" / "guilds" / "dev_guilds.json"
DEFAULT_PUBLIC_REGISTRY = PROJECT_ROOT / "modules" / "core" / "guilds" / "guilds_public.json"


@dataclass
class GuildInfo:
    id: int
    name: str
    joined_at_utc: str | None = None
    last_seen_utc: str | None = None


class GuildTracker(commands.Cog):
    """
    Tracks guilds the bot is in and stores them in a registry JSON file.

    Behavior:
      - If bot.guild_registry_path is set (a pathlib.Path), we use that file.
      - Otherwise, we fall back based on bot.flavor ("dev" vs "public").
      - If neither is present, we default to dev registry.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._task: asyncio.Task | None = None
        self.reconcile_every_seconds = 300  # 5 minutes

        # Pick registry file
        self.guild_log_path: Path = self._resolve_registry_path()

    def _resolve_registry_path(self) -> Path:
        # 1) Explicit override: set by build_bot()
        p = getattr(self.bot, "guild_registry_path", None)
        if isinstance(p, Path):
            return p

        # 2) Otherwise infer from flavor
        flavor = getattr(self.bot, "flavor", "dev")
        if flavor == "public":
            return DEFAULT_PUBLIC_REGISTRY
        return DEFAULT_DEV_REGISTRY

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat()

    def _load(self) -> dict:
        self.guild_log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.guild_log_path.exists():
            return {"servers": []}

        try:
            with self.guild_log_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict) or "servers" not in data:
                return {"servers": []}
            if not isinstance(data["servers"], list):
                return {"servers": []}
            return data

        except Exception:
            return {"servers": []}

    def _save(self, data: dict) -> None:
        self.guild_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.guild_log_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def _upsert_guilds(self, guilds: list[discord.Guild]) -> None:
        data = self._load()
        by_id = {
            str(s.get("id")): s
            for s in data["servers"]
            if isinstance(s, dict) and "id" in s
        }

        now = self._utc_now()
        for g in guilds:
            gid = str(g.id)
            existing = by_id.get(gid)

            if existing:
                existing["name"] = g.name
                existing["last_seen_utc"] = now
                # If it was previously marked left, clear it (optional)
                if "left_at_utc" in existing:
                    existing.pop("left_at_utc", None)
            else:
                by_id[gid] = {
                    "id": g.id,
                    "name": g.name,
                    "joined_at_utc": now,
                    "last_seen_utc": now,
                }

        # Mark guilds we no longer see as "left"
        current_ids = {str(g.id) for g in guilds}
        for gid, rec in by_id.items():
            if gid not in current_ids:
                rec["left_at_utc"] = rec.get("left_at_utc") or now

        data["servers"] = list(by_id.values())
        self._save(data)

    async def _reconcile_loop(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                self._upsert_guilds(list(self.bot.guilds))
            except Exception as e:
                print(f"[guildtracker] reconcile error: {e!r}")
            await asyncio.sleep(self.reconcile_every_seconds)

    def cog_load(self) -> None:
        if self._task is None:
            self._task = self.bot.loop.create_task(self._reconcile_loop())

    def cog_unload(self) -> None:
        if self._task:
            self._task.cancel()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self._upsert_guilds(list(self.bot.guilds))
        flavor = getattr(self.bot, "flavor", "?")
        print(f"[guildtracker:{flavor}] snapshot saved ({len(self.bot.guilds)} guilds) -> {self.guild_log_path}")


    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        self._upsert_guilds(list(self.bot.guilds))
        flavor = getattr(self.bot, "flavor", "?")
        print(f"[guildtracker:{flavor}] joined: {guild.name} ({guild.id})")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self._upsert_guilds(list(self.bot.guilds))
        flavor = getattr(self.bot, "flavor", "?")
        print(f"[guildtracker:{flavor}] removed: {guild.name} ({guild.id})")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(GuildTracker(bot))
