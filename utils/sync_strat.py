from __future__ import annotations

from pathlib import Path

from discord.ext import commands
from modules.utils.guild_sync import sync_commands_to_guilds_from_file


async def sync_from_registry(
    bot: commands.Bot,
    *,
    flavor: str,
    guilds_json: Path,
    do_global_if_empty: bool = True,
    also_global_for_public: bool = False,
) -> None:
    """
    Shared sync strategy for dev/public.

    - Always attempts guild-sync to IDs listed in guilds_json (fast).
    - If no target guilds exist:
        - dev: usually do nothing (because dev bot should be in guilds)
        - public: optionally global-sync
    - Optionally also run a global sync for public after guild sync.
    """
    # 1) Fast path: guild sync to registry targets
    results = await sync_commands_to_guilds_from_file(bot, guilds_json, concurrency=3)

    ok = sum(1 for v in results.values() if isinstance(v, str) and v.startswith("ok"))
    total = len(results)

    # total includes "not_in_guild" + ok + errors
    print(f"[SYNC:{flavor}] Registry guild sync: {ok}/{total} ok")

    # Determine if we actually had any guilds to sync to (present in bot.guilds)
    had_targets = any(v != "not_in_guild" for v in results.values())

    # 2) If this bot isn't in any registry guilds, maybe do global sync
    if not had_targets and do_global_if_empty:
        synced = await bot.sync_commands()  # global
        count = len(synced) if synced is not None else "?"
        print(f"[SYNC:{flavor}] No registry guild targets; global sync: {count} cmds")
        return

    # 3) Optional: also global-sync public bot after guild sync
    if flavor == "public" and also_global_for_public:
        synced = await bot.sync_commands()
        count = len(synced) if synced is not None else "?"
        print(f"[SYNC:{flavor}] Global sync after registry: {count} cmds")
