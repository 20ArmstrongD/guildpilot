import inspect
import logging

import discord
import validators
from discord.ext import commands

from .events import (
    generate_link,
    generate_val_link,
    get_r6siege_player_data,
    load_usernames,
    save_usernames,
)

logger = logging.getLogger("statwrangler")


def validate_url(url: str | None):
    return url if (url and validators.url(url)) else None


class StatWrangler(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ---------------- Bot lifecycle (moved into Cog) ----------------
    # @commands.Cog.listener()
    # async def on_ready(self):
    #     # If your on_ready_bot() prints info / does setup, keep it
    #     try:
    #         await on_ready_bot()
    #     except Exception as e:
    #         logger.exception("on_ready_bot failed: %r", e)

    @commands.Cog.listener()
    async def on_disconnect(self):
        logger.warning("Bot disconnected! Attempting to reconnect...")

    @commands.Cog.listener()
    async def on_resumed(self):
        logger.info("Bot session resumed successfully.")

    # ---------------- Autocomplete (py-cord) ----------------
    async def username_autocomplete(self, ctx: discord.AutocompleteContext):
        """
        py-cord autocomplete:
        - ctx.value is the current typed text
        - ctx.options contains already-selected options (like game)
        """
        current = (ctx.value or "").strip()
        game_value = ctx.options.get("game")  # "siege" / "fortnite" / "valorant"

        if not game_value:
            return []

        usernames = load_usernames()
        game_usernames = usernames.get(game_value, [])

        if not current:
            return game_usernames[:25]

        matches = [name for name in game_usernames if current.lower() in name.lower()]
        return matches[:25]

    # ---------------- Slash command (py-cord) ----------------
    @commands.slash_command(name="game_stats", description="Fetch game stats for a player")
    @discord.option(
        "game", description="Choose a game", choices=["siege", "fortnite", "valorant"]
    )
    @discord.option(
        "username",
        description="Enter the player's name",
        autocomplete=username_autocomplete,
    )
    @discord.option(
        "platform",
        description="Platform (PC, Xbox, PlayStation) — only required for Siege",
        required=False,
        default=None,
    )
    async def pull_stats(self, ctx: discord.ApplicationContext, game: str, username: str, platform: str = None):
        # Prevent Discord interaction timeout
        try:
            await ctx.defer()
        except Exception:
            pass

        game = game.lower().strip()
        username = username.strip()

        # Save username for that game if new
        usernames = load_usernames()
        game_usernames = usernames.get(game, [])

        if username and username not in game_usernames:
            game_usernames.append(username)
            usernames[game] = game_usernames
            save_usernames(usernames)
            logger.info("New username '%s' added to %s list.", username, game)
        else:
            logger.info("%s found in %s list", username, game)

        # Platform normalization (Siege needs it)
        if platform:
            platform = platform.lower().strip()
            platform_map = {"pc": "ubi", "xbox": "xbl", "playstation": "psn"}
            platform = platform_map.get(platform)

            if not platform:
                logger.error("Invalid platform provided")
                await ctx.respond("Invalid platform. Use PC, Xbox, or PlayStation.")
                return

        game_scrapers = {
            "siege": {"func": get_r6siege_player_data, "requires_platform": True},
            "fortnite": {"func": generate_link, "requires_platform": False},
            "valorant": {"func": generate_val_link, "requires_platform": False},
        }

        if game not in game_scrapers:
            await ctx.respond("Game not supported. Choose siege, fortnite, or valorant.")
            return

        scraper_func = game_scrapers[game]["func"]
        requires_platform = game_scrapers[game]["requires_platform"]

        if requires_platform and not platform:
            await ctx.respond("Siege requires a platform: PC, Xbox, or PlayStation.")
            return

        num_args = len(inspect.signature(scraper_func).parameters)

        # ---- Siege path (expects username, platform) ----
        if num_args == 2:
            logger.info("Fetching %s stats for %s on %s...", game, username, platform)

            kd, level, rank, ranked_kd, user_profile_img, rank_img = await get_r6siege_player_data(
                username, platform
            )

            kd = kd or "N/A"
            level = level or "N/A"
            rank = rank or "N/A"
            ranked_kd = ranked_kd or "N/A"
            user_profile_img = validate_url(user_profile_img)
            rank_img = validate_url(rank_img)

            embed = discord.Embed(
                title=f"Stats for {username} on {game.capitalize()}",
                color=discord.Color.yellow(),
            )
            embed.add_field(
                name="Overall Stats",
                value=f"* Level: {level}\n* KD Ratio: {kd}\n",
                inline=False,
            )

            if rank_img:
                embed.add_field(
                    name="Ranked Stats",
                    value=f"* Rank: {rank}\n* Ranked KD: {ranked_kd}",
                    inline=False,
                )
                embed.set_image(url=rank_img)

            if user_profile_img:
                embed.set_thumbnail(url=user_profile_img)

            logger.info(
                "Stats retrieved. Replying to %s in %s (Server: %s).",
                ctx.author,
                ctx.channel,
                ctx.guild.name if ctx.guild else "DM",
            )
            await ctx.respond(embed=embed)
            return

        # ---- Fortnite/Valorant link path (expects username) ----
        if num_args == 1:
            if game == "fortnite":
                url = await generate_link(username)
                if not url:
                    await ctx.respond("Failed to generate the Fortnite link.")
                    return

                embed = discord.Embed(
                    title=f"Fortnite Stats for {username}",
                    color=discord.Color.purple(),
                )
                embed.add_field(name="Link", value=url, inline=False)
                await ctx.respond(embed=embed)
                return

            if game == "valorant":
                url = await generate_val_link(username)
                if not url:
                    await ctx.respond("Failed to generate the Valorant link.")
                    return

                embed = discord.Embed(
                    title=f"Valorant Stats for {username}",
                    color=discord.Color.red(),
                )
                embed.add_field(name="Link", value=url, inline=False)
                await ctx.respond(embed=embed)
                return

        await ctx.respond(f"Could not fetch stats for {username} in {game.capitalize()}.")


def setup(bot: commands.Bot):
    # Make sure logging is configured once in your main entrypoint (recommended),
    # but leaving this safe here if you rely on it.
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%I:%M:%S %p",
        )

    bot.add_cog(StatWrangler(bot))
    # logger.info("StatWrangler Cog has been loaded.")