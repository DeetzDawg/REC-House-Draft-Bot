# Tournament Sign-Up Bot

## What it does
All commands are usable by **anyone** in the server, except `/signup_for`,
`/withdraw_player`, `/set_captain`, and `/set_sub`, which require the **Manage Server**
permission.

- `/signup` — opens a form: primary position, secondary position, tertiary position,
  and whether you want to be a captain, plus a **Submit** button. Position choices are
  **PG, SG, SG - Lock, SF, SF - Lock, PF, C**. Fill out all four dropdowns, then hit
  Submit — it'll tell you if anything's missing. Running `/signup` again overwrites
  your previous entry. **Captain slots scale with sign-ups**: 2 base, 3 once there are
  15 sign-ups, 4 once there are 20. If you pick "Yes" for captain and all current slots
  are already filled, you're signed up as a regular player instead, with a heads-up
  message explaining why. Whenever sign-ups cross 10, 15, or 20 and a slot is still
  open, someone is randomly picked to fill it.
- `/signup_for user:<member>` — **(Manage Server permission required)** opens the same
  form as `/signup`, but fills it out on behalf of the specified member instead of the
  admin themselves. Useful for signing up people who aren't comfortable using slash
  commands, or who forgot. Everything else (captain caps, auto-assignment) applies the
  same way as a normal sign-up.
- `/withdraw_player user:<member>` — **(Manage Server permission required)** removes
  another member's sign-up. Blocked if that member is currently a captain in an active
  draft — reset the tournament first if you need to remove them at that point.
- `/set_captain user:<member> captain:<True/False>` — **(Manage Server permission
  required)** promotes a signed-up player to captain or removes their captain status.
  This can exceed the normal scaling captain cap if you set it intentionally (you'll
  get a heads-up note, but it's allowed). Blocked while that player is a captain in an
  active draft. Making someone a captain automatically clears their sub status.
- `/set_sub user:<member> sub:<True/False>` — **(Manage Server permission required)**
  marks a signed-up player as a **substitute**. Subs stay visible on the roster (tagged
  🪑) but are automatically left out of the draftable pool when `/start_draft` runs —
  so captains can't pick them. Useful when more people sign up than you have roster
  spots for. Can't mark a current captain as a sub (remove captain status first) and
  is blocked while that player is part of an active draft.
- `/withdraw` — removes your own sign-up. Captains can't withdraw mid-draft (someone
  would need to `/reset_tournament` first).
- `/roster` — shows the current sign-up list privately (just to you).
- `/setup_results` — posts the live results message in the current channel. This
  message auto-updates every time someone signs up, withdraws, drafts a player, or the
  tournament is reset. Run this once per tournament, in whatever channel you want the
  public list to live.
- `/start_draft` — kicks off the captains' draft. Requires **at least 2** captains
  signed up (works with 2, 3, or 4). Draft order is randomized once when the draft
  starts, then picks proceed in **serpentine (snake) order** — e.g. with 3 captains:
  A, B, C, C, B, A, A, B, C... The captain at either end of the order picks twice in a
  row when the direction flips, which is standard for snake drafts.
- `/draft_pick player:<name>` — usable only by whichever captain's turn it is. Pick
  from an autocomplete dropdown of players still available. Once picked, that player
  can't be chosen again this draft, and turns follow the serpentine order above.
- `/draft_board` — shows the current draft: each captain's picks, whose turn it is,
  and who's still in the pool. Same info as the auto-updating results message.
- `/reset_tournament` — wipes all sign-ups *and* the draft so you can start a new
  tournament. The results message updates automatically to show it's empty.

If you'd rather lock some of these down later (e.g. only mods can `/reset_tournament`),
that's a quick change to re-add — just let me know.

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
