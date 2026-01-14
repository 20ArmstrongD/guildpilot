# from __future__ import annotations

# ruff: noqa: B008  # py-cord uses discord.discord.option(...) in command signatures
import json
from pathlib import Path

import discord
# from discord import discord.option
from discord.ext import commands

from .core.approvals import ApprovalRequest, ApprovalView
from .core.config_loader import (
    load_guild_settings,
    load_runtime_config,
    save_guild_settings,
)
from .core.permissions import is_approver

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../modules/rolecop/cog.py -> modules
ROLECOP_DIR = PROJECT_ROOT / "rolecop"

MEMB_MSG_PATH = ROLECOP_DIR / "messages" / "welc_msg_membs.json"
BOT_MSG_PATH = ROLECOP_DIR / "messages" / "welc_msg_bots.json"


def _load_messages(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        pass
    return []


class RoleCopCog(commands.Cog):
    """
    RoleCop:
    - Public servers: admins run /rolecop_setup once (approvals channel, approver roles, optional boundary role).
    - Personal server: auto-register settings using personal_config.json defaults (no manual setup required).
    - Promote/Demote: dynamic role targeting per command with guardrails and optional approvals.
    - Kick: approval-based (or instant for approvers if safe_mode is off).
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.cfg = load_runtime_config()
        self.guild_settings = load_guild_settings(self.cfg.guild_settings_path)

        self.member_msgs = _load_messages(MEMB_MSG_PATH)
        self.bot_msgs = _load_messages(BOT_MSG_PATH)

        # pending approvals in memory: message_id -> ApprovalRequest
        self.pending: dict[int, ApprovalRequest] = {}

    # ---------------- Config helpers ----------------
    def _is_personal(self, guild: discord.Guild | None) -> bool:
        return bool(guild and self.cfg.personal_guild_id and guild.id == self.cfg.personal_guild_id)

    def _get_guild_cfg(self, guild: discord.Guild) -> dict:
        """Resolve effective config for a guild (runtime defaults merged with per-guild overrides)."""
        overrides = self.guild_settings.get(str(guild.id), {})

        approvals_channel_name = overrides.get("approvals_channel_name", self.cfg.approvals_channel_name)
        approvals_channel_id = overrides.get("approvals_channel_id")
        approver_role_names = overrides.get("approver_role_names", self.cfg.approver_role_names)
        safe_mode = overrides.get("safe_mode", self.cfg.safe_mode_default)
        max_managed_role_id = overrides.get("max_managed_role_id")

        # Personal guild should not be forced into safe mode
        if self._is_personal(guild):
            safe_mode = False

        return {
            "safe_mode": bool(safe_mode),
            "approvals_channel_name": approvals_channel_name,
            "approvals_channel_id": approvals_channel_id,
            "approver_role_names": list(approver_role_names) if isinstance(approver_role_names, list) else [],
            "dm_approvers_first": bool(overrides.get("dm_approvers_first", self.cfg.dm_approvers_first)),
            "max_managed_role_id": max_managed_role_id,
        }

    def _find_approvals_channel(self, guild: discord.Guild, gcfg: dict) -> discord.TextChannel | None:
        ch_id = gcfg.get("approvals_channel_id")
        if isinstance(ch_id, int):
            ch = guild.get_channel(ch_id)
            if isinstance(ch, discord.TextChannel):
                return ch

        name = gcfg.get("approvals_channel_name")
        if not name:
            return None
        for ch in guild.text_channels:
            if ch.name == name:
                return ch
        return None

    def _is_configured(self, gcfg: dict) -> bool:
        """Configured means we know where to post approvals and who can approve."""
        has_channel = isinstance(gcfg.get("approvals_channel_id"), int) or bool(gcfg.get("approvals_channel_name"))
        roles = gcfg.get("approver_role_names")
        has_roles = isinstance(roles, list) and len(roles) > 0
        return bool(has_channel and has_roles)

    # ---------------- Auto-setup (personal guild) ----------------
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        # Ensure personal guild is pre-configured so you don't have to run /rolecop_setup there.
        await self._ensure_personal_guild_config()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        if self.cfg.personal_guild_id and guild.id == self.cfg.personal_guild_id:
            await self._ensure_personal_guild_config(guild=guild)

    async def _ensure_personal_guild_config(self, guild: discord.Guild | None = None) -> None:
        personal_id = self.cfg.personal_guild_id
        if not personal_id:
            return

        if guild is None:
            guild = self.bot.get_guild(personal_id)
        if guild is None:
            return

        key = str(guild.id)
        if key in self.guild_settings:
            return

        # Use runtime defaults (loaded from config/default.json + config/personal_config.json)
        approvals_name = self.cfg.approvals_channel_name
        approver_names = self.cfg.approver_role_names

        approvals_channel = None
        if approvals_name:
            approvals_channel = discord.utils.get(guild.text_channels, name=approvals_name)

        self.guild_settings[key] = {
            "safe_mode": False,  # personal guild should be convenient by default
            "approvals_channel_name": approvals_channel.name if approvals_channel else approvals_name,
            "approvals_channel_id": approvals_channel.id if approvals_channel else None,
            "approver_role_names": list(approver_names) if isinstance(approver_names, list) else [],
            "max_managed_role_id": None,
        }
        save_guild_settings(self.cfg.guild_settings_path, self.guild_settings)

    # ---------------- Guardrails ----------------
    def _is_privileged_role(self, role: discord.Role) -> bool:
        p = role.permissions
        return bool(
            p.administrator
            or p.manage_guild
            or p.manage_roles
            or p.manage_channels
            or p.manage_webhooks
            or p.ban_members
            or p.kick_members
        )

    def _role_reject_reason(self, guild: discord.Guild, role: discord.Role, gcfg: dict) -> str | None:
        me = guild.me
        if role.is_default():
            return "You can’t target **@everyone**."
        if role.managed:
            return "You can’t target managed/integration roles."
        if self._is_privileged_role(role):
            return "That role is privileged (admin/mod-level). RoleCop will not manage it."
        if me and role >= me.top_role:
            return "I can’t manage that role due to Discord role hierarchy. Move my bot role above it."
        max_id = gcfg.get("max_managed_role_id")
        if isinstance(max_id, int):
            boundary = guild.get_role(max_id)
            if boundary and role >= boundary:
                return f"That role is above this server’s RoleCop boundary (**{boundary.name}**)."
        return None

    async def _notify_requester(self, guild: discord.Guild, request: ApprovalRequest, approved: bool, approver: discord.Member) -> None:
        requester = guild.get_member(request.requester_id)
        if not requester:
            return

        decision = "APPROVED ✅" if approved else "DENIED ❌"
        target = guild.get_member(request.target_id)
        target_txt = target.mention if target else f"<@{request.target_id}>"

        extra = ""
        if request.action in {"promote", "demote"}:
            role_id = request.payload.get("role_id")
            role = guild.get_role(role_id) if isinstance(role_id, int) else None
            if role:
                extra = f"\n**Role:** {role.mention}"

        msg = (
            f"**RoleCop decision:** {decision}\n"
            f"**Action:** {request.action}\n"
            f"**Target:** {target_txt}"
            f"{extra}\n"
            f"**Approved by:** {approver.mention}"
        )
        if request.reason:
            msg += f"\n**Reason:** {request.reason}"

        try:
            await requester.send(msg)
        except discord.Forbidden:
            # DMs closed
            pass

    # ---------------- Setup command (public servers) ----------------
    @commands.slash_command(name="rolecop_setup", description="Configure RoleCop for this server (admin only).")
    async def rolecop_setup(
        self,
        ctx: discord.ApplicationContext,
        approvals_channel: discord.TextChannel = discord.option(
            discord.TextChannel,
            "Channel where approval requests are posted",
            required=True,
        ),
        approver_role_1: discord.Role = discord.option(
            discord.Role,
            "Role allowed to approve/deny requests",
            required=True,
        ),
        approver_role_2: discord.Role = discord.option(
            discord.Role,
            "Optional second approver role",
            required=False,
            default=None,
        ),
        max_managed_role: discord.Role = discord.option(
            discord.Role,
            "Optional boundary role (RoleCop can only manage roles BELOW this role)",
            required=False,
            default=None,
        ),
        safe_mode: bool = discord.option(
            bool,
            "If enabled, even approvers require button approval (two-person action)",
            required=False,
            default=False,
        ),
    ):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.respond("Run this command in a server.", ephemeral=True)

        # Only real admins/managers can configure
        if not (ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_roles):
            return await ctx.respond("You need Administrator or Manage Roles to run setup.", ephemeral=True)

        role_names = [approver_role_1.name]
        if approver_role_2:
            role_names.append(approver_role_2.name)

        # Save per-guild config
        self.guild_settings[str(ctx.guild.id)] = {
            "safe_mode": bool(safe_mode),
            "approvals_channel_name": approvals_channel.name,
            "approvals_channel_id": approvals_channel.id,
            "approver_role_names": role_names,
            "max_managed_role_id": max_managed_role.id if max_managed_role else None,
        }
        save_guild_settings(self.cfg.guild_settings_path, self.guild_settings)

        boundary_txt = max_managed_role.mention if max_managed_role else "None"

        msg = (
            "✅ RoleCop configured for this server.\n"
            f"- Approvals channel: **#{approvals_channel.name}**\n"
            f"- Approver roles: **{', '.join(role_names)}**\n"
            f"- Boundary role: {boundary_txt}\n"
            f"- Safe mode: **{safe_mode}**"
        )
        return await ctx.respond(msg, ephemeral=True)

    # ---------------- Utility commands ----------------
    @commands.slash_command(name="who_has_role", description="List members who have a specific role (admin only).")
    async def who_has_role(self, ctx: discord.ApplicationContext, role: discord.Role):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.respond("Run this in a server.", ephemeral=True)

        gcfg = self._get_guild_cfg(ctx.guild)
        if not is_approver(ctx.author, gcfg["approver_role_names"]):
            return await ctx.respond("You don’t have permission to use this.", ephemeral=True)

        members = [m for m in ctx.guild.members if role in m.roles]
        total = len(members)

        shown = members[:25]
        names = ", ".join(m.mention for m in shown) if shown else "None"

        msg = f"**{role.name}** has **{total}** member(s).\nShowing first {min(total, 25)}:\n{names}"
        return await ctx.respond(msg, ephemeral=True)

    @commands.slash_command(name="user_roles", description="Show the roles a member has (admin only).")
    async def user_roles(self, ctx: discord.ApplicationContext, user: discord.Member):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.respond("Run this in a server.", ephemeral=True)

        gcfg = self._get_guild_cfg(ctx.guild)
        if not is_approver(ctx.author, gcfg["approver_role_names"]):
            return await ctx.respond("You don’t have permission to use this.", ephemeral=True)

        roles = [r for r in user.roles if r.name != "@everyone"]
        roles_sorted = sorted(roles, key=lambda r: r.position, reverse=True)
        role_list = ", ".join(r.mention for r in roles_sorted) if roles_sorted else "None"
        return await ctx.respond(f"Roles for {user.mention}:\n{role_list}", ephemeral=True)

    # ---------------- Approval posting/execution ----------------
    async def _post_approval(
        self,
        *,
        ctx: discord.ApplicationContext,
        gcfg: dict,
        request: ApprovalRequest,
        title: str,
        description: str,
    ) -> None:
        assert ctx.guild is not None

        approvals_channel = self._find_approvals_channel(ctx.guild, gcfg)
        if approvals_channel is None:
            await ctx.respond(
                "RoleCop approvals channel not found. Run `/rolecop_setup` or fix your config.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(title=title, description=description)
        embed.add_field(name="Requester", value=f"<@{request.requester_id}>", inline=True)
        embed.add_field(name="Target", value=f"<@{request.target_id}>", inline=True)
        if request.reason:
            embed.add_field(name="Reason", value=request.reason, inline=False)

        async def on_approve(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            await self._execute_request(interaction, request, approved=True)

        async def on_deny(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            await self._execute_request(interaction, request, approved=False)

        view = ApprovalView(
            approver_role_names=gcfg["approver_role_names"],
            on_approve=on_approve,
            on_deny=on_deny,
            timeout=3600,
        )

        msg = await approvals_channel.send(embed=embed, view=view)
        self.pending[msg.id] = request

        await ctx.respond("✅ Request sent for approval.", ephemeral=True)

    async def _execute_request(self, interaction: discord.Interaction, request: ApprovalRequest, approved: bool) -> None:
        guild = interaction.guild
        if guild is None:
            return

        message = interaction.message  # type: ignore[assignment]
        approver = interaction.user
        if not isinstance(approver, discord.Member):
            approver = guild.get_member(approver.id) or approver  # type: ignore[assignment]

        if not approved:
            try:
                embed = message.embeds[0] if message and message.embeds else discord.Embed(title="RoleCop Request")
                embed.color = discord.Color.red()
                embed.add_field(name="Decision", value=f"❌ Denied by {approver.mention}", inline=False)
                await message.edit(embed=embed, view=None)
            except Exception:
                pass

            try:
                await interaction.followup.send("Denied.", ephemeral=True)
            except Exception:
                pass

            if isinstance(approver, discord.Member):
                await self._notify_requester(guild, request, approved=False, approver=approver)
            return

        # Approved -> execute action
        try:
            if request.action in {"promote", "demote"}:
                target = guild.get_member(request.target_id)
                if not target:
                    raise RuntimeError("Target not found in guild.")

                role_id = request.payload.get("role_id")
                if not isinstance(role_id, int):
                    raise RuntimeError("Missing role_id in request payload.")
                role = guild.get_role(role_id)
                if not role:
                    raise RuntimeError("Role no longer exists.")

                # Re-check guardrails at execution time (roles/hierarchy can change)
                gcfg = self._get_guild_cfg(guild)
                reject = self._role_reject_reason(guild, role, gcfg)
                if reject:
                    raise RuntimeError(reject)

                if request.action == "promote":
                    if role in target.roles:
                        raise RuntimeError("User already has that role.")
                    await target.add_roles(role, reason=f"Approved by {approver} (RoleCop)")
                else:
                    if role not in target.roles:
                        raise RuntimeError("User does not have that role.")
                    await target.remove_roles(role, reason=f"Approved by {approver} (RoleCop)")

            elif request.action == "kick":
                target = guild.get_member(request.target_id)
                if not target:
                    raise RuntimeError("Target not found in guild.")
                await target.kick(reason=f"Approved by {approver} (RoleCop): {request.reason or 'No reason'}")

            else:
                raise RuntimeError(f"Unknown action: {request.action}")

            # Update message
            embed = message.embeds[0] if message and message.embeds else discord.Embed(title="RoleCop Request")
            embed.color = discord.Color.green()
            embed.add_field(name="Decision", value=f"✅ Approved by {approver.mention}", inline=False)
            await message.edit(embed=embed, view=None)

            try:
                await interaction.followup.send("Approved & executed.", ephemeral=True)
            except Exception:
                pass

            if isinstance(approver, discord.Member):
                await self._notify_requester(guild, request, approved=True, approver=approver)

        except Exception as e:
            # Update message with failure
            try:
                embed = message.embeds[0] if message and message.embeds else discord.Embed(title="RoleCop Request")
                embed.color = discord.Color.orange()
                embed.add_field(name="Execution failed", value=str(e), inline=False)
                await message.edit(embed=embed, view=None)
            except Exception:
                pass

            try:
                await interaction.followup.send(f"Approval succeeded but execution failed: {e}", ephemeral=True)
            except Exception:
                pass

    # ---------------- Slash commands ----------------
    @commands.slash_command(name="promote", description="Request adding a role to a user (approval required unless approver).")
    async def promote(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Member = discord.option(discord.Member, "Member to promote", required=True),
        role: discord.Role = discord.option(discord.Role, "Role to add", required=True),
        reason: str = discord.option(str, "Optional reason", required=False, default=None),
    ):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.respond("Run this in a server.", ephemeral=True)

        gcfg = self._get_guild_cfg(ctx.guild)

        if not self._is_personal(ctx.guild) and not self._is_configured(gcfg):
            return await ctx.respond("RoleCop isn’t configured here. An admin must run `/rolecop_setup`.", ephemeral=True)

        reject = self._role_reject_reason(ctx.guild, role, gcfg)
        if reject:
            return await ctx.respond(f"🚫 {reject}", ephemeral=True)

        # No-op check
        if role in user.roles:
            return await ctx.respond(f"✅ {user.mention} already has {role.mention}.", ephemeral=True)

        requester_is_approver = is_approver(ctx.author, gcfg["approver_role_names"])
        if requester_is_approver and not gcfg["safe_mode"]:
            try:
                await user.add_roles(role, reason=f"Direct promote by {ctx.author} (RoleCop)")
                return await ctx.respond(f"✅ Added {role.mention} to {user.mention}.", ephemeral=True)
            except discord.Forbidden:
                return await ctx.respond("I don’t have permission to manage that role.", ephemeral=True)
            except discord.HTTPException:
                return await ctx.respond("Discord API error while promoting.", ephemeral=True)

        req = ApprovalRequest(
            requester_id=ctx.author.id,
            target_id=user.id,
            action="promote",
            reason=reason,
            payload={"role_id": role.id},
        )
        await self._post_approval(
            ctx=ctx,
            gcfg=gcfg,
            request=req,
            title="RoleCop: Promote Request",
            description=f"Request to **add** {role.mention} to {user.mention}.",
        )

    @commands.slash_command(name="demote", description="Request removing a role from a user (approval required unless approver).")
    async def demote(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Member = discord.option(discord.Member, "Member to demote", required=True),
        role: discord.Role = discord.option(discord.Role, "Role to remove", required=True),
        reason: str = discord.option(str, "Optional reason", required=False, default=None),
    ):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.respond("Run this in a server.", ephemeral=True)

        gcfg = self._get_guild_cfg(ctx.guild)

        if not self._is_personal(ctx.guild) and not self._is_configured(gcfg):
            return await ctx.respond("RoleCop isn’t configured here. An admin must run `/rolecop_setup`.", ephemeral=True)

        reject = self._role_reject_reason(ctx.guild, role, gcfg)
        if reject:
            return await ctx.respond(f"🚫 {reject}", ephemeral=True)

        # No-op check
        if role not in user.roles:
            return await ctx.respond(f"⚠️ {user.mention} does not have {role.mention}.", ephemeral=True)

        requester_is_approver = is_approver(ctx.author, gcfg["approver_role_names"])
        if requester_is_approver and not gcfg["safe_mode"]:
            try:
                await user.remove_roles(role, reason=f"Direct demote by {ctx.author} (RoleCop)")
                return await ctx.respond(f"✅ Removed {role.mention} from {user.mention}.", ephemeral=True)
            except discord.Forbidden:
                return await ctx.respond("I don’t have permission to manage that role.", ephemeral=True)
            except discord.HTTPException:
                return await ctx.respond("Discord API error while demoting.", ephemeral=True)

        req = ApprovalRequest(
            requester_id=ctx.author.id,
            target_id=user.id,
            action="demote",
            reason=reason,
            payload={"role_id": role.id},
        )
        await self._post_approval(
            ctx=ctx,
            gcfg=gcfg,
            request=req,
            title="RoleCop: Demote Request",
            description=f"Request to **remove** {role.mention} from {user.mention}.",
        )

    @commands.slash_command(name="kick", description="Request to kick a user (approval required unless approver).")
    async def kick(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Member = discord.option(discord.Member, "Member to kick", required=True),
        reason: str = discord.option(str, "Optional reason", required=False, default=None),
    ):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.respond("Run this in a server.", ephemeral=True)

        gcfg = self._get_guild_cfg(ctx.guild)

        if not self._is_personal(ctx.guild) and not self._is_configured(gcfg):
            return await ctx.respond("RoleCop isn’t configured here. An admin must run `/rolecop_setup`.", ephemeral=True)

        requester_is_approver = is_approver(ctx.author, gcfg["approver_role_names"])
        if requester_is_approver and not gcfg["safe_mode"]:
            try:
                await user.kick(reason=f"Direct kick by {ctx.author} (RoleCop): {reason or 'No reason'}")
                return await ctx.respond(f"✅ Kicked {user.mention}.", ephemeral=True)
            except discord.Forbidden:
                return await ctx.respond("I don’t have permission to kick members.", ephemeral=True)
            except discord.HTTPException:
                return await ctx.respond("Discord API error while kicking.", ephemeral=True)

        req = ApprovalRequest(
            requester_id=ctx.author.id,
            target_id=user.id,
            action="kick",
            reason=reason,
            payload={},
        )
        await self._post_approval(
            ctx=ctx,
            gcfg=gcfg,
            request=req,
            title="RoleCop: Kick Request",
            description=f"Request to **kick** {user.mention}.",
        )
