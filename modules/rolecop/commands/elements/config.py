import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Fix the path: use the actual folder name where your .env lives
dotenv_path='/home/DiscordPi/code/discord_bots/memb-assign-bot/src/.env'

load_dotenv()
# Read env vars (case-sensitive!)
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')
WELCOME_CHANNEL = os.getenv('WELCOME_CHANNEL')  # channel ID as string in .env

# Paths to your welcome message JSON files (match your .env keys)
# Example .env:
# WELCOME_MEMBER_MESSAGES=/abs/path/to/welcome_members.json
# WELCOME_BOT_MESSAGES=/abs/path/to/welcome_bots.json
welc_msg_memb_path = os.getenv('WELCOME_MEMBER_MESSAGES')  # messages for *members*
welc_msg_bot_path  = os.getenv('WELCOME_BOT_MESSAGES')     # messages for *bots*

# Validate critical vars
if not TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN is not set in the .env file.")
if not GUILD_ID:
    raise ValueError("GUILD_ID is not set in the .env file.")
if not WELCOME_CHANNEL:
    raise ValueError("WELCOME_CHANNEL is not set in the .env file.")

# Cast IDs
GUILD_ID = int(GUILD_ID)


# Initialize bot with intents (ensure these are enabled in the portal)
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Role names / emojis
GANG_ROLE_NAME = "Gang Members"
STALLIONS_ROLE_NAME = "The Stallions"
BOTS_ROLE_NAME = "Bots"
EMOJI_APPROVE = "✅"
EMOJI_DENY = "❌"

# Optional: quick sanity log
logging.info(f"GUILD_ID={GUILD_ID}, WELCOME_CHANNEL={WELCOME_CHANNEL}")
logging.info(f"welc_msg_memb_path={welc_msg_memb_path}")
logging.info(f"welc_msg_bot_path={welc_msg_bot_path}")
