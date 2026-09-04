import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import random
import time
import math
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "economy.db")


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
            last_xp_gain REAL DEFAULT 0
        )
    """)
    return conn


def get_user(conn, user_id):
    cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row is None:
        conn.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return (user_id, 0, 0, 1, 0, 0, 0)
    return row


def xp_for_level(level: int) -> int:
    return 5 * (level ** 2) + 50 * level + 100


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        conn = get_conn()
        row = get_user(conn, message.author.id)
        _, balance, xp, level, last_daily, last_work, last_xp_gain = row
        now = time.time()
        if now - last_xp_gain >= 60:  # 1 XP gain per minute of activity
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
                    await message.channel.send(
                        f"🎉 Συγχαρητήρια {message.author.mention}, ανέβηκες στο **level {level}**!"
                    )
                except discord.Forbidden:
                    pass
        conn.close()

    @app_commands.command(name="balance", description="Δείχνει το υπόλοιπό σου")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        conn = get_conn()
        row = get_user(conn, member.id)
        conn.close()
        embed = discord.Embed(title=f"💰 Πορτοφόλι του {member.display_name}", color=discord.Color.gold())
        embed.add_field(name="Υπόλοιπο", value=f"{row[1]} coins")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Μάζεψε το ημερήσιο bonus σου")
    async def daily(self, interaction: discord.Interaction):
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

    @app_commands.command(name="work", description="Δούλεψε για να κερδίσεις coins")
    async def work(self, interaction: discord.Interaction):
        conn = get_conn()
        row = get_user(conn, interaction.user.id)
        now = time.time()
        last_work = row[5]
        if now - last_work < 3600:
            remaining = int(3600 - (now - last_work))
            minutes = remaining // 60
            await interaction.response.send_message(
                f"⏳ Κουράστηκες! Ξαναδοκίμασε σε {minutes} λεπτά.", ephemeral=True
            )
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

    @app_commands.command(name="give", description="Δώσε coins σε άλλο χρήστη")
    async def give(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            await interaction.response.send_message("❌ Το ποσό πρέπει να είναι θετικό.", ephemeral=True)
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

    @app_commands.command(name="level", description="Δείχνει το level και XP σου")
    async def level(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        conn = get_conn()
        row = get_user(conn, member.id)
        conn.close()
        needed = xp_for_level(row[3])
        embed = discord.Embed(title=f"📊 Level του {member.display_name}", color=discord.Color.green())
        embed.add_field(name="Level", value=row[3])
        embed.add_field(name="XP", value=f"{row[2]} / {needed}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Δείχνει το leaderboard του server (coins)")
    async def leaderboard(self, interaction: discord.Interaction):
        conn = get_conn()
        cur = conn.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10")
        rows = cur.fetchall()
        conn.close()
        if not rows:
            await interaction.response.send_message("Δεν υπάρχουν δεδομένα ακόμα.")
            return
        lines = []
        for i, (user_id, balance) in enumerate(rows, 1):
            user = interaction.guild.get_member(user_id)
            name = user.display_name if user else f"Χρήστης {user_id}"
            lines.append(f"**{i}.** {name} — {balance} coins")
        embed = discord.Embed(title="🏆 Leaderboard", description="\n".join(lines), color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
