import datetime
import io
import json
import os
from collections import defaultdict

import asyncpg
import discord
import numpy as np
from discord.ext import tasks
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from PIL import Image
from skimage.metrics import structural_similarity as ssim

from database import default_settings
from database import initialize_db
from database import retrieve_settings
from enums import ActionType
from utils import format_duration

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.runtime_settings = defaultdict(default_settings)

cached_messages = defaultdict(list)
processing_users = set()


async def handle_compromised_account(guildID, userID, channels_used):
    messages = cached_messages.pop((guildID, userID), [])
    if not messages:
        return
    
    for msg in messages:
        try:
            await msg.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

    user: discord.Member = await bot.get_guild(guildID).fetch_member(userID)
    try:
        actionType = bot.runtime_settings[guildID]['ACTION_TYPE']

        if actionType == ActionType.TIMEOUT:
            await user.timeout(datetime.timedelta(days=bot.runtime_settings[guildID]['TIMEOUT_DURATION']))
        elif actionType == ActionType.KICK:
            await user.kick(reason="[Aegis] Account suspected for being compromised.")
    except:
        pass

    title = 'Compromised Account Detected'
    username = f'**User:** {user.global_name}'
    reason = f'Sent {len(messages)} messages in {channels_used} channels within {bot.runtime_settings[guildID]['DETECTION_WINDOW']} seconds'
    action_taken = '**Action Taken:** None'
    if actionType == ActionType.TIMEOUT:
        action_taken = f'**Action Taken:** User timed out for {format_duration(bot.runtime_settings[guildID]['TIMEOUT_DURATION'])}'
    elif actionType == ActionType.KICK:
        action_taken = f'**Action Taken:** Kicked user.'

    embeded: discord.Embed = discord.Embed(
        title=title,
        description=username + '\n' + reason + '\n' + action_taken,
        color=0xff0000,
        timestamp=datetime.datetime.now()
    )
    await bot.get_channel(bot.runtime_settings[guildID]['LOGGING_CHANNEL']).send(embed=embeded)


@tasks.loop(seconds=1)
async def clear_cache():
    now = datetime.datetime.now(datetime.timezone.utc)
    keys = list(cached_messages.keys())

    for key in keys:
        if key in processing_users:
            continue

        cached_messages[key] = [
            msg for msg in cached_messages[key]
            if (now - msg.created_at) <= datetime.timedelta(seconds=bot.runtime_settings[msg.guild.id]['DETECTION_WINDOW'])
        ]

        if not cached_messages[key]:
            del cached_messages[key]
            

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    key = (message.guild.id, message.author.id)
    cached_messages[key].append(message)

    channels_used = set(msg.channel for msg in cached_messages[key])
    if len(channels_used) >= bot.runtime_settings[message.guild.id]['CHANNEL_THRESHOLD'] and key not in processing_users:
        processing_users.add(key)
        try:
            await handle_compromised_account(*key, len(channels_used))
        finally:
            processing_users.discard(key)

    await bot.process_commands(message)


@bot.event
async def on_ready():
    await bot.load_extension('commands')
    await initialize_db(bot=bot)

    # await bot.tree.sync()
    bot.tree.copy_global_to(guild=discord.Object(id=1346357633279459411))
    await bot.tree.sync(guild=discord.Object(id=1346357633279459411))

    for guild in bot.guilds:
        settings = await retrieve_settings(bot=bot, guildID=guild.id)
        if settings:
            bot.runtime_settings[guild.id] = settings

    if not clear_cache.is_running():
        clear_cache.start()

    print("Aegis is ready!")


bot.run(os.getenv("AEGIS_TOKEN"))