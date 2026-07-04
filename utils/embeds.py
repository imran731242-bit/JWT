import discord
from config import EMBED_COLOR, BOT_NAME

def base_embed(title):
    embed = discord.Embed(title=title, color=EMBED_COLOR)
    embed.set_footer(text=BOT_NAME)
    return embed