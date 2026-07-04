import discord, requests
from discord.ext import commands
from discord import app_commands
from io import BytesIO

class Outfit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="outfit", description="Get outfit image")
    async def outfit(self, interaction, uid: str):
        await interaction.response.defer()

        url = f"https://outfit-api-by-ajay.vercel.app/outfit-image?uid={uid}&key=AJAY"
        res = requests.get(url)

        file = discord.File(BytesIO(res.content), filename="outfit.jpg")
        await interaction.followup.send(file=file)

async def setup(bot):
    await bot.add_cog(Outfit(bot))