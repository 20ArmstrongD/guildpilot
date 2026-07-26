from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("pilotai.storage")

STORAGE_DIR = Path(__file__).resolve().parent / "storage"
CONVOS_PATH = STORAGE_DIR / "convos.json"


def load_state(
    path: Path = CONVOS_PATH,
) -> tuple[dict[int, dict[str, Any]], dict[int, int]]:
    """Returns (convos, msg_to_root), matching PilotAI's in-memory shapes."""
    if not path.exists():
        return {}, {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Could not parse %s; starting with empty state.", path)
        return {}, {}

    convos: dict[int, dict[str, Any]] = {}
    for root_id_str, meta in data.get("convos", {}).items():
        try:
            convos[int(root_id_str)] = {
                "history": meta["history"],
                "last_active": datetime.fromisoformat(meta["last_active"]),
                "channel_id": meta["channel_id"],
            }
        except (KeyError, TypeError, ValueError):
            continue

    msg_to_root: dict[int, int] = {}
    for msg_id_str, root_id in data.get("msg_to_root", {}).items():
        try:
            msg_to_root[int(msg_id_str)] = int(root_id)
        except (TypeError, ValueError):
            continue

    return convos, msg_to_root


def save_state(
    convos: dict[int, dict[str, Any]],
    msg_to_root: dict[int, int],
    path: Path = CONVOS_PATH,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "convos": {
            str(root_id): {
                "history": meta["history"],
                "last_active": meta["last_active"].isoformat(),
                "channel_id": meta["channel_id"],
            }
            for root_id, meta in convos.items()
        },
        "msg_to_root": {str(k): v for k, v in msg_to_root.items()},
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
