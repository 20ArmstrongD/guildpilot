import discord
from discord.ext import commands
import logging
from pathlib import Path
import json
import random
from collections import defaultdict

from .commands.elements.config import (
    build_bot,
    get_config,
    GANG_ROLE_NAME,
    STALLIONS_ROLE_NAME,
)

from .commands.elements.sql_logger import DATABASE_PATH

from .commands import (
    register_promote_command,
    register_demote_command,
    register_kick_command,
)

# -----------------------
# Hard-coded Welcome Channel (INT for API calls)
# Replace this with your channel ID if it changes
WELCOME_CHANNEL_ID = 1307093390114160678
# -----------------------

welcome_sent = set()


def channel_mention(cid: int) -> str:
    """Return a clickable #channel mention string for Discord."""
    return f"<#{cid}>"


def render_template(tpl: str, member: discord.Member, role_assigned: str) -> str:
    """Safely render a welcome template, supporting both {WELCOME_CHANNEL} and {welcome_channel}."""
    values = defaultdict(
        str,
        {
            "member": member.mention,
            "member_name": member.display_name,
            "role": role_assigned,
            "guild_name": member.guild.name,
            "WELCOME_CHANNEL": channel_mention(WELCOME_CHANNEL_ID),
            "welcome_channel": channel_mention(WELCOME_CHANNEL_ID),
        },
    )
    return tpl.format_map(values)


def load_messages(path: Path, json_key: str, fallback_list: list[str]) -> list[str]:
    """Load a list of messages from JSON; gracefully fall back on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        msgs = data.get(json_key)
        if isinstance(msgs, list) and all(isinstance(x, str) for x in msgs):
            return msgs
        logging.warning(f"{path} missing key '{json_key}' or not a list; using fallback.")
    except Exception as e:
        logging.warning(f"Failed to load messages from {path}: {e}")
    return fallback_list


async def load_commands(bot: commands.Bot) -> None:
    register_promote_command(bot)
    register_demote_command(bot)
    register_kick_command(bot)


def main() -> None:
    # Load config at runtime (safe for pytest/CI imports)
    cfg = get_config()

    # Build bot at runtime
    bot = build_bot()

    @bot.event
    async def on_ready():
        logging.info(f"Bot is ready and connected as {bot.user}!")
        logging.info(f"Connected to the SQLite database: {DATABASE_PATH}")

        for guild in bot.guilds:
            logging.info(f"Checking role assignment in guild: {guild.name} (ID: {guild.id})")
            bot_member = guild.me  # py-cord provides .me

            # Find the "The Stallions" role
            stallions_role = discord.utils.get(guild.roles, name=STALLIONS_ROLE_NAME)

            if stallions_role:
                logging.info(f"Found {STALLIONS_ROLE_NAME} role in {guild.name}.")
                if bot_member and stallions_role in bot_member.roles:
                    logging.info(f"Bot already has {STALLIONS_ROLE_NAME} in {guild.name}.")
                else:
                    try:
                        if bot_member:
                            await bot_member.add_roles(stallions_role)
                            logging.info(
                                f"Assigned {STALLIONS_ROLE_NAME} to {bot.user.display_name} in {guild.name}."
                            )
                    except discord.Forbidden:
                        logging.error(
                            f"Insufficient permissions to assign {STALLIONS_ROLE_NAME} in {guild.name}."
                        )
                    except discord.HTTPException as e:
                        logging.error(f"HTTP Exception: {e}")
            else:
                logging.warning(f"{STALLIONS_ROLE_NAME} role not found in {guild.name}.")

    @bot.event
    async def on_member_join(member: discord.Member):
        if member.id in welcome_sent:
            return

        # Resolve roles
        gang_role = discord.utils.get(member.guild.roles, name=GANG_ROLE_NAME)
        stallions_role = discord.utils.get(member.guild.roles, name=STALLIONS_ROLE_NAME)

        role_assigned = "No specific role assigned."
        welcome_message = None

        # Ensure we can send to the hard-coded channel
        channel = member.guild.get_channel(WELCOME_CHANNEL_ID) or bot.get_channel(WELCOME_CHANNEL_ID)
        if channel is None:
            logging.error(f"Welcome channel id {WELCOME_CHANNEL_ID} not found in guild {member.guild.id}.")
            return

        # Paths to message JSON (you may want to make these relative later)
        welc_msg_bot_path = Path("/home/bot-vm/code/guildpilot/modules/rolecop/messages/welc_msg_bots.json")
        welc_msg_memb_path = Path("/home/bot-vm/code/guildpilot/modules/rolecop/messages/welc_msg_membs.json")

        # Fallback messages
        DEFAULT_BOT_MSGS = [
            "A new bot {member} just joined. Assigned role: {role}. Say hi in {WELCOME_CHANNEL}.",
            "Heads up: {member} is here. Check permissions and post in {welcome_channel}. Role set to {role}.",
        ]
        DEFAULT_MEMBER_MSGS = [
            "Welcome {member} to {guild_name}! You’ve been added to {role}. Chat in {WELCOME_CHANNEL} 🎉",
            "Glad you’re here {member}! You’re now in {role}. Start in {welcome_channel}.",
        ]

        if member.bot and stallions_role:
            await member.add_roles(stallions_role)
            role_assigned = stallions_role.name
            logging.info(f"Assigned {STALLIONS_ROLE_NAME} role to bot {member.display_name}.")

            bot_msgs = load_messages(welc_msg_bot_path, "WELCOME_MESSAGES_BOTS", DEFAULT_BOT_MSGS)
            selected_message = random.choice(bot_msgs)
            welcome_message = render_template(selected_message, member, role_assigned)

        elif gang_role:
            await member.add_roles(gang_role)
            role_assigned = gang_role.name
            logging.info(f"Assigned {GANG_ROLE_NAME} role to {member.display_name}.")

            memb_msgs = load_messages(welc_msg_memb_path, "WELCOME_MESSAGES_MEMBERS", DEFAULT_MEMBER_MSGS)
            selected_message = random.choice(memb_msgs)
            welcome_message = render_template(selected_message, member, role_assigned)

        else:
            logging.warning(f"No specific role assigned to {member.display_name}.")

        # Send the welcome message (only if we have one)
        if welcome_message:
            try:
                await channel.send(welcome_message)
                welcome_sent.add(member.id)
            except discord.HTTPException as e:
                logging.error(f"Failed to send welcome message: {e}")

    @bot.event
    async def on_connect():
        logging.info("Bot connected to Discord API.")
        await load_commands(bot)

        # If you're using app commands / tree sync, keep this.
        # If your bot uses only prefix commands, you can remove this block.
        try:
            registered_commands = await bot.tree.sync(guild=discord.Object(id=cfg.guild_id))
            logging.info(f"Slash commands registered: {', '.join([cmd.name for cmd in registered_commands])}")
        except Exception as e:
            logging.error(f"failed to sync commands: {e}")

    bot.run(cfg.token)


if __name__ == "__main__":
    main()
