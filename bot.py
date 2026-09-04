import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("PREFIX", "!")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=commands.DefaultHelpCommand())

INITIAL_EXTENSIONS = [
    "cogs.moderation",
    "cogs.fun",
    "cogs.economy",
    "cogs.music",
]


@bot.event
async def on_ready():
    print(f"✅ Συνδέθηκε ως {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Sync {len(synced)} slash commands")
    except Exception as e:
        print(f"⚠️ Σφάλμα στο sync: {e}")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help | /help"))


async def main():
    async with bot:
        for ext in INITIAL_EXTENSIONS:
            try:
                await bot.load_extension(ext)
                print(f"📦 Φορτώθηκε: {ext}")
            except Exception as e:
                print(f"❌ Αποτυχία φόρτωσης {ext}: {e}")
        await bot.start(TOKEN)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌ Δεν βρέθηκε DISCORD_TOKEN. Βάλε το στο .env ή στα Railway variables.")
    asyncio.run(main())
