import datetime as dt
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from .streamer_list_loader import load_streamers
from .twitch_stream_status import build_stream_cards, duration_hm, resolve_to_logins


class StreamSentinel(commands.Cog):
    def __init__(self, bot: commands.Bot, config) -> None:
        self.bot = bot
        self.config = config

        # Per-streamer state: login -> dict(start_dt, message_id, ended)
        self.stream_state: dict[str, dict] = {}

        # Start the loop with a default; we’ll update interval in cog_load
        self.stream_watch_loop.change_interval(seconds=self.config.poll_seconds)

    async def stream_watch_once(self) -> None:
        channel = self.bot.get_channel(self.config.discord_channel_id)
        if channel is None or not isinstance(
            channel, (discord.TextChannel, discord.Thread)
        ):
            print(
                "[stream_watch] Invalid DISCORD_CHANNEL_ID or channel not found/accessible."
            )
            return

        tz = ZoneInfo(self.config.timezone)
        streamers = load_streamers()
        if not streamers:
            return

        # Resolve any display names -> logins, preserving order where possible
        id_to_login = resolve_to_logins(streamers)
        resolved_logins = [id_to_login[s] for s in streamers if s in id_to_login]
        if not resolved_logins:
            return

        # Build current live cards keyed by login (lowercased in your helper)
        live_cards = build_stream_cards(resolved_logins, tz)
        live_logins = set(live_cards.keys())

        # ---- Start events ----
        for login in resolved_logins:
            key = login.lower()
            card = live_cards.get(key)
            state = self.stream_state.get(key)

            if card and (
                not state or state.get("message_id") is None or state.get("ended")
            ):
                embed = discord.Embed(
                    title=f"{card['display_name']} is LIVE",
                    description=card["title"] or "Streaming now",
                    url=f"https://twitch.tv/{card['login']}",
                    timestamp=dt.datetime.now(tz=tz),
                )
                embed.add_field(
                    name="Twitch",
                    value=f"[{card['login']}](https://twitch.tv/{card['login']})",
                    inline=True,
                )
                embed.add_field(name="Category", value=card["game_name"], inline=True)
                embed.add_field(
                    name="Started", value=card["started_at_local_str"], inline=True
                )

                if card.get("box_art_url"):
                    embed.set_thumbnail(url=card["box_art_url"])

                msg = await channel.send(embed=embed)

                self.stream_state[key] = {
                    "start_dt": card["started_at_dt"],
                    "message_id": msg.id,
                    "ended": False,
                }
                print(f"[stream_watch] Announced live for {key} -> message {msg.id}")

        # ---- End events ----
        for key, state in list(self.stream_state.items()):
            if key in live_logins:
                continue

            if state.get("message_id") and not state.get("ended"):
                try:
                    msg = await channel.fetch_message(state["message_id"])  # type: ignore[arg-type]
                except discord.NotFound:
                    self.stream_state[key]["ended"] = True
                    continue
                except discord.HTTPException:
                    continue

                start_dt = state.get("start_dt") or dt.datetime.now(tz=tz)
                end_dt = dt.datetime.now(tz=tz)
                dur = duration_hm(start_dt, end_dt)

                embed = (
                    msg.embeds[0]
                    if msg.embeds
                    else discord.Embed(title="Stream Update")
                )

                # Remove any prior "Ended"/"Duration" fields to avoid duplicates
                filtered_fields = [
                    f for f in embed.fields if f.name not in {"Ended", "Duration"}
                ]
                embed.clear_fields()
                for f in filtered_fields:
                    embed.add_field(name=f.name, value=f.value, inline=f.inline)

                embed.add_field(
                    name="Ended", value=end_dt.strftime("%-I:%M %p %Z"), inline=True
                )
                embed.add_field(name="Duration", value=dur, inline=True)
                embed.set_footer(text="Stream ended")

                try:
                    await msg.edit(embed=embed)
                    self.stream_state[key]["ended"] = True
                    print(
                        f"[stream_watch] Marked ended for {key} -> message {msg.id} ({dur})"
                    )
                except discord.HTTPException:
                    pass

    # ---------- lifecycle ----------
    def cog_load(self) -> None:
        # Start loop once bot is ready; tasks.loop requires bot running
        if not self.stream_watch_loop.is_running():
            self.stream_watch_loop.start()

    def cog_unload(self) -> None:
        if self.stream_watch_loop.is_running():
            self.stream_watch_loop.cancel()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        # Avoid “NoneType user” issues by logging from the real running bot
        # print(f"[streamsentinel] Ready as {self.bot.user} (id={self.bot.user.id})")
        print(
            f"[streamsentinel] will be polling every {self.config.poll_seconds}s in channel {self.config.discord_channel_id}"
        )

    # ---------- loop ----------
    @tasks.loop(seconds=60)  # overridden in __init__ using change_interval
    async def stream_watch_loop(self) -> None:
        await self.stream_watch_once()

    # ---------- slash command ----------
    @commands.slash_command(
        name="refresh_streams",
        description="Force a refresh of Twitch stream statuses right now.",
    )
    async def refresh_streams(self, ctx: discord.ApplicationContext):
        try:
            await ctx.defer(ephemeral=True)
        except Exception:
            pass

        await self.stream_watch_once()

        try:
            await ctx.respond("Refresh complete.", ephemeral=True)
        except Exception:
            pass


def setup(bot: commands.Bot):
    """
    IMPORTANT:
    - env vars should be loaded ONCE in modules/bot/main.py
    - we import get_env_vars here only to build config at setup-time
    """
    from .env_check import (
        get_env_vars,  # local import avoids side effects at import time
    )

    config = get_env_vars()
    bot.add_cog(StreamSentinel(bot, config))
