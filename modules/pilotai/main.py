import discord
from discord.ext import commands

from modules.pilotai.env_check import get_env_vars  # adjust import if needed


def main() -> None:
    config = get_env_vars()

    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    # Load extensions (each one registers its own slash commands)
    # bot.load_extension("modules.pilotai.commands")
    # bot.load_extension("modules.statwrangler.commands")
    # bot.load_extension("modules.streamsentinel.commands")

    @bot.event
    async def on_ready():
        print("\n" + "=" * 60)
        print(f"[READY] Logged in as: {bot.user} (id={bot.user.id})")
        print(f"[READY] discord version: {getattr(discord, '__version__', 'unknown')}")
        print(f"[READY] Connected guilds: {len(bot.guilds)}")
        for g in bot.guilds:
            print(f"  - {g.name} (id={g.id})")

        local_cmds = list(bot.walk_application_commands())
        print(f"[READY] Local app commands found: {len(local_cmds)}")
        for c in local_cmds:
            print(f"  - /{c.name} | guild_ids={getattr(c, 'guild_ids', None)}")

        # NOTE: Global slash commands may take time to appear in Discord UI.
        # The correct scope (applications.commands) is required on the invite.

    bot.run(config.discord_token)


if __name__ == "__main__":
    main()
