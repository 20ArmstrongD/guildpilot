"""
Unit tests for modules/rolecop/core/permissions.py.

Goal:
- Lock down the approver-gating logic (admin override + name-based roles)
  since this decides who can approve/deny promote/demote/kick requests.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import discord

from modules.rolecop.core.permissions import has_any_role_name, is_approver


def _role(name: str) -> MagicMock:
    role = MagicMock()
    role.name = name
    return role


def _member(role_names: list[str], *, administrator: bool = False) -> MagicMock:
    member = MagicMock(spec=discord.Member)
    member.roles = [_role(name) for name in role_names]
    member.guild_permissions = MagicMock(administrator=administrator)
    return member


def test_has_any_role_name_matches_case_insensitively() -> None:
    member = _member(["Admin", "Moderator"])
    assert has_any_role_name(member, ["admin"])


def test_has_any_role_name_no_match() -> None:
    member = _member(["Member"])
    assert not has_any_role_name(member, ["Admin"])


def test_has_any_role_name_empty_wanted_list() -> None:
    member = _member(["Admin"])
    assert not has_any_role_name(member, [])


def test_is_approver_administrator_always_true_even_without_named_role() -> None:
    member = _member([], administrator=True)
    assert is_approver(member, ["Admin"])


def test_is_approver_true_via_named_role() -> None:
    member = _member(["Admin"], administrator=False)
    assert is_approver(member, ["Admin"])


def test_is_approver_false_without_admin_or_named_role() -> None:
    member = _member(["Member"], administrator=False)
    assert not is_approver(member, ["Admin"])
