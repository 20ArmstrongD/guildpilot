from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# repo root -> modules/rolecop/core/config_loader.py
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROLECOP_DIR = PROJECT_ROOT / "modules" / "rolecop"

CONFIG_DIR = ROLECOP_DIR / "config"
STORAGE_DIR = ROLECOP_DIR / "storage"

PUBLIC_CONFIG_PATH = CONFIG_DIR / "default.json"  # <- matches your screenshot
PERSONAL_CONFIG_PATH = CONFIG_DIR / "personal_config.json"  # <- matches your screenshot
GUILD_SETTINGS_PATH = STORAGE_DIR / "guild_settings.json"


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@dataclass(frozen=True)
class RoleCopRuntimeConfig:
    personal_guild_id: int | None
    safe_mode_default: bool
    approvals_channel_name: str | None
    approver_role_names: list[str]
    dm_approvers_first: bool
    guild_settings_path: Path


def load_runtime_config() -> RoleCopRuntimeConfig:
    """
    Load base defaults from config/default.json and overlay config/personal_config.json if present.
    """
    public_cfg = _load_json(PUBLIC_CONFIG_PATH, {})
    personal_cfg = _load_json(PERSONAL_CONFIG_PATH, {})
    merged = _deep_merge(public_cfg, personal_cfg)

    # allow either top-level keys or nested "defaults"
    defaults = merged.get("defaults")
    if not isinstance(defaults, dict):
        defaults = merged  # fallback

    role_names = defaults.get(
        "approver_role_names", defaults.get("approver_role_names", [])
    )
    if not isinstance(role_names, list):
        role_names = []

    return RoleCopRuntimeConfig(
        personal_guild_id=merged.get("personal_guild_id"),
        safe_mode_default=bool(merged.get("safe_mode_default", True)),
        approvals_channel_name=defaults.get("approvals_channel_name"),
        approver_role_names=[str(x) for x in role_names],
        dm_approvers_first=bool(defaults.get("dm_approvers_first", False)),
        guild_settings_path=GUILD_SETTINGS_PATH,
    )


def load_guild_settings(path: Path) -> dict[str, dict]:
    """
    Returns dict: guild_id_str -> settings dict
    Stored as {"guilds": { "<id>": { ... } }}
    """
    data = _load_json(path, {"guilds": {}})
    if not isinstance(data, dict):
        return {}
    guilds = data.get("guilds")
    if not isinstance(guilds, dict):
        return {}
    return guilds


def save_guild_settings(path: Path, guilds: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"guilds": guilds}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
