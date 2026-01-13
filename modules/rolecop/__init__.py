from discord.ext import commands

from .cog import RoleCopCog


def setup(bot: commands.Bot):
    bot.add_cog(RoleCopCog(bot))
