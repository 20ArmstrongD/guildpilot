from __future__ import annotations

import json
from pathlib import Path

import discord
from discord import Option
from discord.ext import commands

from .core.approvals import ApprovalRequest, ApprovalView
from .core.config_loader import load_runtime_config, load_guild_settings, save_guild_settings
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
        """Resolve effective config for a guild (personal merged + per-guild overrides)."""
        overrides = self.guild_settings.get(str(guild.id), {})

        approvals_channel_name = overrides.get("approvals_channel_name", self.cfg.approvals_channel_name)
        approvals_channel_id = overrides.get("approvals_channel_id")

        approver_role_names = overrides.get("approver_role_names", self.cfg.approver_role_names)
        safe_mode = overrides.get("safe_mode", self.cfg.safe_mode_default)

        promote_role_id = overrides.get("promote_role_id")
        demote_role_id = overrides.get("demote_role_id")

        # Personal guild should not be forced into safe mode
        if self._is_personal(guild):
            safe_mode = False

        return {
            "safe_mode": bool(safe_mode),
            "approvals_channel_name": approvals_channel_name,
            "approvals_channel_id": approvals_channel_id,
            "approver_role_names": list(approver_role_names) if isinstance(approver_role_names, list) else [],
            "dm_approvers_first": bool(overrides.get("dm_approvers_first", self.cfg.dm_approvers_first)),
            "promote_role_id": promote_role_id,
            "demote_role_id": demote_role_id,
        }

    def _find_text_channel(self, guild: discord.Guild, *, channel_id: int | None, name: str | None) -> discord.TextChannel | None:
        # Prefer ID (more reliable), fall back to name
        if isinstance(channel_id, int):
            ch = guild.get_channel(channel_id)
            if isinstance(ch, discord.TextChannel):
                return ch

        if not name:
            return None

        for ch in guild.text_channels:
            if ch.name == name:
                return ch

        return None

    def _is_configured(self, gcfg: dict) -> bool:
        return isinstance(gcfg.get("promote_role_id"), int) and isinstance(gcfg.get("demote_role_id"), int) and (
            isinstance(gcfg.get("approvals_channel_id"), int) or bool(gcfg.get("approvals_channel_name"))
        )

    # ---------------- Setup command (public servers) ----------------
    @commands.slash_command(name="rolecop_setup", description="Configure RoleCop for this server (admin only).")
    async def rolecop_setup(
        self,
        ctx: discord.ApplicationContext,
        promote_role: discord.Role = Option(discord.Role, "Role to assign when promoting", required=True),
        demote_role: discord.Role = Option(discord.Role, "Role to remove when demoting", required=True),
        approvals_channel: discord.TextChannel = Option(discord.TextChannel, "Channel where approval requests are posted", required=True),
        approver_role_1: discord.Role = Option(discord.Role, "Primary approver role", required=True),
        approver_role_2: discord.Role = Option(discord.Role, "Secondary approver role (optional)", required=False, default=None),
        safe_mode: bool = Option(bool, "Extra guardrails (recommended)", required=False, default=False),
    ):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.respond("Run this command in a server.", ephemeral=True)

        guild = ctx.guild
        me = guild.me

        # Only real admins/managers can configure
        if not (ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_roles):
            return await ctx.respond("You need Administrator or Manage Roles to run setup.", ephemeral=True)

        # Bot permission guardrails (setup-time, not later)
        if me is None or not me.guild_permissions.manage_roles:
            return await ctx.respond("I need the **Manage Roles** permission before I can run RoleCop.", ephemeral=True)

        # Channel guardrail
        ch_perms = approvals_channel.permissions_for(me)
        if not ch_perms.send_messages:
            return await ctx.respond(
                f"I can’t send messages in {approvals_channel.mention}. Fix channel perms and try again.",
                ephemeral=True,
            )

        # Role guardrails
        def role_problem(r: discord.Role) -> str | None:
            if r.is_default():
                return "You can’t use **@everyone** as a role in RoleCop."
            if r.managed:
                return f"`{r.name}` is a managed/integration role and can’t be used."
            if r >= me.top_role:
                return f"My top role must be **above** `{r.name}` to manage it."
            return None

        for r in (promote_role, demote_role, approver_role_1):
            msg = role_problem(r)
            if msg:
                return await ctx.respond(msg, ephemeral=True)

        if approver_role_2 is not None:
            msg = role_problem(approver_role_2)
            if msg:
                return await ctx.respond(msg, ephemeral=True)
            if approver_role_2.id == approver_role_1.id:
                return await ctx.respond("Approver Role 2 must be different from Approver Role 1.", ephemeral=True)

        role_names = [approver_role_1.name]
        if approver_role_2 is not None:
            role_names.append(approver_role_2.name)

        # Save config (store BOTH id+name for robustness; rest of code can keep using names)
        self.guild_settings[str(guild.id)] = {
            "safe_mode": bool(safe_mode),
            "promote_role_id": promote_role.id,
            "demote_role_id": demote_role.id,
            "approvals_channel_name": approvals_channel.name,
            "approvals_channel_id": approvals_channel.id,
            "approver_role_names": role_names,
        }
        save_guild_settings(self.cfg.guild_settings_path, self.guild_settings)

        await ctx.respond(
            "✅ RoleCop configured for this server.\n"
            f"- Promote role: **{promote_role.name}**\n"
            f"- Demote role: **{demote_role.name}**\n"
            f"- Approvals channel: **#{approvals_channel.name}**\n"
            f"- Approver roles: **{', '.join(role_names)}**\n"
            f"- Safe mode: **{safe_mode}**",
            ephemeral=True,
        )

    # ---------------- Utility commands ----------------
    @commands.slash_command(name="who_has_role", description="List members who have a specific role (admin only).")
    async def who_has_role(
        self,
        ctx: discord.ApplicationContext,
        role: discord.Role = Option(discord.Role, "Role to check", required=True),
    ):
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
        await ctx.respond(msg, ephemeral=True)

    @commands.slash_command(name="user_roles", description="Show the roles a member has (admin only).")
    async def user_roles(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Member = Option(discord.Member, "Member to inspect", required=True),
    ):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.respond("Run this in a server.", ephemeral=True)

        gcfg = self._get_guild_cfg(ctx.guild)
        if not is_approver(ctx.author, gcfg["approver_role_names"]):
            return await ctx.respond("You don’t have permission to use this.", ephemeral=True)

        roles = [r for r in user.roles if r.name != "@everyone"]
        roles_sorted = sorted(roles, key=lambda r: r.position, reverse=True)
        role_list = ", ".join(r.mention for r in roles_sorted) if roles_sorted else "None"
        await ctx.respond(f"Roles for {user.mention}:\n{role_list}", ephemeral=True)

    # ---------------- Promote/Demote/Kick core ----------------
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

        approvals_channel = self._find_text_channel(
            ctx.guild,
            channel_id=gcfg.get("approvals_channel_id"),
            name=gcfg.get("approvals_channel_name"),
        )
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

        message = interaction.message  # type: ignore
        approver = interaction.user

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
            return

        try:
            if request.action in {"promote", "demote"}:
                target = guild.get_member(request.target_id)
                if not target:
                    raise RuntimeError("Target not found in guild.")

                role_id = request.payload["role_id"]
                role = guild.get_role(role_id)
                if not role:
                    raise RuntimeError("Configured role no longer exists.")

                # Extra safe-mode guardrail: bot must be able to manage the role
                me = guild.me
                if me and role >= me.top_role:
                    raise RuntimeError("Bot role hierarchy prevents managing that role.")

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

            embed = message.embeds[0] if message and message.embeds else discord.Embed(title="RoleCop Request")
            embed.color = discord.Color.green()
            embed.add_field(name="Decision", value=f"✅ Approved by {approver.mention}", inline=False)
            await message.edit(embed=embed, view=None)

            try:
                await interaction.followup.send("Approved & executed.", ephemeral=True)
            except Exception:
                pass

        except Exception as e:
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
    @commands.slash_command(name="promote", description="Request a promotion for a user.")
    async def promote(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Member = Option(discord.Member, "Member to promote", required=True),
        reason: str = Option(str, "Optional reason", required=False, default=None),
    ):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.respond("Run this in a server.", ephemeral=True)

        gcfg = self._get_guild_cfg(ctx.guild)

        # Require setup (unless personal guild has defaults that work)
        if not self._is_personal(ctx.guild) and not self._is_configured(gcfg):
            return await ctx.respond("Not configured yet. An admin must run `/rolecop_setup` first.", ephemeral=True)

        role_id = gcfg.get("promote_role_id")
        if not isinstance(role_id, int):
            return await ctx.respond("Promote role is not configured. Run `/rolecop_setup`.", ephemeral=True)

        role = ctx.guild.get_role(role_id)
        if not role:
            return await ctx.respond("Configured promote role no longer exists. Re-run `/rolecop_setup`.", ephemeral=True)

        if role in user.roles:
            return await ctx.respond(f"✅ {user.mention} already has **{role.name}**.", ephemeral=True)

        # If requester is approver, execute instantly
        if is_approver(ctx.author, gcfg["approver_role_names"]):
            try:
                await user.add_roles(role, reason=f"Direct promote by {ctx.author} (RoleCop)")
                return await ctx.respond(f"✅ Promoted {user.mention} to **{role.name}**.", ephemeral=True)
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
            description=f"Request to **add** role {role.mention} to {user.mention}.",
        )

    @commands.slash_command(name="demote", description="Request a demotion (remove demote role) for a user.")
    async def demote(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Member = Option(discord.Member, "Member to demote", required=True),
        reason: str = Option(str, "Optional reason", required=False, default=None),
    ):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.respond("Run this in a server.", ephemeral=True)

        gcfg = self._get_guild_cfg(ctx.guild)

        if not self._is_personal(ctx.guild) and not self._is_configured(gcfg):
            return await ctx.respond("Not configured yet. An admin must run `/rolecop_setup` first.", ephemeral=True)

        role_id = gcfg.get("demote_role_id")
        if not isinstance(role_id, int):
            return await ctx.respond("Demote role is not configured. Run `/rolecop_setup`.", ephemeral=True)

        role = ctx.guild.get_role(role_id)
        if not role:
            return await ctx.respond("Configured demote role no longer exists. Re-run `/rolecop_setup`.", ephemeral=True)

        if role not in user.roles:
            return await ctx.respond(f"⚠️ {user.mention} does not have **{role.name}**.", ephemeral=True)

        if is_approver(ctx.author, gcfg["approver_role_names"]):
            try:
                await user.remove_roles(role, reason=f"Direct demote by {ctx.author} (RoleCop)")
                return await ctx.respond(f"✅ Removed **{role.name}** from {user.mention}.", ephemeral=True)
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
            description=f"Request to **remove** role {role.mention} from {user.mention}.",
        )

    @commands.slash_command(name="kick", description="Request to kick a user (approval required unless approver).")
    async def kick(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Member = Option(discord.Member, "Member to kick", required=True),
        reason: str = Option(str, "Optional reason", required=False, default=None),
    ):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.respond("Run this in a server.", ephemeral=True)

        gcfg = self._get_guild_cfg(ctx.guild)

        if not self._is_personal(ctx.guild) and not self._is_configured(gcfg):
            return await ctx.respond("Not configured yet. An admin must run `/rolecop_setup` first.", ephemeral=True)

        if is_approver(ctx.author, gcfg["approver_role_names"]):
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
