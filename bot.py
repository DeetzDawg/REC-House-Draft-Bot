"""
Tournament Sign-Up Discord Bot
--------------------------------
Slash commands:
  /signup          - Opens an interactive form (primary/secondary position, Lock/Hash, captain?)
                     Only 2 captains are allowed per tournament.
  /roster          - Shows the current sign-up list (ephemeral, on-demand)
  /withdraw        - Removes your own sign-up
  /setup_results   - (admin) Posts the auto-updating results message in the current channel
  /reset_tournament- (admin) Clears all sign-ups and the draft, and starts fresh
  /start_draft     - (admin) Begins the captains' draft. Requires exactly 2 captains signed up.
  /draft_pick      - (captains only, on their turn) Draft a player from the available pool
  /draft_board     - Shows current draft picks, whose turn it is, and remaining players

Data is stored in tournament_data.json so it survives bot restarts.
"""

import json
import os
import random
import discord
from discord import app_commands
from discord.ext import commands

DATA_FILE = "tournament_data.json"

POSITIONS = ["PG", "SG", "SF", "PF", "C"]
TYPES = ["Lock", "Hash"]
MAX_CAPTAINS = 2

# ---------- Persistence ----------

def load_data():
    if not os.path.exists(DATA_FILE):
        return default_data()
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    # Backfill draft key for data files saved before the draft feature existed
    if "draft" not in data:
        data["draft"] = default_draft()
    return data


def default_draft():
    return {"active": False, "complete": False, "captains": [], "teams": {}, "turn": None, "available": []}


def default_data():
    return {
        "results_channel_id": None,
        "results_message_id": None,
        "signups": {},
        "draft": default_draft(),
    }


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ---------- Bot setup ----------

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.manage_guild
    return app_commands.check(predicate)


def build_results_embed(data: dict) -> discord.Embed:
    signups = data["signups"]
    embed = discord.Embed(
        title="🏀 Tournament Sign-Ups",
        description=f"Total players: **{len(signups)}**",
        color=discord.Color.blurple(),
    )
    if not signups:
        embed.add_field(name="No sign-ups yet", value="Use `/signup` to join!", inline=False)
        return embed

    # Captains listed first, then everyone else, in sign-up order
    captains = [s for s in signups.values() if s["captain"]]
    others = [s for s in signups.values() if not s["captain"]]

    def fmt(entry):
        tag = "👑 " if entry["captain"] else ""
        return (
            f"{tag}**{entry['display_name']}** — "
            f"Primary: `{entry['primary']}` ({entry['type']}) | "
            f"Secondary: `{entry['secondary']}`"
        )

    lines = [fmt(e) for e in captains] + [fmt(e) for e in others]

    # Discord embed fields cap at 1024 chars; chunk if needed
    chunk = ""
    field_num = 1
    for line in lines:
        if len(chunk) + len(line) + 1 > 1024:
            embed.add_field(name=f"Players {field_num}", value=chunk, inline=False)
            chunk = ""
            field_num += 1
        chunk += line + "\n"
    if chunk:
        embed.add_field(name=f"Players {field_num}" if field_num > 1 else "Players", value=chunk, inline=False)

    draft = data.get("draft", default_draft())
    if draft["active"] or draft["complete"]:
        embed.add_field(name="\u200b", value="**🏀 Draft**", inline=False)
        for cap_id in draft["captains"]:
            cap_name = signups.get(cap_id, {}).get("display_name", "Unknown")
            picks = draft["teams"].get(cap_id, [])
            if picks:
                pick_names = ", ".join(signups.get(pid, {}).get("display_name", "Unknown") for pid in picks)
            else:
                pick_names = "*no picks yet*"
            turn_marker = " ⬅️ on the clock" if draft["active"] and draft["turn"] == cap_id else ""
            embed.add_field(name=f"👑 {cap_name}{turn_marker}", value=pick_names, inline=False)

        if draft["complete"]:
            embed.add_field(name="Status", value="✅ Draft complete!", inline=False)
        elif draft["available"]:
            remaining = ", ".join(signups.get(pid, {}).get("display_name", "Unknown") for pid in draft["available"])
            embed.add_field(name="Available Players", value=remaining, inline=False)

    return embed


async def refresh_results_message(data: dict, client: discord.Client):
    channel_id = data.get("results_channel_id")
    message_id = data.get("results_message_id")
    if not channel_id or not message_id:
        return
    channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
    try:
        message = await channel.fetch_message(message_id)
        await message.edit(embed=build_results_embed(data))
    except discord.NotFound:
        pass  # Message was deleted; admin will need to /setup_results again


# ---------- Sign-up UI ----------

class PrimarySelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=p) for p in POSITIONS]
        super().__init__(placeholder="Primary position", options=options, custom_id="primary")

    async def callback(self, interaction: discord.Interaction):
        self.view.primary = self.values[0]
        for opt in self.options:
            opt.default = opt.value == self.values[0]
        await interaction.response.edit_message(view=self.view)


class SecondarySelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=p) for p in POSITIONS]
        super().__init__(placeholder="Secondary position", options=options, custom_id="secondary")

    async def callback(self, interaction: discord.Interaction):
        self.view.secondary = self.values[0]
        for opt in self.options:
            opt.default = opt.value == self.values[0]
        await interaction.response.edit_message(view=self.view)


class TypeSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=t) for t in TYPES]
        super().__init__(placeholder="Lock or Hash (primary position)", options=options, custom_id="type")

    async def callback(self, interaction: discord.Interaction):
        self.view.pos_type = self.values[0]
        for opt in self.options:
            opt.default = opt.value == self.values[0]
        await interaction.response.edit_message(view=self.view)


class CaptainSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label="Yes"), discord.SelectOption(label="No")]
        super().__init__(placeholder="Want to be a captain?", options=options, custom_id="captain")

    async def callback(self, interaction: discord.Interaction):
        self.view.captain = self.values[0] == "Yes"
        for opt in self.options:
            opt.default = opt.label == self.values[0]
        await interaction.response.edit_message(view=self.view)


class SubmitButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Submit Sign-Up", style=discord.ButtonStyle.green, row=4)

    async def callback(self, interaction: discord.Interaction):
        view: SignupView = self.view
        missing = []
        if view.primary is None:
            missing.append("Primary position")
        if view.secondary is None:
            missing.append("Secondary position")
        if view.pos_type is None:
            missing.append("Lock/Hash")
        if view.captain is None:
            missing.append("Captain")
        if missing:
            await interaction.response.send_message(
                f"⚠️ Please fill out: {', '.join(missing)}", ephemeral=True
            )
            return

        data = load_data()
        uid = str(interaction.user.id)

        if view.captain:
            existing_captains = [
                u for u, s in data["signups"].items() if s["captain"] and u != uid
            ]
            if len(existing_captains) >= MAX_CAPTAINS:
                await interaction.response.edit_message(
                    content=(
                        f"⚠️ There are already {MAX_CAPTAINS} captains signed up. "
                        "You've been signed up as a regular player instead."
                    ),
                    embed=None,
                    view=None,
                )
                view.captain = False
                data["signups"][uid] = {
                    "display_name": interaction.user.display_name,
                    "primary": view.primary,
                    "secondary": view.secondary,
                    "type": view.pos_type,
                    "captain": False,
                }
                save_data(data)
                await refresh_results_message(data, interaction.client)
                return

        data["signups"][uid] = {
            "display_name": interaction.user.display_name,
            "primary": view.primary,
            "secondary": view.secondary,
            "type": view.pos_type,
            "captain": view.captain,
        }
        save_data(data)
        await refresh_results_message(data, interaction.client)

        await interaction.response.edit_message(
            content="✅ You're signed up! You can run `/signup` again anytime to update your entry.",
            embed=None,
            view=None,
        )


class SignupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.primary = None
        self.secondary = None
        self.pos_type = None
        self.captain = None
        self.add_item(PrimarySelect())
        self.add_item(SecondarySelect())
        self.add_item(TypeSelect())
        self.add_item(CaptainSelect())
        self.add_item(SubmitButton())


# ---------- Commands ----------

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")


@bot.tree.command(name="signup", description="Sign up for the tournament")
async def signup(interaction: discord.Interaction):
    await interaction.response.send_message(
        "Fill out your sign-up below:", view=SignupView(), ephemeral=True
    )


@bot.tree.command(name="withdraw", description="Remove yourself from the tournament")
async def withdraw(interaction: discord.Interaction):
    data = load_data()
    uid = str(interaction.user.id)
    if uid not in data["signups"]:
        await interaction.response.send_message("You're not signed up.", ephemeral=True)
        return

    draft = data.get("draft", default_draft())
    if draft["active"] and uid in draft["captains"]:
        await interaction.response.send_message(
            "🚫 You're a captain in an active draft and can't withdraw right now. "
            "Ask an admin to `/reset_tournament` if needed.",
            ephemeral=True,
        )
        return
    if draft["active"] and uid in draft["available"]:
        draft["available"].remove(uid)

    del data["signups"][uid]
    save_data(data)
    await refresh_results_message(data, interaction.client)
    await interaction.response.send_message("You've been removed from the tournament.", ephemeral=True)


@bot.tree.command(name="roster", description="View the current tournament sign-ups")
async def roster(interaction: discord.Interaction):
    data = load_data()
    await interaction.response.send_message(embed=build_results_embed(data), ephemeral=True)


@bot.tree.command(name="setup_results", description="[Admin] Post the auto-updating results message here")
@is_admin()
async def setup_results(interaction: discord.Interaction):
    data = load_data()
    embed = build_results_embed(data)
    message = await interaction.channel.send(embed=embed)
    data["results_channel_id"] = interaction.channel.id
    data["results_message_id"] = message.id
    save_data(data)
    await interaction.response.send_message("✅ Results message posted and will auto-update.", ephemeral=True)


