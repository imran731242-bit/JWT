import discord
from discord.ext import commands
from config import TOKEN

intents = discord.Intents.default()
bot = commands.Bot(command_prefix=!, intents=intents)

COGS = [
    cogs.get,
    cogs.wishlist,
    cogs.region,
    cogs.level,
    cogs.bancheck,
    cogs.token,
    cogs.banner,
    cogs.outfit,
    cogs.events
]

@bot.event
async def on_ready()
    print(fLogged in as {bot.user})

    try
        synced = await bot.tree.sync()
        print(fSynced {len(synced)} commands)
    except Exception as e
        print(e)

async def load_extensions()
    for cog in COGS
        try
            await bot.load_extension(cog)
            print(fLoaded {cog})
        except Exception as e
            print(fFailed {cog} {e})

async def main()
    async with bot
        await load_extensions()
        await bot.start(TOKEN)

import asyncio
asyncio.run(main())