import json
import os

import discord
from discord.ext import commands

GUILD_LOG_PATH = "/home/bot-vm/code/guildpilot/modules/statwrangler/json/guilds.json"


class StatWranglerBotInit(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _ensure_file(self) -> dict:
        os.makedirs(os.path.dirname(GUILD_LOG_PATH), exist_ok=True)

        if not os.path.exists(GUILD_LOG_PATH) or os.path.getsize(GUILD_LOG_PATH) == 0:
            data = {"servers": []}
            with open(GUILD_LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return data

        with open(GUILD_LOG_PATH, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {"servers": []}

        if "servers" not in data or not isinstance(data["servers"], list):
            data = {"servers": []}

        return data

    def _write(self, data: dict) -> None:
        with open(GUILD_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        print(f"🔔 on_guild_join triggered for: {guild.name} ({guild.id})")

        data = self._ensure_file()

        if not any(str(g.get("id")) == str(guild.id) for g in data["servers"]):
            data["servers"].append({"id": str(guild.id), "name": guild.name})
            self._write(data)

        print(f"✅ Joined new server: {guild.name} ({guild.id})")

    @commands.Cog.listener()
    async def on_ready(self):
        # Make sure guilds.json is in sync with current guilds
        data = self._ensure_file()

        existing_ids = {str(s.get("id")) for s in data["servers"] if "id" in s}
        updated = False

        for guild in self.bot.guilds:
            if str(guild.id) not in existing_ids:
                data["servers"].append({"id": str(guild.id), "name": guild.name})
                updated = True
                print(
                    f"📌 Added missing server from startup: {guild.name} ({guild.id})"
                )

        if updated:
            self._write(data)

        # Helpful logging
        print("\n" + "=" * 60)
        print(f"[STATWRANGLER] Logged in as: {self.bot.user} (id={self.bot.user.id})")
        print(f"[STATWRANGLER] Connected guilds: {len(self.bot.guilds)}")
        for g in self.bot.guilds:
            print(f"  - {g.name} (id={g.id})")

        try:
            cmds = list(self.bot.walk_application_commands())
            print(f"[STATWRANGLER] Loaded {len(cmds)} slash command(s).")
        except Exception:
            pass


def setup(bot: commands.Bot):
    bot.add_cog(StatWranglerBotInit(bot))