@bot.tree.command(name="reset_tournament", description="[Admin] Clear all sign-ups for a new tournament")
@is_admin()
async def reset_tournament(interaction: discord.Interaction):
    data = load_data()
    data["signups"] = {}
    data["draft"] = default_draft()
    save_data(data)
    await refresh_results_message(data, interaction.client)
    await interaction.response.send_message("🔄 Tournament reset. All sign-ups cleared.", ephemeral=True)


@bot.tree.command(name="start_draft", description="[Admin] Begin the captains' draft")
@is_admin()
async def start_draft(interaction: discord.Interaction):
    data = load_data()
    signups = data["signups"]

    if data["draft"]["active"]:
        await interaction.response.send_message(
            "⚠️ A draft is already in progress. Use `/draft_board` to see it.", ephemeral=True
        )
        return

    captains = [uid for uid, s in signups.items() if s["captain"]]
    if len(captains) != MAX_CAPTAINS:
        await interaction.response.send_message(
            f"⚠️ Need exactly {MAX_CAPTAINS} captains signed up to start the draft "
            f"(currently {len(captains)}).",
            ephemeral=True,
        )
        return

    available = [uid for uid in signups if uid not in captains]
    first_pick = random.choice(captains)
    data["draft"] = {
        "active": True,
        "complete": False,
        "captains": captains,
        "teams": {c: [] for c in captains},
        "turn": first_pick,
        "available": available,
    }
    save_data(data)
    await refresh_results_message(data, interaction.client)

    if not available:
        data["draft"]["active"] = False
        data["draft"]["complete"] = True
        save_data(data)
        await refresh_results_message(data, interaction.client)
        await interaction.response.send_message(
            "✅ Draft started, but there are no players left to draft — marked complete.",
            ephemeral=True,
        )
        return

    first_captain_name = signups[first_pick]["display_name"]
    await interaction.response.send_message(
        f"🎲 Coin flip: {first_captain_name} picks first! "
        "Captains use `/draft_pick` on their turn.",
    )


async def player_autocomplete(interaction: discord.Interaction, current: str):
    data = load_data()
    draft = data["draft"]
    signups = data["signups"]
    choices = []
    for uid in draft.get("available", []):
        name = signups.get(uid, {}).get("display_name", "Unknown")
        if current.lower() in name.lower():
            choices.append(app_commands.Choice(name=name, value=uid))
    return choices[:25]


@bot.tree.command(name="draft_pick", description="[Captains] Draft a player from the available pool")
@app_commands.describe(player="The player you want to draft")
@app_commands.autocomplete(player=player_autocomplete)
async def draft_pick(interaction: discord.Interaction, player: str):
    data = load_data()
    draft = data["draft"]
    uid = str(interaction.user.id)

    if not draft["active"]:
        await interaction.response.send_message(
            "⚠️ There's no active draft. An admin can start one with `/start_draft`.",
            ephemeral=True,
        )
        return
    if uid != draft["turn"]:
        current_name = data["signups"].get(draft["turn"], {}).get("display_name", "someone")
        await interaction.response.send_message(
            f"🚫 It's not your turn — waiting on {current_name}.", ephemeral=True
        )
        return
    if player not in draft["available"]:
        await interaction.response.send_message(
            "⚠️ That player isn't available (already picked, or invalid). "
            "Pick from the autocomplete list.",
            ephemeral=True,
        )
        return

    draft["available"].remove(player)
    draft["teams"][uid].append(player)

    picked_name = data["signups"].get(player, {}).get("display_name", "Unknown")

    if draft["available"]:
        other_captain = next(c for c in draft["captains"] if c != uid)
        draft["turn"] = other_captain
        next_name = data["signups"].get(other_captain, {}).get("display_name", "the other captain")
        turn_note = f"{next_name} is on the clock."
    else:
        draft["active"] = False
        draft["complete"] = True
        draft["turn"] = None
        turn_note = "That was the last player — draft complete! 🎉"

    save_data(data)
    await refresh_results_message(data, interaction.client)
    await interaction.response.send_message(f"✅ Drafted **{picked_name}**. {turn_note}")


@bot.tree.command(name="draft_board", description="View the current draft picks and whose turn it is")
async def draft_board(interaction: discord.Interaction):
    data = load_data()
    await interaction.response.send_message(embed=build_results_embed(data), ephemeral=True)


@setup_results.error
@reset_tournament.error
@start_draft.error
async def admin_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "🚫 You need the 'Manage Server' permission to do that.", ephemeral=True
        )
    else:
        raise error


if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    if not TOKEN:
        raise SystemExit("Set the DISCORD_BOT_TOKEN environment variable before running the bot.")
    bot.run(TOKEN)
