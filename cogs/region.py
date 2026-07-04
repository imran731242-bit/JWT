import discord, requests
from discord.ext import commands
from discord import app_commands
from config import EMBED_COLOR

class Region(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="region", description="Check player region")
    async def region(self, interaction: discord.Interaction, uid: str):
        await interaction.response.defer()

        try:
            url = f"https://region-check-api-by-ajay-k3ax.vercel.app/region?uid={uid}"
            res = requests.get(url).json()

            embed = discord.Embed(title="🌍 Region Info", color=EMBED_COLOR)
            embed.add_field(name="UID", value=uid)
            embed.add_field(name="Nickname", value=res.get("nickname", "Not Found"))
            embed.add_field(name="Region", value=res.get("region_name", "Not Found"))

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}")

async def setup(bot):
    await bot.add_cog(Region(bot))