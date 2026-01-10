import asyncio
import datetime as dt
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from env_check import get_env_vars
from streamer_list_load import load_streamers
from twitch_stream_status import build_stream_cards, duration_hm, resolve_to_logins

cfg = get_env_vars()
if not cfg:
    raise SystemExit("Missing required environment variables. See logs above.")

intents = discord.Intents.default()
intents.message_content = False  # not needed for this bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Per-streamer state: login -> dict(start_dt, message_id, ended)
STREAM_STATE: dict[str, dict] = {}

async def stream_watch_once():
    channel = bot.get_channel(cfg.discord_channel_id)
    if channel is None or not isinstance(channel, (discord.TextChannel, discord.Thread)):
        print("[stream_watch] Invalid DISCORD_CHANNEL_ID or channel not found/accessible.")
        return

    tz = ZoneInfo(cfg.timezone)
    streamers = load_streamers()
    #print(f"[DEBUG] Loaded streamers: {streamers}")

    if not streamers:
        return

    # Resolve any display names -> logins, preserving order where possible
    id_to_login = resolve_to_logins(streamers)
    #print(f"[DEBUG] id_to_login map: {id_to_login}")
    resolved_logins = [id_to_login[s] for s in streamers if s in id_to_login]
    if not resolved_logins:
        return

    # Build current live cards keyed by login
    live_cards = build_stream_cards(resolved_logins, tz)
    #print(f"[DEBUG] Live cards: {live_cards}")

    live_logins = set(live_cards.keys())
    # Keep state keyed by login
    known_logins = set(STREAM_STATE.keys())

    # Handle new lives (start events)
    for login in resolved_logins:
        key = login.lower()
        card = live_cards.get(key)
        state = STREAM_STATE.get(key)

        if card and (not state or state.get("message_id") is None or state.get("ended")):
            # Post new embed
            embed = discord.Embed(
                title=f"{card['display_name']} is LIVE",
                description=card['title'] or "Streaming now",
                url=f"https://twitch.tv/{card['login']}",
                timestamp=dt.datetime.now(tz=tz),
            )
            embed.add_field(name="Twitch", value=f"[{card['login']}](https://twitch.tv/{card['login']})", inline=True)
            embed.add_field(name="Category", value=card['game_name'], inline=True)
            embed.add_field(name="Started", value=card['started_at_local_str'], inline=True)
            if card.get("box_art_url"):
                embed.set_thumbnail(url=card["box_art_url"])

            msg = await channel.send(embed=embed)

            STREAM_STATE[key] = {
                "start_dt": card["started_at_dt"],
                "message_id": msg.id,
                "ended": False,
            }
            print(f"[stream_watch] Announced live for {key} -> message {msg.id}")

    # Handle ended streams (end events): known live state but no longer in live_cards
    for key, state in list(STREAM_STATE.items()):
        # If we still see them live, skip
        if key in live_logins:
            continue

        # If we have a message_id and not already ended, mark ended and update embed
        if state.get("message_id") and not state.get("ended"):
            channel = bot.get_channel(cfg.discord_channel_id)
            if channel is None or not isinstance(channel, (discord.TextChannel, discord.Thread)):
                continue

            try:
                msg = await channel.fetch_message(state["message_id"])  # type: ignore
            except discord.NotFound:
                STREAM_STATE[key]["ended"] = True
                continue
            except discord.HTTPException:
                continue

            # Build updated embed
            tz = ZoneInfo(cfg.timezone)
            start_dt = state.get("start_dt") or dt.datetime.now(tz=tz)
            end_dt = dt.datetime.now(tz=tz)
            dur = duration_hm(start_dt, end_dt)

            embed = msg.embeds[0] if msg.embeds else discord.Embed(title="Stream Update")
            # Remove any prior "Ended"/"Duration" fields to avoid duplicates
            filtered_fields = [f for f in embed.fields if f.name not in {"Ended", "Duration"}]
            embed.clear_fields()
            for f in filtered_fields:
                embed.add_field(name=f.name, value=f.value, inline=f.inline)
            embed.add_field(name="Ended", value=end_dt.strftime("%-I:%M %p %Z"), inline=True)
            embed.add_field(name="Duration", value=dur, inline=True)
            embed.set_footer(text="Stream ended")

            try:
                await msg.edit(embed=embed)
                STREAM_STATE[key]["ended"] = True
                print(f"[stream_watch] Marked ended for {key} -> message {msg.id} ({dur})")
            except discord.HTTPException:
                pass

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    if not stream_watch_loop.is_running():
        stream_watch_loop.start()

    # If the library supports app commands (discord.py), sync here
    if hasattr(bot, "tree"):
        try:
            await bot.tree.sync()
            print("[appcmd] Slash commands synced globally (discord.py style).")
        except Exception as e:
            print(f"[appcmd] Global sync failed: {e!r}")

@tasks.loop(seconds=cfg.poll_seconds)
async def stream_watch_loop():
    await stream_watch_once()

# -------- Slash command: refresh (supports both discord.py and py-cord) --------
if hasattr(bot, "tree"):
    # discord.py (app_commands) path
    @bot.tree.command(name="refresh_streams", description="Force a refresh of Twitch stream statuses right now.")
    async def refresh_streams(interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        await stream_watch_once()
        try:
            await interaction.followup.send("Refresh complete.", ephemeral=True)
        except Exception:
            pass
else:
    # py-cord slash command path
    @bot.slash_command(name="refresh_streams", description="Force a refresh of Twitch stream statuses right now.")
    async def refresh_streams(ctx):
        try:
            await ctx.defer(ephemeral=True)
        except Exception:
            pass
        await stream_watch_once()
        try:
            await ctx.followup.send("Refresh complete.", ephemeral=True)
        except Exception:
            # Fallback if followup is unavailable
            try:
                await ctx.respond("Refresh complete.", ephemeral=True)
            except Exception:
                pass

if __name__ == "__main__":
    bot.run(cfg.discord_token)