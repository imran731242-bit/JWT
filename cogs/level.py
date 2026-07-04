import discord, requests
from discord.ext import commands
from discord import app_commands
from config import EMBED_COLOR

class Level(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="level", description="Check player level")
    async def level(self, interaction, uid: str):
        await interaction.response.defer()

        data = requests.get(f"https://info.killersharmabot.online/level?uid={uid}").json()
        p = data.get("data", data)

        embed = discord.Embed(title="⭐ Level Info", color=EMBED_COLOR)
        embed.add_field(name="UID", value=uid)
        embed.add_field(name="Level", value=str(p.get("level", "N/A")))
        embed.add_field(name="EXP", value=str(p.get("exp", "N/A")))

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Level(bot))