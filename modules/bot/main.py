import asyncio
import logging

import discord

from modules.core.env_check.env_check import get_dev_env_vars, get_env_vars
from utils.guild_sync import sync_commands_to_guilds_from_file
from utils.sync_strat import sync_from_registry
from pathlib import Path


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


def build_bot(*, flavor: str, dev_guild_id: int | None = None) -> discord.Bot:
    intents = discord.Intents.default()
    intents.message_content = True

    bot = discord.Bot(intents=intents)

    # ✅ attach flavor + registry path BEFORE loading extensions
    bot.flavor = flavor

    project_root = Path(__file__).resolve().parents[2]  # adjust if your main.py is located differently
    if flavor == "dev":
        bot.guild_registry_path = project_root / "modules" / "core" / "guilds" / "dev_guilds.json"
    else:
        bot.guild_registry_path = project_root / "modules" / "core" / "guilds" / "public_guilds.json"

    print(f"[BOOT:{flavor}] loading modules")

    loaded: list[str] = []
    for name, path in MODULES_PUBLIC:
        bot.load_extension(path)
        loaded.append(name)
    print(f"[BOOT:{flavor}] Loaded modules: {', '.join(loaded)}")

    if flavor == "dev":
        dev_loaded: list[str] = []
        for name, path in MODULES_DEV_ONLY:
            bot.load_extension(path)
            dev_loaded.append(name)
        print(f"[BOOT:{flavor}] Loaded dev modules: {', '.join(dev_loaded)}")

    @bot.event
    async def on_ready():
        print(f"\n===== STARTUP:{flavor} =====")
        print(f"[READY:{flavor}] Logged in as {bot.user} (id={bot.user.id})")

        if getattr(bot, "_did_sync_once", False):
            print(f"[READY:{flavor}] Already synced commands once; skipping re-sync.")
            print(f"===== READY:{flavor} =====\n")
            return

        bot._did_sync_once = True
        print(f"[READY:{flavor}] Syncing commands...")

        guilds_json: Path = bot.guild_registry_path

        try:
            results = await sync_commands_to_guilds_from_file(
                bot,
                guilds_json,
                concurrency=3,
                tag=f"{flavor}:guilds",
            )

            if results:
                ok = sum(1 for v in results.values() if v == "ok" or str(v).startswith("ok"))
                err = sum(1 for v in results.values() if str(v).startswith("error:"))
                skipped = sum(1 for v in results.values() if v == "not_in_guild")
                print(f"[DEPLOY:{flavor}] deployed to {ok} guild(s) | {err} error(s) | {skipped} skipped")
            else:
                print(f"[DEPLOY:{flavor}] no registry targets (0 guilds)")

        except Exception as e:
            print(f"[DEPLOY:{flavor}] ERROR syncing commands: {type(e).__name__}: {e}")

        # Commands loaded locally (in-memory)
        cmds = list(bot.walk_application_commands())

        unique: dict[str, object] = {}
        for c in cmds:
            key = getattr(c, "qualified_name", c.name)
            unique[key] = c

        print(f"[CMDS:{flavor}] loaded {len(unique)} commands locally (raw: {len(cmds)})")
        for name in sorted(unique.keys()):
            print(f"    • /{name}")

        print(f"\n===== READY:{flavor} =====\n")

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
