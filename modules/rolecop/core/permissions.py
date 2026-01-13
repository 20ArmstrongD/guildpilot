from __future__ import annotations

import discord


def _norm(s: str) -> str:
    return s.strip().lower()


def has_any_role_name(member: discord.Member, role_names: list[str]) -> bool:
    wanted = {_norm(x) for x in role_names if isinstance(x, str)}
    if not wanted:
        return False
    return any(_norm(r.name) in wanted for r in member.roles)


def is_approver(member: discord.Member, approver_role_names: list[str]) -> bool:
    # Strong built-in perms always win
    if member.guild_permissions.administrator:
        return True
    # Name-based roles (your personal mode uses this)
    return has_any_role_name(member, approver_role_names)
