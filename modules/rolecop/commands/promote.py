import discord
from discord.ext import commands
import logging

from .elements import (
    EMOJI_APPROVE,
    EMOJI_DENY,
    #log_request_promote_demote,
)



# Function to promote a member
async def promote_member(interaction, member, role):
    await member.add_roles(role)
    await interaction.followup.send(f"{member.display_name} has been promoted to {role.name}.", ephemeral=True)
    
    # Log the promotion request
    log_request_promote_demote(interaction.user.display_name, f"Promoted {member.display_name} to {role.name}", True, interaction.user.display_name)


def register_promote_command(bot):
    cfg = get_config()
    # Slash command: Promote a member
    @bot.tree.command(guild=discord.Object(id=GUILD_ID), name="promote", description="Request to promote a <member> from a <role>")
    async def promote(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        await interaction.response.defer()
        admin_role = discord.utils.get(interaction.guild.roles, name="Admin")

        # Check if the user is an admin
        if admin_role in interaction.user.roles:
            await promote_member(interaction, member, role)
            logging.info(f'{interaction.user.display_name} aka: Admin promoted {member.display_name} to {role.name}.')
            log_request_promote_demote(interaction.user.display_name, f"Promoted {member.display_name} to {role.name}", True, interaction.user.display_name)
        else:
            # Notify admins for approval
            admins = [admin for admin in interaction.guild.members if admin_role in admin.roles]
            if admins:
                admin_mentions = ', '.join(admin.mention for admin in admins)

                # Send the approval request message to the paddys-pub channel
                general_channel = discord.utils.get(interaction.guild.text_channels, name="🏢-admin-approval")
                if general_channel:
                    try:
                        approval_message = await general_channel.send(
                            f"{admin_mentions}, {interaction.user.mention} is requesting to promote {member.display_name} to {role.name}. "
                            f"React with {EMOJI_APPROVE} to approve or {EMOJI_DENY} to deny."
                        )

                        def check(reaction, user):
                            return user in admins and reaction.message.id == approval_message.id and str(reaction.emoji) in [EMOJI_APPROVE, EMOJI_DENY]

                        # Wait for a reaction from admins
                        reaction, user = await bot.wait_for('reaction_add', check=check)

                        if str(reaction.emoji) == EMOJI_APPROVE:
                            await promote_member(interaction, member, role)
                            logging.info(f'{user.display_name} approved promotion of {member.display_name} to {role.name}.')
                            log_request_promote_demote(user.display_name, f"Approved promotion of {member.display_name} to {role.name}", True, user.display_name)
                        else:
                            await interaction.followup.send(f"Promotion of {member.display_name} to {role.name} has been denied.", ephemeral=True)
                            logging.info(f'{user.display_name} denied promotion of {member.display_name} to {role.name}.')
                            log_request_promote_demote(user.display_name, f"Denied promotion of {member.display_name} to {role.name}", False, user.display_name)
                    except Exception as e:
                        logging.error(f"Error sending approval message: {e}")
                        await interaction.followup.send("There was an error processing the approval request.", ephemeral=True)
                else:
                    await interaction.followup.send("Could not find the paddys-pub channel.", ephemeral=True)
            else:
                await interaction.followup.send("No Admins found to approve the request.", ephemeral=True)