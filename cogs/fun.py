import discord
from discord import app_commands
from discord.ext import commands
import random

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


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="8ball", description="Ρώτα τη μαγική μπάλα")
    async def eightball(self, interaction: discord.Interaction, question: str):
        answer = random.choice(EIGHTBALL_ANSWERS)
        embed = discord.Embed(title="🎱 Magic 8-Ball", color=discord.Color.purple())
        embed.add_field(name="Ερώτηση", value=question, inline=False)
        embed.add_field(name="Απάντηση", value=answer, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="coinflip", description="Ρίχνει ένα νόμισμα")
    async def coinflip(self, interaction: discord.Interaction):
        result = random.choice(["Κορώνα 🪙", "Γράμματα 🪙"])
        await interaction.response.send_message(f"Το νόμισμα έδειξε: **{result}**")

    @app_commands.command(name="dice", description="Ρίχνει ζάρι (1-6 ή custom πλευρές)")
    async def dice(self, interaction: discord.Interaction, sides: int = 6):
        result = random.randint(1, sides)
        await interaction.response.send_message(f"🎲 Έριξες: **{result}** (από 1 έως {sides})")

    @app_commands.command(name="meme", description="Στέλνει ένα τυχαίο joke/meme κείμενο")
    async def meme(self, interaction: discord.Interaction):
        await interaction.response.send_message(random.choice(JOKES))

    @app_commands.command(name="rps", description="Παίξε πέτρα-ψαλίδι-χαρτί με το bot")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Πέτρα", value="rock"),
        app_commands.Choice(name="Ψαλίδι", value="scissors"),
        app_commands.Choice(name="Χαρτί", value="paper"),
    ])
    async def rps(self, interaction: discord.Interaction, choice: app_commands.Choice[str]):
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
        await interaction.response.send_message(
            f"Εσύ: **{names[user_choice]}** | Bot: **{names[bot_choice]}**\n{result}"
        )

    @app_commands.command(name="avatar", description="Δείχνει το avatar ενός χρήστη")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        embed = discord.Embed(title=f"Avatar του {member.display_name}", color=discord.Color.blue())
        embed.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
