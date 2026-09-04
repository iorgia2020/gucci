import os
import time
import random
import sqlite3
import asyncio
import datetime
import collections

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import yt_dlp

# ============================================================
#  ΡΥΘΜΙΣΕΙΣ / SETUP
# ============================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("PREFIX", "!")
DB_PATH = os.path.join(os.path.dirname(__file__), "economy.db")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.invites = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=commands.DefaultHelpCommand())


# Γενικός error handler για ΟΛΕΣ τις slash commands (καλύπτει και όσες
# δεν έχουν δικό τους @command.error, π.χ. kick/ban/mute/warn/clear/slowmode)
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        msg = "❌ Δεν έχεις τα απαραίτητα δικαιώματα για αυτή την εντολή."
    elif isinstance(error, app_commands.errors.BotMissingPermissions):
        msg = "❌ Δεν έχω τα απαραίτητα δικαιώματα για να εκτελέσω αυτή την εντολή."
    elif isinstance(error, app_commands.errors.CommandOnCooldown):
        msg = f"⏳ Δοκίμασε ξανά σε {error.retry_after:.1f}s."
    else:
        msg = f"⚠️ Κάτι πήγε στραβά: {error}"
        print(f"Unhandled app command error: {error!r}")

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        pass


# ============================================================
#  ECONOMY / LEVELS — DB HELPERS
# ============================================================

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            last_daily REAL DEFAULT 0,
            last_work REAL DEFAULT 0,
            last_xp_gain REAL DEFAULT 0,
            invites INTEGER DEFAULT 0
        )
    """)
    # Προσθήκη της στήλης invites αν λείπει από παλιότερη βάση
    cols = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "invites" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN invites INTEGER DEFAULT 0")
        conn.commit()
    return conn


def get_user(conn, user_id):
    cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row is None:
        conn.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return (user_id, 0, 0, 1, 0, 0, 0, 0)
    return row


def xp_for_level(level: int) -> int:
    return 5 * (level ** 2) + 50 * level + 100


# ============================================================
#  MODERATION
# ============================================================

warns_store = {}


@bot.tree.command(name="kick", description="Κάνει kick έναν χρήστη")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Δεν δόθηκε λόγος"):
    await member.kick(reason=reason)
    embed = discord.Embed(
        title="👢 Kick",
        description=f"Ο/Η {member.mention} έφυγε από τον server.\n**Λόγος:** {reason}",
        color=discord.Color.orange(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ban", description="Κάνει ban έναν χρήστη")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Δεν δόθηκε λόγος"):
    await member.ban(reason=reason)
    embed = discord.Embed(
        title="🔨 Ban",
        description=f"Ο/Η {member.mention} έφαγε ban.\n**Λόγος:** {reason}",
        color=discord.Color.red(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="unban", description="Κάνει unban έναν χρήστη (με user ID)")
@app_commands.checks.has_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"✅ Έγινε unban ο/η **{user}**.")
    except Exception:
        await interaction.response.send_message("❌ Δεν βρέθηκε χρήστης με αυτό το ID.", ephemeral=True)


@bot.tree.command(name="mute", description="Κάνει timeout έναν χρήστη (σε λεπτά)")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "Δεν δόθηκε λόγος"):
    if minutes <= 0 or minutes > 40320:  # Discord's max timeout είναι 28 μέρες
        await interaction.response.send_message(
            "❌ Η διάρκεια πρέπει να είναι μεταξύ 1 και 40320 λεπτών (28 ημέρες).", ephemeral=True
        )
        return
    duration = datetime.timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    embed = discord.Embed(
        title="🔇 Mute",
        description=f"Ο/Η {member.mention} σιώπησε για **{minutes} λεπτά**.\n**Λόγος:** {reason}",
        color=discord.Color.dark_grey(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="unmute", description="Αφαιρεί το timeout από έναν χρήστη")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(f"🔊 Ο/Η {member.mention} μπορεί να μιλήσει ξανά.")


@bot.tree.command(name="warn", description="Δίνει προειδοποίηση σε χρήστη")
@app_commands.checks.has_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Δεν δόθηκε λόγος"):
    warns_store.setdefault(member.id, []).append(reason)
    count = len(warns_store[member.id])
    embed = discord.Embed(
        title="⚠️ Προειδοποίηση",
        description=f"Ο/Η {member.mention} πήρε προειδοποίηση.\n**Λόγος:** {reason}\n**Σύνολο:** {count}",
        color=discord.Color.yellow(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="warnings", description="Δείχνει τις προειδοποιήσεις ενός χρήστη")
async def warnings_cmd(interaction: discord.Interaction, member: discord.Member):
    user_warns = warns_store.get(member.id, [])
    if not user_warns:
        await interaction.response.send_message(f"Ο/Η {member.mention} δεν έχει προειδοποιήσεις.")
        return
    text = "\n".join(f"{i+1}. {w}" for i, w in enumerate(user_warns))
    await interaction.response.send_message(f"**Προειδοποιήσεις για {member.mention}:**\n{text}")


@bot.tree.command(name="clear", description="Διαγράφει μηνύματα από το κανάλι")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Διαγράφηκαν {len(deleted)} μηνύματα.", ephemeral=True)


@bot.tree.command(name="slowmode", description="Ορίζει slowmode στο κανάλι (σε δευτερόλεπτα)")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, seconds: int):
    if seconds < 0 or seconds > 21600:
        await interaction.response.send_message(
            "❌ Το slowmode πρέπει να είναι μεταξύ 0 και 21600 δευτερολέπτων (6 ώρες).", ephemeral=True
        )
        return
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"🐌 Slowmode ορίστηκε στα {seconds} δευτερόλεπτα.")


# ============================================================
#  ANNOUNCE
# ============================================================

COLOR_CHOICES = {
    "μπλε": discord.Color.blue(),
    "κόκκινο": discord.Color.red(),
    "πράσινο": discord.Color.green(),
    "χρυσό": discord.Color.gold(),
    "μοβ": discord.Color.purple(),
}


@bot.tree.command(name="announce", description="Στέλνει ένα embed announcement σε κανάλι της επιλογής σου")
@app_commands.describe(
    title="Ο τίτλος του announcement",
    message="Το κυρίως κείμενο. Χρησιμοποίησε '\\n' για νέα γραμμή.",
    channel="Το κανάλι όπου θα σταλεί (προεπιλογή: το τρέχον κανάλι)",
    color="Χρώμα του πλαϊνού περιθωρίου του embed",
    image_url="Προαιρετικό: link εικόνας",
)
@app_commands.choices(color=[app_commands.Choice(name=n, value=n) for n in COLOR_CHOICES.keys()])
@app_commands.checks.has_permissions(manage_guild=True)
async def announce(
    interaction: discord.Interaction,
    title: str,
    message: str,
    channel: discord.TextChannel = None,
    color: app_commands.Choice[str] = None,
    image_url: str = None,
):
    target_channel = channel or interaction.channel
    chosen_color = COLOR_CHOICES.get(color.value, discord.Color.blue()) if color else discord.Color.blue()
    formatted_message = message.replace("\\n", "\n")

    embed = discord.Embed(title=title, description=formatted_message, color=chosen_color)
    embed.set_footer(text=f"Announcement από {interaction.user.display_name}")
    if image_url:
        embed.set_image(url=image_url)

    try:
        await target_channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Στάλθηκε στο {target_channel.mention}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Δεν έχω δικαίωμα να στείλω μήνυμα σε αυτό το κανάλι.", ephemeral=True)


@announce.error
async def announce_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ Χρειάζεσαι δικαίωμα 'Manage Server' για αυτή την εντολή.", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ Σφάλμα: {error}", ephemeral=True)


@bot.tree.command(name="sendmessage", description="Στέλνει απλό κείμενο (όχι embed) σε κανάλι της επιλογής σου")
@app_commands.describe(
    channel="Το κανάλι όπου θα σταλεί το μήνυμα",
    message="Το κείμενο που θα στείλει το bot. Χρησιμοποίησε '\\n' για νέα γραμμή.",
)
@app_commands.checks.has_permissions(manage_guild=True)
async def sendmessage(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    formatted_message = message.replace("\\n", "\n")
    try:
        await channel.send(formatted_message)
        await interaction.response.send_message(f"✅ Στάλθηκε στο {channel.mention}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Δεν έχω δικαίωμα να στείλω μήνυμα σε αυτό το κανάλι.", ephemeral=True)


@sendmessage.error
async def sendmessage_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ Χρειάζεσαι δικαίωμα 'Manage Server' για αυτή την εντολή.", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ Σφάλμα: {error}", ephemeral=True)


# ============================================================
#  FUN
# ============================================================

EIGHTBALL_ANSWERS = [
    "Ναι, σίγουρα.", "Μάλλον ναι.", "Δεν είμαι σίγουρος, ρώτα ξανά.",
    "Δεν το βλέπω καλό.", "Όχι.", "Σίγουρα όχι.", "Ρώτα με αργότερα.",
    "Οι πηγές λένε ναι.", "Απίθανο.", "100% ναι!",
]

JOKES = [
    "Γιατί ο προγραμματιστής μπερδεύει το Halloween με τα Χριστούγεννα; Γιατί OCT 31 == DEC 25.",
    "Πόσοι προγραμματιστές χρειάζονται για να αλλάξουν μια λάμπα; Κανένας, είναι hardware πρόβλημα.",
    "Ο κώδικάς μου δεν έχει bugs, έχει απρόβλεπτα features.",
]


@bot.tree.command(name="8ball", description="Ρώτα τη μαγική μπάλα")
async def eightball(interaction: discord.Interaction, question: str):
    answer = random.choice(EIGHTBALL_ANSWERS)
    embed = discord.Embed(title="🎱 Magic 8-Ball", color=discord.Color.purple())
    embed.add_field(name="Ερώτηση", value=question, inline=False)
    embed.add_field(name="Απάντηση", value=answer, inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="coinflip", description="Ρίχνει ένα νόμισμα")
async def coinflip(interaction: discord.Interaction):
    result = random.choice(["Κορώνα 🪙", "Γράμματα 🪙"])
    await interaction.response.send_message(f"Το νόμισμα έδειξε: **{result}**")


@bot.tree.command(name="dice", description="Ρίχνει ζάρι (1-6 ή custom πλευρές)")
async def dice(interaction: discord.Interaction, sides: int = 6):
    result = random.randint(1, sides)
    await interaction.response.send_message(f"🎲 Έριξες: **{result}** (από 1 έως {sides})")


@bot.tree.command(name="meme", description="Στέλνει ένα τυχαίο joke/meme κείμενο")
async def meme(interaction: discord.Interaction):
    await interaction.response.send_message(random.choice(JOKES))


@bot.tree.command(name="rps", description="Παίξε πέτρα-ψαλίδι-χαρτί με το bot")
@app_commands.choices(choice=[
    app_commands.Choice(name="Πέτρα", value="rock"),
    app_commands.Choice(name="Ψαλίδι", value="scissors"),
    app_commands.Choice(name="Χαρτί", value="paper"),
])
async def rps(interaction: discord.Interaction, choice: app_commands.Choice[str]):
    options = ["rock", "scissors", "paper"]
    bot_choice = random.choice(options)
    user_choice = choice.value

    if user_choice == bot_choice:
        result = "🤝 Ισοπαλία!"
    elif (
        (user_choice == "rock" and bot_choice == "scissors")
        or (user_choice == "scissors" and bot_choice == "paper")
        or (user_choice == "paper" and bot_choice == "rock")
    ):
        result = "🎉 Κέρδισες!"
    else:
        result = "🤖 Κέρδισε το bot!"

    names = {"rock": "Πέτρα", "scissors": "Ψαλίδι", "paper": "Χαρτί"}
    await interaction.response.send_message(f"Εσύ: **{names[user_choice]}** | Bot: **{names[bot_choice]}**\n{result}")


@bot.tree.command(name="avatar", description="Δείχνει το avatar ενός χρήστη")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"Avatar του {member.display_name}", color=discord.Color.blue())
    embed.set_image(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)


# ============================================================
#  ECONOMY & LEVELS
# ============================================================

@bot.event
async def on_message(message: discord.Message):
    # Χρειάζεται για να δουλεύει και το XP gain, αλλά και τα prefix commands (αν προστεθούν)
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    conn = get_conn()
    row = get_user(conn, message.author.id)
    _, balance, xp, level, last_daily, last_work, last_xp_gain, _invites = row
    now = time.time()
    if now - last_xp_gain >= 60:
        gained = random.randint(5, 15)
        xp += gained
        needed = xp_for_level(level)
        leveled_up = False
        while xp >= needed:
            xp -= needed
            level += 1
            leveled_up = True
            needed = xp_for_level(level)
        conn.execute(
            "UPDATE users SET xp=?, level=?, last_xp_gain=? WHERE user_id=?",
            (xp, level, now, message.author.id),
        )
        conn.commit()
        if leveled_up:
            try:
                await message.channel.send(f"🎉 Συγχαρητήρια {message.author.mention}, ανέβηκες στο **level {level}**!")
            except discord.Forbidden:
                pass
    conn.close()
    await bot.process_commands(message)


@bot.tree.command(name="balance", description="Δείχνει το υπόλοιπό σου")
async def balance(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    conn = get_conn()
    row = get_user(conn, member.id)
    conn.close()
    embed = discord.Embed(title=f"💰 Πορτοφόλι του {member.display_name}", color=discord.Color.gold())
    embed.add_field(name="Υπόλοιπο", value=f"{row[1]} coins")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="daily", description="Μάζεψε το ημερήσιο bonus σου")
async def daily(interaction: discord.Interaction):
    conn = get_conn()
    row = get_user(conn, interaction.user.id)
    now = time.time()
    last_daily = row[4]
    if now - last_daily < 86400:
        remaining = int(86400 - (now - last_daily))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await interaction.response.send_message(
            f"⏳ Πρέπει να περιμένεις ακόμα {hours}ώ {minutes}λ για το επόμενο daily.", ephemeral=True
        )
        conn.close()
        return
    amount = random.randint(100, 300)
    new_balance = row[1] + amount
    conn.execute("UPDATE users SET balance=?, last_daily=? WHERE user_id=?", (new_balance, now, interaction.user.id))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"🎁 Πήρες **{amount} coins**! Νέο υπόλοιπο: {new_balance}")


@bot.tree.command(name="work", description="Δούλεψε για να κερδίσεις coins")
async def work(interaction: discord.Interaction):
    conn = get_conn()
    row = get_user(conn, interaction.user.id)
    now = time.time()
    last_work = row[5]
    if now - last_work < 3600:
        remaining = int(3600 - (now - last_work))
        minutes = remaining // 60
        await interaction.response.send_message(f"⏳ Κουράστηκες! Ξαναδοκίμασε σε {minutes} λεπτά.", ephemeral=True)
        conn.close()
        return
    amount = random.randint(20, 80)
    new_balance = row[1] + amount
    conn.execute("UPDATE users SET balance=?, last_work=? WHERE user_id=?", (new_balance, now, interaction.user.id))
    conn.commit()
    conn.close()
    jobs = ["πλασιέ", "delivery", "streamer", "μπάρμαν", "dev freelancer"]
    job = random.choice(jobs)
    await interaction.response.send_message(f"💼 Δούλεψες ως **{job}** και κέρδισες **{amount} coins**!")


@bot.tree.command(name="give", description="Δώσε coins σε άλλο χρήστη")
async def give(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Το ποσό πρέπει να είναι θετικό.", ephemeral=True)
        return
    if member.id == interaction.user.id:
        await interaction.response.send_message("❌ Δεν μπορείς να στείλεις coins στον εαυτό σου.", ephemeral=True)
        return
    if member.bot:
        await interaction.response.send_message("❌ Δεν μπορείς να στείλεις coins σε bot.", ephemeral=True)
        return
    conn = get_conn()
    sender = get_user(conn, interaction.user.id)
    if sender[1] < amount:
        await interaction.response.send_message("❌ Δεν έχεις αρκετά coins.", ephemeral=True)
        conn.close()
        return
    get_user(conn, member.id)
    conn.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, interaction.user.id))
    conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, member.id))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"✅ Έστειλες **{amount} coins** στον/στην {member.mention}!")


@bot.tree.command(name="level", description="Δείχνει το level και XP σου")
async def level_cmd(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    conn = get_conn()
    row = get_user(conn, member.id)
    conn.close()
    needed = xp_for_level(row[3])
    embed = discord.Embed(title=f"📊 Level του {member.display_name}", color=discord.Color.green())
    embed.add_field(name="Level", value=row[3])
    embed.add_field(name="XP", value=f"{row[2]} / {needed}")
    await interaction.response.send_message(embed=embed)


leaderboard_group = app_commands.Group(name="leaderboard", description="Leaderboards του server")


@leaderboard_group.command(name="coins", description="Δείχνει το leaderboard του server (coins)")
async def leaderboard_coins(interaction: discord.Interaction):
    conn = get_conn()
    cur = conn.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await interaction.response.send_message("Δεν υπάρχουν δεδομένα ακόμα.")
        return
    lines = []
    for i, (user_id, balance_) in enumerate(rows, 1):
        user = interaction.guild.get_member(user_id)
        name = user.display_name if user else f"Χρήστης {user_id}"
        lines.append(f"**{i}.** {name} — {balance_} coins")
    embed = discord.Embed(title="🏆 Leaderboard (Coins)", description="\n".join(lines), color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)


# ============================================================
#  MUSIC
# ============================================================

YTDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}
FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)


class Song:
    def __init__(self, title, url, stream_url, requester):
        self.title = title
        self.url = url
        self.stream_url = stream_url
        self.requester = requester


class GuildMusicState:
    def __init__(self):
        self.queue = collections.deque()
        self.voice_client: discord.VoiceClient = None
        self.current: Song = None


music_states: dict[int, GuildMusicState] = {}


def get_music_state(guild_id: int) -> GuildMusicState:
    if guild_id not in music_states:
        music_states[guild_id] = GuildMusicState()
    return music_states[guild_id]


async def search_song(query: str):
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
    if "entries" in data:
        if not data["entries"]:
            return None
        data = data["entries"][0]
    return Song(title=data.get("title", "Άγνωστος τίτλος"), url=data.get("webpage_url"), stream_url=data["url"], requester=None)


def play_next(guild_id: int, error=None):
    state = get_music_state(guild_id)
    if state.queue:
        song = state.queue.popleft()
        state.current = song
        source = discord.FFmpegPCMAudio(song.stream_url, **FFMPEG_OPTS)
        state.voice_client.play(source, after=lambda e: play_next(guild_id, e))
    else:
        state.current = None


@bot.tree.command(name="join", description="Το bot μπαίνει στο voice channel σου")
async def join(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message("❌ Πρέπει να είσαι σε voice channel.", ephemeral=True)
        return
    channel = interaction.user.voice.channel
    state = get_music_state(interaction.guild.id)
    if state.voice_client and state.voice_client.is_connected():
        await state.voice_client.move_to(channel)
    else:
        state.voice_client = await channel.connect()
    await interaction.response.send_message(f"✅ Μπήκα στο **{channel.name}**")


@bot.tree.command(name="leave", description="Το bot φεύγει από το voice channel")
async def leave(interaction: discord.Interaction):
    state = get_music_state(interaction.guild.id)
    if state.voice_client:
        await state.voice_client.disconnect()
        state.queue.clear()
        state.current = None
        await interaction.response.send_message("👋 Έφυγα από το voice channel.")
    else:
        await interaction.response.send_message("❌ Δεν είμαι σε voice channel.", ephemeral=True)


@bot.tree.command(name="play", description="Παίζει τραγούδι από YouTube (link ή αναζήτηση)")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    if not interaction.user.voice:
        await interaction.followup.send("❌ Πρέπει να είσαι σε voice channel.")
        return

    state = get_music_state(interaction.guild.id)
    if not state.voice_client or not state.voice_client.is_connected():
        state.voice_client = await interaction.user.voice.channel.connect()

    try:
        song = await search_song(query)
    except Exception as e:
        await interaction.followup.send(f"❌ Σφάλμα αναζήτησης: {e}")
        return

    if song is None:
        await interaction.followup.send("❌ Δεν βρέθηκε τίποτα.")
        return

    song.requester = interaction.user
    state.queue.append(song)

    if not state.voice_client.is_playing() and not state.voice_client.is_paused():
        play_next(interaction.guild.id)
        await interaction.followup.send(f"▶️ Παίζει τώρα: **{song.title}**")
    else:
        await interaction.followup.send(f"➕ Προστέθηκε στη λίστα: **{song.title}**")


@bot.tree.command(name="pause", description="Παύση της μουσικής")
async def pause(interaction: discord.Interaction):
    state = get_music_state(interaction.guild.id)
    if state.voice_client and state.voice_client.is_playing():
        state.voice_client.pause()
        await interaction.response.send_message("⏸️ Παύση.")
    else:
        await interaction.response.send_message("❌ Δεν παίζει τίποτα.", ephemeral=True)


@bot.tree.command(name="resume", description="Συνέχιση της μουσικής")
async def resume(interaction: discord.Interaction):
    state = get_music_state(interaction.guild.id)
    if state.voice_client and state.voice_client.is_paused():
        state.voice_client.resume()
        await interaction.response.send_message("▶️ Συνέχεια.")
    else:
        await interaction.response.send_message("❌ Δεν είναι σε παύση.", ephemeral=True)


@bot.tree.command(name="skip", description="Πάει στο επόμενο τραγούδι")
async def skip(interaction: discord.Interaction):
    state = get_music_state(interaction.guild.id)
    if state.voice_client and (state.voice_client.is_playing() or state.voice_client.is_paused()):
        state.voice_client.stop()
        await interaction.response.send_message("⏭️ Skip!")
    else:
        await interaction.response.send_message("❌ Δεν παίζει τίποτα.", ephemeral=True)


@bot.tree.command(name="stop", description="Σταματάει τη μουσική και αδειάζει τη λίστα")
async def stop(interaction: discord.Interaction):
    state = get_music_state(interaction.guild.id)
    state.queue.clear()
    if state.voice_client:
        state.voice_client.stop()
    await interaction.response.send_message("⏹️ Σταμάτησε η μουσική και αδειάστηκε η λίστα.")


@bot.tree.command(name="queue", description="Δείχνει τη λίστα αναπαραγωγής")
async def queue_cmd(interaction: discord.Interaction):
    state = get_music_state(interaction.guild.id)
    if not state.current and not state.queue:
        await interaction.response.send_message("📭 Η λίστα είναι άδεια.")
        return
    lines = []
    if state.current:
        lines.append(f"▶️ Τώρα παίζει: **{state.current.title}**")
    for i, song in enumerate(state.queue, 1):
        lines.append(f"{i}. {song.title}")
    await interaction.response.send_message("\n".join(lines))


# ============================================================
#  INVITE TRACKING
# ============================================================

# guild_id -> {invite_code: uses}
invite_cache: dict[int, dict[str, int]] = {}


async def cache_guild_invites(guild: discord.Guild):
    try:
        invites = await guild.invites()
        invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
    except discord.Forbidden:
        print(f"⚠️ Δεν έχω δικαίωμα 'Manage Server' στο {guild.name} για invite tracking.")


@bot.event
async def on_guild_join(guild: discord.Guild):
    # Χωρίς αυτό, αν το bot μπει σε νέο server ενώ ήδη τρέχει, δεν έχει
    # baseline invite counts και ο πρώτος χρήστης που μπαίνει αποδίδεται λάθος.
    await cache_guild_invites(guild)


@bot.event
async def on_invite_create(invite: discord.Invite):
    invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses or 0


@bot.event
async def on_invite_delete(invite: discord.Invite):
    invite_cache.get(invite.guild.id, {}).pop(invite.code, None)


@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    before = invite_cache.get(guild.id, {})
    try:
        after_invites = await guild.invites()
    except discord.Forbidden:
        return

    after = {inv.code: inv.uses for inv in after_invites}
    used_invite = None
    for inv in after_invites:
        if after.get(inv.code, 0) > before.get(inv.code, 0):
            used_invite = inv
            break

    invite_cache[guild.id] = after

    if used_invite and used_invite.inviter:
        conn = get_conn()
        get_user(conn, used_invite.inviter.id)
        conn.execute(
            "UPDATE users SET invites = invites + 1 WHERE user_id=?",
            (used_invite.inviter.id,),
        )
        conn.commit()
        conn.close()


@bot.tree.command(name="invites", description="Δείχνει πόσα άτομα έχει καλέσει ένας χρήστης")
async def invites_cmd(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    conn = get_conn()
    row = get_user(conn, member.id)
    conn.close()
    embed = discord.Embed(title=f"📨 Invites του {member.display_name}", color=discord.Color.teal())
    embed.add_field(name="Σύνολο invites", value=str(row[7]))
    await interaction.response.send_message(embed=embed)


@leaderboard_group.command(name="invites", description="Δείχνει ποιοι έχουν καλέσει τους περισσότερους στον server")
async def leaderboard_invites(interaction: discord.Interaction):
    conn = get_conn()
    cur = conn.execute("SELECT user_id, invites FROM users WHERE invites > 0 ORDER BY invites DESC LIMIT 10")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await interaction.response.send_message("Δεν υπάρχουν καταγεγραμμένα invites ακόμα.")
        return
    lines = []
    for i, (user_id, invite_count) in enumerate(rows, 1):
        user = interaction.guild.get_member(user_id)
        name = user.display_name if user else f"Χρήστης {user_id}"
        lines.append(f"**{i}.** {name} — {invite_count} invites")
    embed = discord.Embed(title="🏆 Leaderboard Invites", description="\n".join(lines), color=discord.Color.teal())
    await interaction.response.send_message(embed=embed)


bot.tree.add_command(leaderboard_group)


# ============================================================
#  READY / STARTUP
# ============================================================

@bot.event
async def on_ready():
    print(f"✅ Συνδέθηκε ως {bot.user} (ID: {bot.user.id})")
    for guild in bot.guilds:
        await cache_guild_invites(guild)
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Sync {len(synced)} slash commands")
    except Exception as e:
        print(f"⚠️ Σφάλμα στο sync: {e}")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help | /help"))


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌ Δεν βρέθηκε DISCORD_TOKEN. Βάλε το στο .env ή στα Railway variables.")
    bot.run(TOKEN)
