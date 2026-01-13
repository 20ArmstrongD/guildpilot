import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

from .elements import EMOJI_APPROVE, EMOJI_DENY #, #log_request_kick

log = logging.getLogger(__name__)

# Cooldown dictionary to prevent spam
kick_cooldowns: dict[int, datetime] = {}
COOLDOWN_TIME = 300  # 5 minutes


async def kick_member(interaction: discord.Interaction, member: discord.Member, admin_user: discord.Member) -> None:
    try:
        await member.kick(reason=f"Kick approved by {admin_user.display_name}")
        log_request_kick(member.display_name, "Kicked", interaction.user.display_name, admin_user.display_name)
        await interaction.followup.send(
            f"{member.display_name} has been kicked by {admin_user.mention}.",
            ephemeral=True,
        )
        log.info(f"{admin_user.display_name} approved and kicked {member.display_name}.")
    except discord.Forbidden:
        await interaction.followup.send("I don't have permission to kick this user.", ephemeral=True)
        log.error(f"Failed to kick {member.display_name} due to insufficient permissions.")
    except discord.HTTPException as e:
        await interaction.followup.send("An error occurred while kicking the user.", ephemeral=True)
        log.error(f"HTTP Exception while kicking {member.display_name}: {e}")


def register_kick_command(bot: commands.Bot) -> None:
    """
    Registers /kick_request on the provided bot instance.

    IMPORTANT:
    - No global `bot`
    - No global `GUILD_ID`
    - No env access at import time
    """

    @bot.slash_command(name="kick_request", description="Request an admin to kick a member.")
    async def kick_request(ctx: discord.ApplicationContext, member: discord.Member):
        # ctx.interaction is the underlying discord.Interaction
        interaction = ctx.interaction
        await interaction.response.defer()

        user_id = interaction.user.id
        now = datetime.now(timezone.utc)

        # Cooldown check
        if user_id in kick_cooldowns:
            elapsed = (now - kick_cooldowns[user_id]).total_seconds()
            if elapsed < COOLDOWN_TIME:
                await interaction.followup.send(
                    "You must wait before making another kick request.",
                    ephemeral=True,
                )
                return

        kick_cooldowns[user_id] = now

        if interaction.guild is None:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return

        admin_role = discord.utils.get(interaction.guild.roles, name="Admin")
        if not admin_role:
            await interaction.followup.send("No Admin role found in this server.", ephemeral=True)
            return

        admin_channel = discord.utils.get(interaction.guild.text_channels, name="🏢-admin-approval")
        warning_channel = discord.utils.get(interaction.guild.text_channels, name="member-warnings")
        private_admin_channel = discord.utils.get(interaction.guild.text_channels, name="private-admin-approval")

        if not admin_channel:
            await interaction.followup.send("Kick approval channel not found.", ephemeral=True)
            return

        # Try DM the user being kicked; if not possible, warn in warnings channel if available
        try:
            await member.send(
                f"Hey {member.mention}, {interaction.user.mention} has sent a request to {admin_role.mention} "
                f"to kick you from the server. Admins will review this request."
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            log.warning(f"Could not send DM to {member.display_name}: {e}")
            if warning_channel:
                await warning_channel.send(
                    f"{member.mention}, you have been flagged for a kick request by {interaction.user.mention}. "
                    f"An admin will review this request."
                )

        # Notify admins
        admins = [m for m in interaction.guild.members if admin_role in m.roles]
        if not admins:
            await interaction.followup.send("No Admins found to approve the request.", ephemeral=True)
            return

        admin_mentions = ", ".join(a.mention for a in admins)
        approval_message = await admin_channel.send(
            f"{admin_mentions}, {interaction.user.mention} is requesting to kick {member.mention}. "
            f"React with {EMOJI_APPROVE} to approve or {EMOJI_DENY} to deny."
        )
        await approval_message.add_reaction(EMOJI_APPROVE)
        await approval_message.add_reaction(EMOJI_DENY)

        def check(reaction: discord.Reaction, user: discord.User) -> bool:
            return (
                user in admins
                and reaction.message.id == approval_message.id
                and str(reaction.emoji) in [EMOJI_APPROVE, EMOJI_DENY]
            )

        try:
            reaction, admin_user = await bot.wait_for("reaction_add", check=check, timeout=300.0)

            if str(reaction.emoji) == EMOJI_APPROVE:
                # Second confirmation
                confirmation_message = await admin_channel.send(
                    f"{admin_user.mention}, are you sure you want to kick {member.mention}? "
                    f"React with {EMOJI_APPROVE} again to confirm."
                )
                await confirmation_message.add_reaction(EMOJI_APPROVE)

                def check_second(r: discord.Reaction, u: discord.User) -> bool:
                    return (
                        u.id == admin_user.id
                        and r.message.id == confirmation_message.id
                        and str(r.emoji) == EMOJI_APPROVE
                    )

                try:
                    await bot.wait_for("reaction_add", check=check_second, timeout=60.0)
                    # admin_user from wait_for is a User; kick_member expects Member
                    admin_member = interaction.guild.get_member(admin_user.id) or admin_user
                    await kick_member(interaction, member, admin_member)  # type: ignore[arg-type]
                except asyncio.TimeoutError:
                    if private_admin_channel:
                        await private_admin_channel.send(
                            f"{admin_user.mention}, the second confirmation timed out. "
                            f"Kick request for {member.mention} has been cancelled."
                        )
                    else:
                        await admin_channel.send(
                            f"{admin_user.mention}, second confirmation timed out. Kick cancelled."
                        )
            else:
                await interaction.followup.send(
                    f"Kick request for {member.mention} has been denied.",
                    ephemeral=True,
                )
                log.info(f"{admin_user} denied kick request for {member.display_name}.")

        except asyncio.TimeoutError:
            await admin_channel.send("Kick request timed out.")
