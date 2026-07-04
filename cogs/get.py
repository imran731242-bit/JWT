import discord, requests
from discord.ext import commands
from discord import app_commands
from config import EMBED_COLOR

class Get(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="get", description="Get player info")
    async def get(self, interaction, uid: str):
        await interaction.response.defer()

        data = requests.get(f"https://info.killersharmabot.online/player-info?uid={uid}").json()
        basic = data.get("basicInfo", {})

        embed = discord.Embed(title="🎮 Player Info", color=EMBED_COLOR)
        embed.add_field(name="Name", value=basic.get("nickname", "N/A"))
        embed.add_field(name="UID", value=uid)
        embed.add_field(name="Level", value=str(basic.get("level", "N/A")))
        embed.add_field(name="Region", value=basic.get("region", "N/A"))
        embed.add_field(name="Likes", value=str(basic.get("liked", "N/A")))

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Get(bot))