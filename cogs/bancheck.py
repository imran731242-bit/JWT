import discord
from discord import app_commands
from discord.ext import commands
import requests
from config import EMBED_COLOR
from utils.api import BAN_CHECK

class BanCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="bancheck", description="Check player ban status")
    async def bancheck(self, interaction: discord.Interaction, uid: str):
        await interaction.response.defer()

        try:
            res = requests.get(BAN_CHECK.format(uid=uid), timeout=100)

            if res.status_code != 200:
                await interaction.followup.send("❌ API Error")
                return

            data = res.json()

            embed = discord.Embed(
                title="🔨 Ban Check Result",
                color=EMBED_COLOR
            )

            embed.add_field(name="UID", value=uid, inline=False)
            embed.add_field(name="Name", value=data.get("name", "Not Found"))
            embed.add_field(name="Region", value=data.get("region", "Not Found"))
            embed.add_field(name="Status", value=data.get("ban_status", "Not Found"))

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}")

async def setup(bot):
    await bot.add_cog(BanCheck(bot))