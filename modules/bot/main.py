import asyncio
import logging

import discord

from modules.core.env_check.env_check import get_env_vars, get_dev_env_vars


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%I:%M:%S %p",
    )
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("discord.client").setLevel(logging.WARNING)


MODULES_PUBLIC = [
    ("core.guilds", "modules.core.guilds.guilds_tracker"),
    ("pilotai", "modules.pilotai.commands"),
    ("statwrangler", "modules.statwrangler.commands"),
    ("rolecop", "modules.rolecop"),
]

MODULES_DEV_ONLY = [
    ("streamsentinel", "modules.streamsentinel.commands"),
]


def build_bot(*, flavor: str) -> discord.Bot:
    intents = discord.Intents.default()
    intents.message_content = True

    bot = discord.Bot(intents=intents)

    print(f"[BOOT:{flavor}] loading modules")

    loaded = []
    for name, path in MODULES_PUBLIC:
        bot.load_extension(path)
        loaded.append(name)
    print(f"[BOOT:{flavor}] Loaded modules: {', '.join(loaded)}")

    if flavor == "dev":
        dev_loaded = []
        for name, path in MODULES_DEV_ONLY:
            bot.load_extension(path)
            dev_loaded.append(name)
        print(f"[BOOT:{flavor}] Loaded dev modules: {', '.join(dev_loaded)}")

    @bot.event
    async def on_ready():
        print(f"[READY:{flavor}] Logged in as {bot.user} (id={bot.user.id})")

        cmds = list(bot.walk_application_commands())
        print(f"[READY:{flavor}] local slash commands loaded: {len(cmds)}")
        for c in cmds:
            print(f"  * /{c.name}")

        # Optional: show what Discord actually has registered per guild

    return bot


async def run_two_bots() -> None:
    configure_logging()

    config = get_env_vars()
    dev_config = get_dev_env_vars()

    public_bot = build_bot(flavor="public")
    dev_bot = build_bot(flavor="dev")

    # Start both bots concurrently
    await asyncio.gather(
        public_bot.start(config.discord_token),
        dev_bot.start(dev_config.discord_token),
    )


def main() -> None:
    try:
        asyncio.run(run_two_bots())
    except KeyboardInterrupt:
        print("[SHUTDOWN] received Ctrl+C")


if __name__ == "__main__":
    main()
