import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import collections

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


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.states: dict[int, GuildMusicState] = {}

    def get_state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self.states:
            self.states[guild_id] = GuildMusicState()
        return self.states[guild_id]

    async def search(self, query: str) -> Song | None:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        if "entries" in data:
            if not data["entries"]:
                return None
            data = data["entries"][0]
        return Song(title=data.get("title", "Άγνωστος τίτλος"), url=data.get("webpage_url"), stream_url=data["url"], requester=None)

    def play_next(self, guild_id: int, error=None):
        state = self.get_state(guild_id)
        if state.queue:
            song = state.queue.popleft()
            state.current = song
            source = discord.FFmpegPCMAudio(song.stream_url, **FFMPEG_OPTS)
            state.voice_client.play(source, after=lambda e: self.play_next(guild_id, e))
        else:
            state.current = None

    @app_commands.command(name="join", description="Το bot μπαίνει στο voice channel σου")
    async def join(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("❌ Πρέπει να είσαι σε voice channel.", ephemeral=True)
            return
        channel = interaction.user.voice.channel
        state = self.get_state(interaction.guild.id)
        if state.voice_client and state.voice_client.is_connected():
            await state.voice_client.move_to(channel)
        else:
            state.voice_client = await channel.connect()
        await interaction.response.send_message(f"✅ Μπήκα στο **{channel.name}**")

    @app_commands.command(name="leave", description="Το bot φεύγει από το voice channel")
    async def leave(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        if state.voice_client:
            await state.voice_client.disconnect()
            state.queue.clear()
            state.current = None
            await interaction.response.send_message("👋 Έφυγα από το voice channel.")
        else:
            await interaction.response.send_message("❌ Δεν είμαι σε voice channel.", ephemeral=True)

    @app_commands.command(name="play", description="Παίζει τραγούδι από YouTube (link ή αναζήτηση)")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        if not interaction.user.voice:
            await interaction.followup.send("❌ Πρέπει να είσαι σε voice channel.")
            return

        state = self.get_state(interaction.guild.id)
        if not state.voice_client or not state.voice_client.is_connected():
            state.voice_client = await interaction.user.voice.channel.connect()

        try:
            song = await self.search(query)
        except Exception as e:
            await interaction.followup.send(f"❌ Σφάλμα αναζήτησης: {e}")
            return

        if song is None:
            await interaction.followup.send("❌ Δεν βρέθηκε τίποτα.")
            return

        song.requester = interaction.user
        state.queue.append(song)

        if not state.voice_client.is_playing() and not state.voice_client.is_paused():
            self.play_next(interaction.guild.id)
            await interaction.followup.send(f"▶️ Παίζει τώρα: **{song.title}**")
        else:
            await interaction.followup.send(f"➕ Προστέθηκε στη λίστα: **{song.title}**")

    @app_commands.command(name="pause", description="Παύση της μουσικής")
    async def pause(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.pause()
            await interaction.response.send_message("⏸️ Παύση.")
        else:
            await interaction.response.send_message("❌ Δεν παίζει τίποτα.", ephemeral=True)

    @app_commands.command(name="resume", description="Συνέχιση της μουσικής")
    async def resume(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        if state.voice_client and state.voice_client.is_paused():
            state.voice_client.resume()
            await interaction.response.send_message("▶️ Συνέχεια.")
        else:
            await interaction.response.send_message("❌ Δεν είναι σε παύση.", ephemeral=True)

    @app_commands.command(name="skip", description="Πάει στο επόμενο τραγούδι")
    async def skip(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        if state.voice_client and (state.voice_client.is_playing() or state.voice_client.is_paused()):
            state.voice_client.stop()  # τριγγερίζει το after -> play_next
            await interaction.response.send_message("⏭️ Skip!")
        else:
            await interaction.response.send_message("❌ Δεν παίζει τίποτα.", ephemeral=True)

    @app_commands.command(name="stop", description="Σταματάει τη μουσική και αδειάζει τη λίστα")
    async def stop(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        state.queue.clear()
        if state.voice_client:
            state.voice_client.stop()
        await interaction.response.send_message("⏹️ Σταμάτησε η μουσική και αδειάστηκε η λίστα.")

    @app_commands.command(name="queue", description="Δείχνει τη λίστα αναπαραγωγής")
    async def queue_cmd(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        if not state.current and not state.queue:
            await interaction.response.send_message("📭 Η λίστα είναι άδεια.")
            return
        lines = []
        if state.current:
            lines.append(f"▶️ Τώρα παίζει: **{state.current.title}**")
        for i, song in enumerate(state.queue, 1):
            lines.append(f"{i}. {song.title}")
        await interaction.response.send_message("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
