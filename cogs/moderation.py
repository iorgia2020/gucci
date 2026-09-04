import discord
from discord import app_commands
from discord.ext import commands
import datetime


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_check_perms(self, member: discord.Member, perm: str) -> bool:
        return getattr(member.guild_permissions, perm, False)

    # ---------- KICK ----------
    @app_commands.command(name="kick", description="Κάνει kick έναν χρήστη")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Δεν δόθηκε λόγος"):
        await member.kick(reason=reason)
        embed = discord.Embed(
            title="👢 Kick",
            description=f"Ο/Η {member.mention} έφυγε από τον server.\n**Λόγος:** {reason}",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed)

    # ---------- BAN ----------
    @app_commands.command(name="ban", description="Κάνει ban έναν χρήστη")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Δεν δόθηκε λόγος"):
        await member.ban(reason=reason)
        embed = discord.Embed(
            title="🔨 Ban",
            description=f"Ο/Η {member.mention} έφαγε ban.\n**Λόγος:** {reason}",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed)

    # ---------- UNBAN ----------
    @app_commands.command(name="unban", description="Κάνει unban έναν χρήστη (με user ID)")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            await interaction.response.send_message(f"✅ Έγινε unban ο/η **{user}**.")
        except Exception:
            await interaction.response.send_message("❌ Δεν βρέθηκε χρήστης με αυτό το ID.", ephemeral=True)

    # ---------- TIMEOUT / MUTE ----------
    @app_commands.command(name="mute", description="Κάνει timeout έναν χρήστη (σε λεπτά)")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "Δεν δόθηκε λόγος"):
        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        embed = discord.Embed(
            title="🔇 Mute",
            description=f"Ο/Η {member.mention} σιώπησε για **{minutes} λεπτά**.\n**Λόγος:** {reason}",
            color=discord.Color.dark_grey(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unmute", description="Αφαιρεί το timeout από έναν χρήστη")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None)
        await interaction.response.send_message(f"🔊 Ο/Η {member.mention} μπορεί να μιλήσει ξανά.")

    # ---------- WARN (in-memory, simple) ----------
    warns = {}

    @app_commands.command(name="warn", description="Δίνει προειδοποίηση σε χρήστη")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Δεν δόθηκε λόγος"):
        self.warns.setdefault(member.id, []).append(reason)
        count = len(self.warns[member.id])
        embed = discord.Embed(
            title="⚠️ Προειδοποίηση",
            description=f"Ο/Η {member.mention} πήρε προειδοποίηση.\n**Λόγος:** {reason}\n**Σύνολο:** {count}",
            color=discord.Color.yellow(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="warnings", description="Δείχνει τις προειδοποιήσεις ενός χρήστη")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        user_warns = self.warns.get(member.id, [])
        if not user_warns:
            await interaction.response.send_message(f"Ο/Η {member.mention} δεν έχει προειδοποιήσεις.")
            return
        text = "\n".join(f"{i+1}. {w}" for i, w in enumerate(user_warns))
        await interaction.response.send_message(f"**Προειδοποιήσεις για {member.mention}:**\n{text}")

    # ---------- CLEAR / PURGE ----------
    @app_commands.command(name="clear", description="Διαγράφει μηνύματα από το κανάλι")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 Διαγράφηκαν {len(deleted)} μηνύματα.", ephemeral=True)

    # ---------- SLOWMODE ----------
    @app_commands.command(name="slowmode", description="Ορίζει slowmode στο κανάλι (σε δευτερόλεπτα)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int):
        await interaction.channel.edit(slowmode_delay=seconds)
        await interaction.response.send_message(f"🐌 Slowmode ορίστηκε στα {seconds} δευτερόλεπτα.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
