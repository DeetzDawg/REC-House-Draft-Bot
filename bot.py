"""
Tournament Sign-Up Discord Bot
--------------------------------
Slash commands:
  /signup          - Opens an interactive form (primary/secondary position, Lock/Hash, captain?)
  /roster          - Shows the current sign-up list (ephemeral, on-demand)
  /withdraw        - Removes your own sign-up
  /setup_results   - (admin) Posts the auto-updating results message in the current channel
  /reset_tournament- (admin) Clears all sign-ups and starts fresh

Data is stored in tournament_data.json so it survives bot restarts.
"""

import json
import os
import discord
from discord import app_commands
from discord.ext import commands

DATA_FILE = "tournament_data.json"

POSITIONS = ["PG", "SG", "SF", "PF", "C"]
TYPES = ["Lock", "Hash"]

# ---------- Persistence ----------

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"results_channel_id": None, "results_message_id": None, "signups": {}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


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
        data["signups"][str(interaction.user.id)] = {
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
    save_data(data)
    await refresh_results_message(data, interaction.client)
    await interaction.response.send_message("🔄 Tournament reset. All sign-ups cleared.", ephemeral=True)


@setup_results.error
@reset_tournament.error
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
