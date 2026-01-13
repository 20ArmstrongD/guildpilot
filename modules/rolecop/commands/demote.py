import discord 
from discord.ext import commands
import logging
from .elements import (
    EMOJI_APPROVE,
    EMOJI_DENY
)


# Initialize bot with intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True  


# Function to demote a member
async def demote_member(interaction, member, role):
    try:
        await member.remove_roles(role)
        await interaction.followup.send(f"{member.display_name} has been demoted from {role.name}.", ephemeral=True)
            # Log the demotion request
        logging.INFO(interaction.user.display_name, f"Demoted {member.display_name} from {role.name}", True, interaction.user.display_name)
        
        # Log the demotion request
        logging.INFO(interaction.user.display_name, f"Demoted {member.display_name} from {role.name}", True, interaction.user.display_name)

    except discord.Forbidden:
        await interaction.followup.send(f"Insufficient permissions to demote {member.display_name}.", ephemeral=True)
        # Optionally log the error
        logging.error(f"Failed to demote {member.display_name} from {role.name} due to insufficient permissions.")

    except discord.HTTPException as e:
        await interaction.followup.send(f"An error occurred while demoting {member.display_name}.", ephemeral=True)
        # Optionally log the error
        logging.error(f"HTTP Exception while demoting {member.display_name} from {role.name}: {e}")


def register_demote_command(bot: commands.Bot) -> None:
    get_config()
    # Slash command: Demote a member
    @bot.tree.command(guild=discord.Object(id=GUILD_ID), name="demote", description="Request to demote a <member> from <role>")
    async def demote(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        await interaction.response.defer()
        admin_role = discord.utils.get(interaction.guild.roles, name="Admin")

        # Check if the user is an admin
        if admin_role in interaction.user.roles:
            await demote_member(interaction, member, role)
            logging.info(f'{interaction.user.display_name} aka: Admin just demoted {member.display_name} from {role.name}.')
            logging.INFO(interaction.user.display_name, f"just demoted {member.display_name} from {role.name}", True, interaction.user.display_name)
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
                            f"{admin_mentions}, {interaction.user.mention} is requesting to demote {member.display_name} from {role.name}. "
                            f"React with {EMOJI_APPROVE} to approve or {EMOJI_DENY} to deny."
                        )

                        def check(reaction, user):
                            return user in admins and reaction.message.id == approval_message.id and str(reaction.emoji) in [EMOJI_APPROVE, EMOJI_DENY]

                        # Wait for a reaction from admins
                        reaction, user = await bot.wait_for('reaction_add', check=check)

                        if str(reaction.emoji) == EMOJI_APPROVE:
                            await demote_member(interaction, member, role)
                            logging.info(f'{user.display_name} approved demotion of {member.display_name} from {role.name}.')
                            logging.INFO(user.display_name, f"Approved demotion of {member.display_name} from {role.name}", True, user.display_name)
                        else:
                            await interaction.followup.send(f"Demotion of {member.display_name} from {role.name} has been denied.", ephemeral=True)
                            logging.info(f'{user.display_name} denied demotion of {member.display_name} from {role.name}.')
                            logging.INFO(user.display_name, f"Denied demotion of {member.display_name} from {role.name}", False, user.display_name)
                    except Exception as e:
                        logging.error(f"Error sending approval message: {e}")
                        await interaction.followup.send("There was an error processing the approval request.", ephemeral=True)
                else:
                    await interaction.followup.send("Could not find the paddys-pub channel.", ephemeral=True)
            else:
                await interaction.followup.send("No Admins found to approve the request.", ephemeral=True)