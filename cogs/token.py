import discord, requests
from discord.ext import commands
from discord import app_commands
from config import EMBED_COLOR

class Token(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="token", description="Get token info")
    async def token(self, interaction, uid: str, password: str):
        await interaction.response.defer(ephemeral=True)

        try:
            url = f"https://info.killersharmabot.online/token?uid={uid}&password={password}"
            data = requests.get(url).json()

            embed = discord.Embed(title="🔑 Token Info", color=EMBED_COLOR)
            embed.add_field(name="UID", value=uid)
            embed.add_field(name="Nickname", value=data.get("nickname", "N/A"))
            embed.add_field(name="Region", value=data.get("notiRegion", "N/A"))

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Token(bot))