import discord
from discord.ext import commands


intent = discord.Intents.default()
intent.message_content = True
intent.members = True

# Create an instance of Bot for slash commands
botstuff = commands.Bot(command_prefix="!", intents=intent)
