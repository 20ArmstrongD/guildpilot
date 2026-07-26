"""
Unit tests for modules/rolecop/core/approvals.py.

Goal:
- Confirm ApprovalView.interaction_check actually gates button clicks to
  approvers only, since that's the whole point of RoleCop's approval flow.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord

from modules.rolecop.core.approvals import ApprovalView


def _role(name: str) -> MagicMock:
    role = MagicMock()
    role.name = name
    return role


def _member(role_names: list[str], *, administrator: bool = False) -> MagicMock:
    member = MagicMock(spec=discord.Member)
    member.roles = [_role(name) for name in role_names]
    member.guild_permissions = MagicMock(administrator=administrator)
    return member


def _make_view() -> ApprovalView:
    return ApprovalView(
        approver_role_names=["Admin"],
        on_approve=AsyncMock(),
        on_deny=AsyncMock(),
    )


def _interaction_for(member: MagicMock) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = member
    interaction.response = AsyncMock()
    return interaction


def test_interaction_check_allows_approver_role() -> None:
    async def scenario() -> None:
        view = _make_view()
        interaction = _interaction_for(_member(["Admin"]))

        assert await view.interaction_check(interaction) is True
        interaction.response.send_message.assert_not_called()

    asyncio.run(scenario())


def test_interaction_check_allows_administrator() -> None:
    async def scenario() -> None:
        view = _make_view()
        interaction = _interaction_for(_member([], administrator=True))

        assert await view.interaction_check(interaction) is True

    asyncio.run(scenario())


def test_interaction_check_denies_non_approver_and_notifies() -> None:
    async def scenario() -> None:
        view = _make_view()
        interaction = _interaction_for(_member(["Member"]))

        assert await view.interaction_check(interaction) is False
        interaction.response.send_message.assert_called_once()
        assert (
            interaction.response.send_message.call_args.kwargs.get("ephemeral")
            is True
        )

    asyncio.run(scenario())
