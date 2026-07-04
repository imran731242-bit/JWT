import discord, requests
from discord.ext import commands
from discord import app_commands
from io import BytesIO

class Banner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="banner", description="Get banner")
    async def banner(self, interaction, region: str, uid: str):
        await interaction.response.defer()

        url = f"https://ffavtarbanner.vercel.app/avatar-banner?uid={uid}&region={region}"
        res = requests.get(url)

        file = discord.File(BytesIO(res.content), filename="banner.webp")
        await interaction.followup.send(file=file)

async def setup(bot):
    await bot.add_cog(Banner(bot))