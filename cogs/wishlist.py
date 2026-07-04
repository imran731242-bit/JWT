import discord, requests
from discord.ext import commands
from discord import app_commands
from config import EMBED_COLOR

class Wishlist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="wishlist", description="Get wishlist")
    async def wishlist(self, interaction, uid: str):
        await interaction.response.defer()

        data = requests.get(
            f"https://info.killersharmabot.online/wishlist?uid={uid}"
        ).json()

        wishlist = data.get("wishlist", [])
        if not wishlist:
            await interaction.followup.send("❌ Wishlist not found")
            return

        embed = discord.Embed(title="🎁 Wishlist", color=EMBED_COLOR)
        embed.description = f"Total Items: {len(wishlist)}"

        await interaction.followup.send(embed=embed)

        for item in wishlist:
            name = item.get("name", "Unknown")
            image = item.get("item_image_link")
            if image:
                await interaction.followup.send(image)

async def setup(bot):
    await bot.add_cog(Wishlist(bot))