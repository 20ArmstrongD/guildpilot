import discord
from discord.ext import commands
import os
import requests
import json
from .intents import intent, botstuff

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
    with open(GUILD_LOG_PATH, "r") as f:
        data = json.load(f)

    # Append new guild info if not already tracked
    if not any(str(g["id"]) == str(guild.id) for g in data["servers"]):
        data["servers"].append({
            "id": str(guild.id),
            "name": guild.name
        })

        with open(GUILD_LOG_PATH, "w") as f:
            json.dump(data, f, indent=4)

    print(f"✅ Joined new server: {guild.name} ({guild.id})")

@bot.event
async def on_Ready():
    try:
        print(f'✅ Logged in as {bot.user}')  
        
        for guild in bot.guilds:
            print(f'Connected to: {guild.name} (ID: {guild.id})')
    except Exception as e:
            print(f'❌ Failed to list connected guilds: {e}')

        # --- Ensure all current guilds are tracked in the JSON file ---
    try:
        # If file doesn't exist or is empty/corrupt, initialize it
        if not os.path.exists(GUILD_LOG_PATH) or os.path.getsize(GUILD_LOG_PATH) == 0:
            with open(GUILD_LOG_PATH, "w") as f:
                json.dump({"servers": []}, f)

        with open(GUILD_LOG_PATH, "r+") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {"servers": []}

            existing_ids = {s["id"] for s in data["servers"]}
            updated = False

            for guild in bot.guilds:
                if str(guild.id) not in existing_ids:
                    data["servers"].append({
                        "id": str(guild.id),
                        "name": guild.name
                    })
                    updated = True
                    print(f"📌 Added missing server from startup: {guild.name} ({guild.id})")

            if updated:
                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()
    except Exception as e:
            print(f"❌ Failed to sync guilds.json with current guilds: {e}")

        # --- Sync slash commands ---
    try:
        # Load the guild IDs from your JSON file
        with open(GUILD_LOG_PATH, "r") as file:
            data = json.load(file)
            servers = data.get("servers", [])

        if servers:
            for server in servers:
                guild_id = server.get("id")
                guild_name = server.get("name")
                if guild_id:
                    try:
                        guild = discord.Object(id=guild_id)
                        await bot.tree.sync(guild=guild)
                        print(f"✅ Synced commands for guild: {guild_name} (ID: {guild_id})")
                    except Exception as e:
                        print(f"⚠️ Failed to sync commands for guild {guild_name} (ID: {guild_id}): {e}")
                else:
                    print(f"⚠️ No ID found for server: {guild_name}")
        else:
            print("⚠️ No server data found in guild.json.")
            
    except Exception as e:
        print(f"⚠️ Error during on_ready sync: {e}")