# Tournament Sign-Up Bot

## What it does
- `/signup` — opens a form: primary position (PG/SG/SF/PF/C), secondary position,
  Lock or Hash (for your primary position), and whether you want to be a captain.
  Running `/signup` again overwrites your previous entry.
- `/withdraw` — removes your own sign-up.
- `/roster` — shows the current sign-up list privately (just to you).
- `/setup_results` — **(admin only)** posts the live results message in the current
  channel. This message auto-updates every time someone signs up, withdraws, or the
  tournament is reset. Run this once per tournament, in whatever channel you want the
  public list to live.
- `/reset_tournament` — **(admin only)** wipes all sign-ups so you can start a new
  tournament. The results message updates automatically to show it's empty.

"Admin" = anyone with the **Manage Server** permission in your Discord server.

## Setup

1. **Create the bot application**
   - Go to https://discord.com/developers/applications → New Application.
   - Go to the "Bot" tab → click "Reset Token" → copy the token (keep it secret).
   - Under "Installation" / "OAuth2", generate an invite URL with scopes:
     `bot`, `applications.commands`, and permissions: `Send Messages`, `Embed Links`,
     `Use Slash Commands`. Use that URL to invite the bot to your server.

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set your bot token as an environment variable**
   ```bash
   export DISCORD_BOT_TOKEN="your-token-here"      # macOS/Linux
   setx DISCORD_BOT_TOKEN "your-token-here"         # Windows (new terminal after)
   ```

4. **Run the bot**
   ```bash
   python bot.py
   ```

5. **In Discord**, run `/setup_results` in the channel where you want the live roster
   posted, then let people start using `/signup`.

## Notes
- Data is saved to `tournament_data.json` in the same folder as `bot.py`, so sign-ups
  survive a bot restart. Delete this file if you ever want a full hard reset (or just
  use `/reset_tournament`).
- No special "Message Content" intent is needed since everything runs through slash
  commands and buttons/dropdowns.
- If the results message ever gets deleted, just run `/setup_results` again to repost it.
