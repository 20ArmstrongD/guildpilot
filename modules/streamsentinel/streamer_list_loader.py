from pathlib import Path
from typing import Optional, Union

STREAMERS_FILE = Path("/home/DiscordPi/code/discord_bots/Streaming-Bot/src/streamers.txt")

def load_streamers(path: Optional[Union[str, Path]] = None) -> list[str]:
    """
    Load Twitch logins from a file (one per line).
    - Ignores blank lines and lines or suffixes after '#'
    - De-dupes case-insensitively while preserving order
    """
    file_path = Path(path).expanduser() if path else STREAMERS_FILE

    if not (file_path.exists() and file_path.is_file()):
        print(f"[streamer_list_load] No streamer list found at {file_path}")
        return []

    out: list[str] = []
    seen: set[str] = set()

    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            # strip inline comments and whitespace
            s = line.split("#", 1)[0].strip()
            if not s:
                continue
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(key)  # <-- append login (always lowercase)

    print(f"[streamer_list_load] Loaded {len(out)} streamers: {out}")
    return out  # <-- missing before
