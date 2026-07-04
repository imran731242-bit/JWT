import discord, requests
from discord.ext import commands
from discord import app_commands

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="events", description="Get region events")
    async def events(self, interaction, region: str):
        await interaction.response.defer()

        data = requests.get(
            f"https://flash-by-events.vercel.app/events?region={region}&key=Flash"
        ).json()

        items = data.get("events", {}).get("items", [])
        if not items:
            await interaction.followup.send("❌ No events found")
            return

        for item in items:
            banner = item.get("Banner")
            if banner:
                await interaction.followup.send(banner)

async def setup(bot):
    await bot.add_cog(Events(bot))