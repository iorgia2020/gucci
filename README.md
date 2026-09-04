# Full Custom Discord Bot 🤖

Bot με:
- **Moderation**: `/kick`, `/ban`, `/unban`, `/mute`, `/unmute`, `/warn`, `/warnings`, `/clear`, `/slowmode`
- **Fun**: `/8ball`, `/coinflip`, `/dice`, `/meme`, `/rps`, `/avatar`
- **Economy & Levels**: `/balance`, `/daily`, `/work`, `/give`, `/level`, `/leaderboard` (+ αυτόματο XP όσο μιλάς)
- **Music**: `/join`, `/leave`, `/play`, `/pause`, `/resume`, `/skip`, `/stop`, `/queue`

## 1. Δημιουργία Discord Application

1. Πήγαινε στο https://discord.com/developers/applications → **New Application**
2. Bot tab → **Add Bot** → αντέγραψε το **Token**
3. Στο **Bot** tab, ενεργοποίησε:
   - `MESSAGE CONTENT INTENT`
   - `SERVER MEMBERS INTENT`
4. Στο **OAuth2 → URL Generator**, επίλεξε scopes `bot` + `applications.commands`,
   και permissions: Administrator (ή τα ελάχιστα που χρειάζεσαι) → πάρε το link και κάλεσε το bot στον server σου.

## 2. Τοπικό τρέξιμο (δοκιμή)

```bash
pip install -r requirements.txt
cp .env.example .env   # και βάλε το token σου μέσα
python bot.py
```

Χρειάζεται επίσης **ffmpeg** εγκατεστημένο τοπικά για τη μουσική
(π.χ. `sudo apt install ffmpeg` σε Linux, ή `choco install ffmpeg` σε Windows).

## 3. Deployment στο Railway

1. Ανέβασε τον φάκελο σε ένα GitHub repo.
2. Πήγαινε στο https://railway.app → **New Project → Deploy from GitHub repo**.
3. Στο Railway project, πήγαινε στο **Variables** και πρόσθεσε:
   - `DISCORD_TOKEN` = το token σου
   - `PREFIX` = `!` (προαιρετικό)
4. Το `nixpacks.toml` φροντίζει να εγκατασταθεί αυτόματα το `ffmpeg`.
5. Deploy — το bot θα μείνει online 24/7 όσο τρέχει το Railway service.

⚠️ **Σημείωση για economy.db**: Το SQLite αρχείο σβήνεται σε κάθε νέο deploy στο Railway
(το filesystem είναι ephemeral). Αν θες μόνιμα δεδομένα, πρόσθεσε ένα
[Railway Volume](https://docs.railway.app/reference/volumes) και άλλαξε το `DB_PATH`
στο `cogs/economy.py` ώστε να δείχνει εκεί.

## 4. Προσαρμογή

- Πρόσθεσε δικά σου cogs στο `cogs/` και βάλε το όνομά τους στη λίστα
  `INITIAL_EXTENSIONS` μέσα στο `bot.py`.
- Άλλαξε emoji, μηνύματα, χρώματα embeds όπως θες.
