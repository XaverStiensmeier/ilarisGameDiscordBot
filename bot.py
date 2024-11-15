import discord
from discord.ext import commands
import random
from datetime import datetime, timedelta
import yaml
import os

# Initialize bot with the new prefix "~"
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix="~", intents=intents)

# Player data structure
class Player:
    def __init__(self, wounds=0, inventory=None, equipped_weapons=None, equipped_armor=None, last_roll=None, last_attack=None, being_attacked_today=False):
        self.wounds = wounds
        self.inventory = inventory or []
        self.equipped_weapons = equipped_weapons or []
        self.equipped_armor = equipped_armor or None
        self.last_roll = last_roll or datetime.min
        self.last_attack = last_attack or datetime.min
        self.being_attacked_today = being_attacked_today

    def get_defense(self):
        RS = self.equipped_armor.get("RS", 0) if self.equipped_armor else 0
        return WS_BASE + RS

    def take_damage(self, damage):
        defense = self.get_defense()
        excess_damage = max(0, damage - defense)
        wounds_to_add = excess_damage // defense + (1 if excess_damage % defense else 0)
        self.wounds += wounds_to_add
        if self.wounds >= MAX_WOUNDS:
            return "You have died."
        return f"You have {self.wounds} wounds."

    def to_dict(self):
        return {
            "wounds": self.wounds,
            "inventory": self.inventory,
            "equipped_weapons": self.equipped_weapons,
            "equipped_armor": self.equipped_armor,
            "last_roll": self.last_roll.isoformat(),
            "last_attack": self.last_attack.isoformat(),
            "being_attacked_today": self.being_attacked_today
        }

    @classmethod
    def from_dict(cls, data):
        last_roll = datetime.fromisoformat(data["last_roll"]) if data["last_roll"] else datetime.min
        last_attack = datetime.fromisoformat(data["last_attack"]) if data["last_attack"] else datetime.min
        return cls(
            wounds=data["wounds"],
            inventory=data["inventory"],
            equipped_weapons=data["equipped_weapons"],
            equipped_armor=data["equipped_armor"],
            last_roll=last_roll,
            last_attack=last_attack,
            being_attacked_today=data["being_attacked_today"]
        )

# Constants
WS_BASE = 4  # Base defense
MAX_WOUNDS = 8  # Maximum wounds before death
DAILY_COOLDOWN = timedelta(days=1)

# Load locations and items from YAML
with open("locations.yaml", "r") as file:
    LOCATIONS = yaml.safe_load(file)

# Load or initialize player data
def load_players():
    if os.path.exists("players.yaml"):
        with open("players.yaml", "r") as file:
            data = yaml.safe_load(file)
            # Convert dictionaries to Player objects
            return {k: Player.from_dict(v) for k, v in data.items()}
    return {}

players = load_players()

# Helper function to save player data
def save_players():
    with open("players.yaml", "w") as file:
        # Save Player objects as dictionaries
        data = {k: v.to_dict() for k, v in players.items()}
        yaml.dump(data, file)

# Commands
@bot.command(name="roll")
async def roll_for_item(ctx, *, location: str = None):
    player = players.setdefault(ctx.author.id, Player())

    # Check if the player is dead
    if player.wounds >= MAX_WOUNDS:
        await ctx.send("You are dead and cannot roll for items.")
        return

    # Check if location is valid
    location = location.strip() if location else ""
    if location not in LOCATIONS:
        # Show list of available locations if location is invalid or not provided
        available_locations = ", ".join(LOCATIONS.keys())
        await ctx.send(f"Invalid location. Available locations are:\n{available_locations}")
        return

    # Check cooldown for daily roll
    if datetime.now() - player.last_roll < DAILY_COOLDOWN:
        await ctx.send("You can only roll once per day.")
        return

    # Roll for a random item from the specified location
    item_pool = LOCATIONS[location]
    item = random.choice(item_pool)
    player.inventory.append(item)
    player.last_roll = datetime.now()
    save_players()  # Save player data after rolling
    await ctx.send(f"You received: {item['name']} from {location}!")

@bot.command(name="equip")
async def equip_item(ctx, *, item_name: str):
    player = players.setdefault(ctx.author.id, Player())
    
    # Find the item in the player's inventory
    item = next((i for i in player.inventory if i["name"].lower() == item_name.lower()), None)
    if item is None:
        await ctx.reply(f"Du hast den Gegenstand {item_name} nicht im Inventar ...")
        await check_status(ctx)
        return

    # Check the item type and equip accordingly
    if item["type"] == "waffe":
        # Handle equipping weapons based on handedness
        print(item)
        if item["hands"] == 2 or len(player.equipped_weapons) == 2:
            player.equipped_weapons = [item]  # Two-handed weapon
        elif player.equipped_weapons[0]["hands"] == 1:
            player.equipped_weapons.append(item)
        await ctx.reply(f"Deine Waffen sind {[(equipped_weapon['name'], f"{equipped_weapon['hands']}-haendig") for equipped_weapon in player.equipped_weapons]}")
    
    elif item["type"] == "ruestung":
        player.equipped_armor = item  # Equip the armor
        await ctx.reply(f"Du hast {item['name']} als deine Rüstung ausgerüstet.")
    else:
        await ctx.reply("Dieser Gegenstand kann nicht ausgerüstet werden.")
        return

    save_players()  # Save player data after equipping an item

@bot.command(name="status")
async def check_status(ctx):
    player = players.setdefault(ctx.author.id, Player())
    equipped_weapons = ", ".join([w["name"] for w in player.equipped_weapons]) if player.equipped_weapons else "None"
    equipped_armor = player.equipped_armor["name"] if player.equipped_armor else "None"
    await ctx.reply(f"**Status**\n"
                   f"Equipped Weapons: {equipped_weapons}\n"
                   f"Equipped Armor: {equipped_armor}\n"
                   f"Defense (WS + RS): {player.get_defense()}\n"
                   f"Wounds: {player.wounds}/{MAX_WOUNDS}"
                   f"Inventory: {players.inventory}")

# Save data when bot stops
@bot.event
async def on_disconnect():
    save_players()

# Run the bot
with open("config.yaml", "r") as file:
    CONFIG = yaml.safe_load(file)
bot.run(CONFIG["token"])
