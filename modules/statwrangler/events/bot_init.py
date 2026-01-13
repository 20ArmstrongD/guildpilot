# import requests
import json

# from discord.ext import commands
import os

import discord

from .intents import botstuff, intent

# Set up bot with command prefix and intents (using discord.Bot)
intents = intent
intents.messages = True
intents.guilds = True

# Initialize the bot using discord.Bot (for slash commands)
bot = botstuff

GUILD_LOG_PATH = "/home/bot-vm/code/guildpilot/modules/statwrangler/json/guilds.json"


@bot.event
async def on_guild_join(guild):
    print(f"🔔 on_guild_join triggered for: {guild.name} ({guild.id})")

    # Ensure file exists and is valid
    if not os.path.exists(GUILD_LOG_PATH) or os.path.getsize(GUILD_LOG_PATH) == 0:
        with open(GUILD_LOG_PATH, "w") as f:
            json.dump({"servers": []}, f)

    # Load existing data
    with open(GUILD_LOG_PATH) as f:
        data = json.load(f)

    # Append new guild info if not already tracked
    if not any(str(g["id"]) == str(guild.id) for g in data["servers"]):
        data["servers"].append({"id": str(guild.id), "name": guild.name})

        with open(GUILD_LOG_PATH, "w") as f:
            json.dump(data, f, indent=4)

    print(f"✅ Joined new server: {guild.name} ({guild.id})")


@bot.event
async def on_ready_bot():
    # ---- Basic startup logging ----
    try:
        print(f"✅ Logged in as {bot.user}")
        for guild in bot.guilds:
            print(f"Connected to: {guild.name} (ID: {guild.id})")
    except Exception as e:
        print(f"❌ Failed to list connected guilds: {e!r}")

    # ---- Ensure all current guilds are tracked in the JSON file ----
    try:
        # Ensure file exists and has valid JSON
        if not os.path.exists(GUILD_LOG_PATH) or os.path.getsize(GUILD_LOG_PATH) == 0:
            with open(GUILD_LOG_PATH, "w") as f:
                json.dump({"servers": []}, f, indent=4)

        with open(GUILD_LOG_PATH, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {"servers": []}

        if "servers" not in data or not isinstance(data["servers"], list):
            data = {"servers": []}

        existing_ids = {str(s.get("id")) for s in data["servers"] if "id" in s}
        updated = False

        for guild in bot.guilds:
            if str(guild.id) not in existing_ids:
                data["servers"].append({"id": str(guild.id), "name": guild.name})
                updated = True
                print(
                    f"📌 Added missing server from startup: {guild.name} ({guild.id})"
                )

        if updated:
            with open(GUILD_LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

        try:
            print("\n" + "=" * 60)
            print(f"[READY] Logged in as: {bot.user} (id={bot.user.id})")
            print(f"[READY] py-cord discord module: {discord.__file__}")
            print(
                f"[READY] discord version: {getattr(discord, '__version__', 'unknown')}"
            )
            print(f"[READY] Latency: {round(bot.latency * 1000)} ms")

            # Guilds the bot is currently connected to
            print(f"[READY] Connected guilds: {len(bot.guilds)}")
            for g in bot.guilds:
                print(
                    f"  - {g.name} (id={g.id}) | members≈{getattr(g, 'member_count', 'unknown')}"
                )

            # Application / slash commands loaded locally
            cmds = getattr(bot, "application_commands", [])
            print(f"[READY] Loaded application commands (local): {len(cmds)}")
            for c in cmds:
                guild_ids = getattr(c, "guild_ids", None)
                desc = getattr(c, "description", "")
                print(f"  - /{c.name} | guild_ids={guild_ids} | desc='{desc}'")
        except Exception as e:
            print(f"Error syncing commands: {e}")

    except Exception as e:
        print(f"❌ Failed to sync guilds.json with current guilds: {e!r}")

    # ---- Py-cord note: no bot.tree.sync ----
    # Py-cord registers slash commands automatically.
    # Optional: show how many app commands are loaded
    try:
        cmds = list(bot.walk_application_commands())
        print(f"✅ Loaded {len(cmds)} slash command(s) (py-cord).")
    except Exception:
        pass
