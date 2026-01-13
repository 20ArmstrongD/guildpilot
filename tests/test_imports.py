"""
Smoke tests for the GuildPilot repo.

Goal:
- Catch broken imports early (missing deps, bad module paths, syntax errors).
- Ensure each bot module's entrypoint imports cleanly.
- Ensure env-check logic can run with placeholder values (no real secrets).

Run:
  pytest -q
  pytest -q tests/test_smoke_all.py
"""

from __future__ import annotations

import importlib


# ---- Helpers ----
def _import(module_path: str) -> None:
    """Import a module by dotted path and raise a clear error if it fails."""
    importlib.import_module(module_path)


# ---- Import smoke tests ----
def test_import_top_level_packages() -> None:
    _import("modules")
    _import("modules.pilotai")
    _import("modules.rolecop")
    _import("modules.statwrangler")
    _import("modules.streamsentinel")


def test_import_entrypoints() -> None:
    """
    Import bot entrypoints (adjust if your file names differ).
    These imports should NOT start the bot or connect to Discord;
    they should only define functions/classes.
    """
    _import("modules.pilotai.main")
    _import("modules.rolecop")

    # If these modules have specific main files, import those instead.
    # Otherwise, importing the package is still useful.
    # Uncomment/adjust based on your actual layout:
    # _import("modules.statwrangler.main")
    # _import("modules.streamsentinel.main")


def test_env_check_with_placeholders(monkeypatch) -> None:
    """
    Ensures your env_check/get_env_vars function works with fake values.
    If your project uses different env var names, update below.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    monkeypatch.setenv("DISCORD_TOKEN", "test-placeholder")
    monkeypatch.setenv("GUILD_ID", "123456789012345678")

    # If env_check lives somewhere else, update this import path.
    from modules.pilotai.env_check import get_env_vars  # type: ignore

    config = get_env_vars()
    assert config is not None
