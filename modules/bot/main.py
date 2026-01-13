import logging

import discord

from modules.statwrangler.events.env_check import get_env_vars


def configure_logging() -> None:
    # Your application logs
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%I:%M:%S %p",
    )

    # Silence noisy discord / py-cord internals
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("discord.client").setLevel(logging.WARNING)


def main():
    configure_logging()

    config = get_env_vars()

    intents = discord.Intents.default()
    intents.message_content = True

    bot = discord.Bot(intents=intents)

    modules_to_load = [
    ("core.guilds", "modules.core.guilds.guilds_tracker"),
    ("pilotai", "modules.pilotai.commands"),
    ("statwrangler", "modules.statwrangler.commands"),
    ("streamsentinel", "modules.streamsentinel.commands"),
    ("rolecop", "modules.rolecop")
   

]

    loaded = []
    for name, path in modules_to_load:
        bot.load_extension(path)
        loaded.append(name)

    print(f"[BOOT] Loaded modules: {', '.join(loaded)}")

    @bot.event
    async def on_ready():
        print(f"[READY] Logged in as {bot.user} (id={bot.user.id})")

        cmds = list(bot.walk_application_commands())
        print(f"[READY] slash commands: {len(cmds)}")
        for c in cmds:
            print(f"  * /{c.name}")

    bot.run(config.discord_token)


if __name__ == "__main__":
    main()


