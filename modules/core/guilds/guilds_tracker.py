import asyncio
import json
import os
from datetime import UTC, datetime
from dataclasses import dataclass
import discord
from discord.ext import commands
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # guild_tracker.py -> guilds -> core -> modules -> PROJECT
GUILD_LOG_PATH = PROJECT_ROOT / "modules" / "core" / "guilds" / "guilds.json"



@dataclass
class GuildInfo:
    id: int
    name: str
    joined_at_utc: str | None = None
    last_seen_utc: str | None = None


class GuildTracker(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._task: asyncio.Task | None = None
        self.reconcile_every_seconds = 300  # 5 minutes

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat()

    def _load(self) -> dict:
        GUILD_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not GUILD_LOG_PATH.exists():
            return {"servers": []}
        try:
            with GUILD_LOG_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "servers" not in data:
                return {"servers": []}
            if not isinstance(data["servers"], list):
                return {"servers": []}
            return data
        except Exception:
            return {"servers": []}

    def _save(self, data: dict) -> None:
        with open(GUILD_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def _upsert_guilds(self, guilds: list[discord.Guild]) -> None:
        data = self._load()
        by_id = {str(s.get("id")): s for s in data["servers"] if isinstance(s, dict) and "id" in s}

        now = self._utc_now()
        for g in guilds:
            gid = str(g.id)
            existing = by_id.get(gid)

            if existing:
                existing["name"] = g.name
                existing["last_seen_utc"] = now
            else:
                by_id[gid] = {
                    "id": g.id,
                    "name": g.name,
                    "joined_at_utc": now,
                    "last_seen_utc": now,
                }

        # Optional: mark guilds we no longer see as "left"
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
        # Start background reconciliation task
        if self._task is None:
            self._task = self.bot.loop.create_task(self._reconcile_loop())

    def cog_unload(self) -> None:
        if self._task:
            self._task.cancel()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        # Snapshot on startup
        self._upsert_guilds(list(self.bot.guilds))
        print(f"[guildtracker] snapshot saved ({len(self.bot.guilds)} guilds)")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        self._upsert_guilds(list(self.bot.guilds))
        print(f"[guildtracker] joined: {guild.name} ({guild.id})")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self._upsert_guilds(list(self.bot.guilds))
        print(f"[guildtracker] removed: {guild.name} ({guild.id})")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(GuildTracker(bot))
