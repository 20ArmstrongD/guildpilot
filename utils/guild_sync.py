from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from discord.ext import commands


from typing import Any

def extract_guild_ids(data: Any) -> list[int]:
    guild_ids: set[int] = set()

    # Case A: [123, 456] or [{"id":123}, ...]
    if isinstance(data, list):
        for item in data:
            if isinstance(item, int):
                guild_ids.add(item)
            elif isinstance(item, dict) and "id" in item:
                try:
                    guild_ids.add(int(item["id"]))
                except (TypeError, ValueError):
                    pass

    # Case B: {"servers": [{"id":...}, ...]}  ✅ YOUR FILE
    elif isinstance(data, dict):
        for key in ("servers", "guilds"):
            if isinstance(data.get(key), list):
                for item in data[key]:
                    if isinstance(item, dict) and "id" in item:
                        try:
                            guild_ids.add(int(item["id"]))
                        except (TypeError, ValueError):
                            pass

        # Case C: {"123": {...}, "456": {...}}
        for k in data.keys():
            try:
                guild_ids.add(int(k))
            except (TypeError, ValueError):
                pass

    return sorted(guild_ids)


def load_guild_ids_from_json(path: Path) -> list[int]:
    if not path.exists():
        return []

    raw = json.loads(path.read_text(encoding="utf-8"))
    return extract_guild_ids(raw)



async def sync_commands_to_guilds_from_file(
    bot: discord.Bot,
    guilds_json_path: Path,
    *,
    tag: str = "guilds",
    concurrency: int = 3,
) -> dict[int, str]:
    """
    Reads guild IDs from guilds_json_path and syncs slash commands to each guild.
    Logs per-guild results with guild name + id.
    Returns {guild_id: "ok" | "not_in_guild" | "error: ..."}.
    """
    guild_ids = load_guild_ids_from_json(guilds_json_path)

    if not guild_ids:
        print(f"[SYNC:{tag}] No guild IDs found in {guilds_json_path}")
        return {}

    present_ids = {g.id for g in bot.guilds}
    target_ids = [gid for gid in guild_ids if gid in present_ids]
    missing_ids = [gid for gid in guild_ids if gid not in present_ids]

    print(
        f"[SYNC:{tag}] registry: {len(guild_ids)} ids | "
        f"connected: {len(present_ids)} guilds | "
        f"targets: {len(target_ids)} | "
        f"skipping: {len(missing_ids)}"
    )

    results: dict[int, str] = {gid: "not_in_guild" for gid in missing_ids}

    sem = asyncio.Semaphore(concurrency)

    def _guild_label(gid: int) -> str:
        g = bot.get_guild(gid)
        if g is None:
            return f"Unknown Guild ({gid})"
        return f"{g.name} ({g.id})"

    async def _sync_one(gid: int) -> None:
        async with sem:
            label = _guild_label(gid)
            try:
                print(f"[SYNC:{tag}] → syncing to {label}")
                synced = await bot.sync_commands(guild_ids=[gid])

                # py-cord may return None even on success
                if synced is None:
                    results[gid] = "ok"
                    print(f"[SYNC:{tag}] ✅ synced {label}")
                else:
                    results[gid] = "ok"
                    print(f"[SYNC:{tag}] ✅ synced {label} ({len(synced)} commands)")

            except Exception as e:
                results[gid] = f"error: {type(e).__name__}: {e}"
                print(f"[SYNC:{tag}] ❌ failed {label}: {type(e).__name__}: {e}")

    await asyncio.gather(*(_sync_one(gid) for gid in target_ids))

    ok = sum(1 for v in results.values() if v == "ok")
    err = sum(1 for v in results.values() if isinstance(v, str) and v.startswith("error:"))
    skipped = sum(1 for v in results.values() if v == "not_in_guild")

    print(f"[SYNC:{tag}] done: {ok} ok | {err} errors | {skipped} skipped")

    # Optional: print skipped guilds by name/id for clarity
    if skipped:
        for gid in missing_ids:
            print(f"[SYNC:{tag}] ⏭️  skipped (bot not in guild): {_guild_label(gid)}")

    return results