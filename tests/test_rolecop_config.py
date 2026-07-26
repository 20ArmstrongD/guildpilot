"""
Unit tests for modules/rolecop/core/config_loader.py.

Goal:
- Lock down the default/personal config merge behavior.
- Regression-test the bug where PUBLIC_CONFIG_PATH pointed at a file
  (config/default.json) that didn't exist in the repo (it was named
  public.example.json), silently leaving RoleCop's public defaults empty.
"""

from __future__ import annotations

import json

from modules.rolecop.core import config_loader


def test_public_config_path_exists_in_repo() -> None:
    """Regression test: the loader must point at a file that's actually
    committed, or RoleCop silently falls back to an empty config."""
    assert config_loader.PUBLIC_CONFIG_PATH.exists()


def test_deep_merge_overlays_nested_dicts() -> None:
    base = {"defaults": {"a": 1, "b": 2}, "top": "base"}
    override = {"defaults": {"b": 99, "c": 3}}

    merged = config_loader._deep_merge(base, override)

    assert merged == {"defaults": {"a": 1, "b": 99, "c": 3}, "top": "base"}


def test_load_runtime_config_reads_default_json(tmp_path, monkeypatch) -> None:
    default_path = tmp_path / "default.json"
    default_path.write_text(
        json.dumps(
            {
                "safe_mode_default": True,
                "defaults": {
                    "approvals_channel_name": "admin-approval",
                    "approver_role_names": ["Admin"],
                    "dm_approvers_first": False,
                },
            }
        )
    )
    monkeypatch.setattr(config_loader, "PUBLIC_CONFIG_PATH", default_path)
    monkeypatch.setattr(
        config_loader, "PERSONAL_CONFIG_PATH", tmp_path / "missing_personal.json"
    )

    cfg = config_loader.load_runtime_config()

    assert cfg.approvals_channel_name == "admin-approval"
    assert cfg.approver_role_names == ["Admin"]
    assert cfg.safe_mode_default is True


def test_load_runtime_config_personal_overlay_wins(tmp_path, monkeypatch) -> None:
    default_path = tmp_path / "default.json"
    default_path.write_text(
        json.dumps(
            {
                "defaults": {
                    "approver_role_names": ["Admin"],
                    "approvals_channel_name": "admin-approval",
                }
            }
        )
    )
    personal_path = tmp_path / "personal_config.json"
    personal_path.write_text(
        json.dumps({"personal_guild_id": 42, "defaults": {"approver_role_names": ["Owner"]}})
    )

    monkeypatch.setattr(config_loader, "PUBLIC_CONFIG_PATH", default_path)
    monkeypatch.setattr(config_loader, "PERSONAL_CONFIG_PATH", personal_path)

    cfg = config_loader.load_runtime_config()

    assert cfg.personal_guild_id == 42
    assert cfg.approver_role_names == ["Owner"]  # personal overlay wins
    assert cfg.approvals_channel_name == "admin-approval"  # untouched key preserved


def test_load_runtime_config_missing_files_falls_back_to_empty_defaults(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        config_loader, "PUBLIC_CONFIG_PATH", tmp_path / "missing_default.json"
    )
    monkeypatch.setattr(
        config_loader, "PERSONAL_CONFIG_PATH", tmp_path / "missing_personal.json"
    )

    cfg = config_loader.load_runtime_config()

    assert cfg.approver_role_names == []
    assert cfg.approvals_channel_name is None


def test_guild_settings_round_trip(tmp_path) -> None:
    path = tmp_path / "guild_settings.json"
    guilds = {"123": {"approver_role_names": ["Admin"], "safe_mode": True}}

    config_loader.save_guild_settings(path, guilds)
    loaded = config_loader.load_guild_settings(path)

    assert loaded == guilds


def test_load_guild_settings_missing_file_returns_empty_dict(tmp_path) -> None:
    loaded = config_loader.load_guild_settings(tmp_path / "does_not_exist.json")
    assert loaded == {}
