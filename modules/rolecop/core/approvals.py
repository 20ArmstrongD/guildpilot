from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Awaitable

import discord

from .permissions import is_approver


@dataclass
class ApprovalRequest:
    requester_id: int
    target_id: int
    action: str  # "promote" | "demote" | "kick"
    reason: str | None
    payload: dict  # action-specific data (role ids, etc.)


class ApprovalView(discord.ui.View):
    def __init__(
        self,
        *,
        approver_role_names: list[str],
        on_approve: Callable[[discord.Interaction], Awaitable[None]],
        on_deny: Callable[[discord.Interaction], Awaitable[None]],
        timeout: float = 3600,
    ) -> None:
        super().__init__(timeout=timeout)
        self.approver_role_names = approver_role_names
        self._on_approve = on_approve
        self._on_deny = on_deny

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        if is_approver(interaction.user, self.approver_role_names):
            return True
        try:
            await interaction.response.send_message(
                "You don’t have permission to approve/deny this request.",
                ephemeral=True,
            )
        except Exception:
            pass
        return False

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve_btn(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self._on_approve(interaction)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny_btn(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self._on_deny(interaction)
