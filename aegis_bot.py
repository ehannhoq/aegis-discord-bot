import datetime
import io
import json
import os
from collections import defaultdict
from difflib import SequenceMatcher

import asyncpg
import discord
import numpy as np
from discord.ext import tasks
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from PIL import Image
from skimage.metrics import structural_similarity as ssim
from scipy.optimize import linear_sum_assignment

from database import default_settings
from database import initialize_db
from database import retrieve_settings
from enums import ActionType
from utils import format_duration
from utils import send_embeded

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.runtime_settings = defaultdict(default_settings)

cached_messages = defaultdict(list)
processing_users = set()

MESSAGE_SIMILARITY_THRESHOLD = 0.80
IMAGE_SIMILARITY_THRESHOLD = 0.90


async def check_similar_messages(messages: list[discord.Message]) -> bool:
    anchor = messages[0]
    for i in range(1, len(messages)):
        if anchor.content != '' and messages[i].content != '':
            ratio = SequenceMatcher(None, anchor.content, messages[i].content).ratio()
            if ratio >= MESSAGE_SIMILARITY_THRESHOLD:   
                return True

        if anchor.attachments and messages[i].attachments:
            score = await attachment_set_similarity(anchor.attachments, messages[i].attachments)
            if score >= IMAGE_SIMILARITY_THRESHOLD:
                return True
    
    return False

async def attachment_set_similarity(attachments_a: list[discord.Attachment], attachments_b: list[discord.Attachment]) -> float:
    matrix = np.zeros((len(attachments_a), len(attachments_b)))

    for i, a in enumerate(attachments_a):
        a_bytes = await a.read()
        a_image = np.array(Image.open(io.BytesIO(a_bytes)).convert('RGB'))
        for j, b in enumerate(attachments_b):
            b_bytes = await b.read()
            b_image = np.array(Image.open(io.BytesIO(b_bytes)).convert('RGB'))
            matrix[i][j] = ssim(a_image, b_image, data_range=255, channel_axis=-1)

    row, col = linear_sum_assignment(-matrix)
    paired_scores = matrix[row, col]

    max_len = max(len(attachments_a), len(attachments_b))
    return paired_scores.sum() / max_len


async def handle_compromised_account(guildID, userID, channels_used):
    messages = cached_messages.pop((guildID, userID), [])
    if not messages:
        return
    
    for msg in messages:
        try:
            await msg.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

    guild: discord.Guild = bot.get_guild(guildID)
    user: discord.Member = await guild.fetch_member(userID)
    
    actionType = bot.runtime_settings[guildID]['ACTION_TYPE']
    try:
        if actionType == ActionType.TIMEOUT.value:
            await user.timeout(datetime.timedelta(days=bot.runtime_settings[guildID]['TIMEOUT_DURATION']))
        elif actionType == ActionType.KICK.value:
            await user.kick(reason="[Aegis] Account suspected for being compromised.")
    except (discord.Forbidden, discord.HTTPException):
        pass

    if bot.runtime_settings[guildID]['LOGGING_CHANNEL']:
        title = 'Compromised Account Detected'
        username = f'**User:** {user.global_name}'
        reason = f'**Reason:** Sent {len(messages)} messages in {channels_used} channels within {bot.runtime_settings[guildID]['DETECTION_WINDOW']} seconds'
        action_taken = '**Action Taken:** None'
        if actionType == ActionType.TIMEOUT.value:
            action_taken = f'**Action Taken:** User timed out for {format_duration(bot.runtime_settings[guildID]['TIMEOUT_DURATION'])}'
        elif actionType == ActionType.KICK.value:
            action_taken = f'**Action Taken:** Kicked user.'

        await send_embeded(bot=bot, guildID=guildID, channel_id=bot.runtime_settings[guildID]['LOGGING_CHANNEL'], title=title, description=username + '\n' + reason + '\n' + action_taken, color=0xff0000, timestamp=datetime.datetime.now())

        if bot.runtime_settings[guildID]['ROLE_PING']:
            role = guild.get_role(bot.runtime_settings[guildID]['ROLE_PING'])
            await guild.get_channel(bot.runtime_settings[guildID]['LOGGING_CHANNEL']).send(f'{role.mention}')

        


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
            similar_messages = await check_similar_messages(cached_messages[key])
            if similar_messages:
                await handle_compromised_account(*key, len(channels_used))
            else:
                title = 'Compromised Account Suspected'
                user = f"**User:** {message.author.global_name}"
                reason = f'**Reason:** Sent {len(cached_messages[key])} messages in {len(channels_used)} within {bot.runtime_settings[message.guild.id]['DETECTION_WINDOW']} seconds'

                await send_embeded(bot=bot, guildID=message.guild.id, title=title, description=user + '\n' + reason + '\n' + '**Action Taken:** None', color=0xff8800, timestamp=datetime.datetime.now())
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