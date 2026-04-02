import datetime
import io
import json
import os
from collections import defaultdict
from enum import Enum

import asyncpg
import discord
import numpy as np
from discord.ext import tasks
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from PIL import Image
from skimage.metrics import structural_similarity as ssim


class ActionType(Enum):
    NONE = 0
    TIMEOUT = 1
    KICK = 2


load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
runtime_settings = defaultdict(dict)

cached_messages = defaultdict(list)
processing_users = set()


def format_duration(days):
    hours = days * 24
    if hours < 24:
        return f'{hours:g} {"hour" if hours == 1 else "hours"}'
    return f'{days:g} {"day" if days == 1 else "days"}'


async def initialize_db():
    bot.db = await asyncpg.create_pool(os.getenv('DATABASE_URI'))
    await bot.db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            guild_id        BIGINT  PRIMARY KEY,
            log_channel     BIGINT,
            action_type INTEGER DEFAULT 0,
            timeout_dur     FLOAT   DEFAULT 7,
            det_win         FLOAT   DEFAULT 1,
            chan_thres      INTEGER DEFAULT 3
        )
    """)


async def save_settings(guildID, loggingID, actionType, timeoutDuration, detectionWindow, channelThreshold):
    await bot.db.execute("""
        INSERT INTO settings (guild_id, log_channel, action_type, timeout_dur, det_win, chan_thres)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (guild_id) DO UPDATE SET
            log_channel = EXCLUDED.log_channel,
            action_type = EXCLUDED.action_type,
            timeout_dur = EXCLUDED.timeout_dur,
            det_win = EXCLUDED.det_win,
            chan_thres = EXCLUDED.chan_thres
    """, guildID, loggingID, actionType, timeoutDuration, detectionWindow, channelThreshold)


async def retrieve_settings(guildID):
    row = await bot.db.fetchrow(
        "SELECT log_channel, action_type, timeout_dur, det_win, chan_thres FROM settings WHERE guild_id = $1",
        guildID
    )
    if row:
        return {
            "LOGGING_CHANNEL": row["log_channel"],
            "ACTION_TYPE": row["action_type"],
            "TIMEOUT_DURATION": row["timeout_dur"],
            "DETECTION_WINDOW": row["det_win"],
            "CHANNEL_THRESHOLD": row["chan_thres"]
        }
    return None


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
        actionType = runtime_settings[guildID]['ACTION_TYPE']

        if actionType == ActionType.TIMEOUT:
            await user.timeout(datetime.timedelta(days=runtime_settings[guildID]['TIMEOUT_DURATION']))

        if actionType == ActionType.KICK:
            await user.kick(reason="[Aegis] Account suspected for being compromised.")
    except:
        pass

    embeded: discord.Embed = discord.Embed(
        title='Compromised Account Detected',
        description=f'**User:** {user.global_name}\n**Reason:** Sent {len(messages)} messages in {channels_used} channels within {runtime_settings[guildID]['DETECTION_WINDOW']} seconds.\n**Action Taken:** User timed out for {format_duration(runtime_settings[guildID]['TIMEOUT_DURATION'])}',
        color=0xff0000,
        timestamp=datetime.datetime.now()
    )
    await bot.get_channel(runtime_settings[guildID]['LOGGING_CHANNEL']).send(embed=embeded)


@tasks.loop(seconds=1)
async def clear_cache():
    now = datetime.datetime.now(datetime.timezone.utc)
    keys = list(cached_messages.keys())

    for key in keys:
        if key in processing_users:
            continue

        cached_messages[key] = [
            msg for msg in cached_messages[key]
            if (now - msg.created_at) <= datetime.timedelta(seconds=runtime_settings[msg.guild.id]['DETECTION_WINDOW'])
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
    if len(channels_used) >= runtime_settings[message.guild.id]['CHANNEL_THRESHOLD'] and key not in processing_users:
        processing_users.add(key)
        try:
            await handle_compromised_account(*key, len(channels_used))
        finally:
            processing_users.discard(key)

    await bot.process_commands(message)


@bot.tree.command(name='setlogchannel', description='Set the channel for bot logs')
@app_commands.checks.has_permissions(administrator=True)
async def setLogChannel(interaction: discord.Interaction, channel: discord.TextChannel):
    runtime_settings[interaction.guild.id]['LOGGING_CHANNEL'] = channel.id

    await bot.db.execute("""
        INSERT INTO SETTINGS (guild_id, log_channel)
        VALUES ($2, $1)
        ON CONFLICT (guild_id)
        DO UPDATE SET log_channel = $1
    """, channel.id, interaction.guild.id)

    await interaction.response.send_message(f'Log channel set to {channel.mention}')


@bot.tree.command(name='settimeoutduration', description='Set the timeout duration in days')
@app_commands.checks.has_permissions(administrator=True)
async def setTimeoutDuration(interaction: discord.Interaction, duration: float):
    runtime_settings[interaction.guild.id]['TIMEOUT_DURATION'] = duration

    await bot.db.execute("""
        INSERT INTO SETTINGS (guild_id, timeout_dur)
        VALUES ($2, $1)
        ON CONFLICT (guild_id)
        DO UPDATE SET timeout_dur = $1
    """, duration, interaction.guild.id)

    await interaction.response.send_message(f'Timeout duration set to {format_duration(duration)}')


@bot.tree.command(name='setdetectiontime', description='Set the amount of time between messages to flag a user in seconds')
@app_commands.checks.has_permissions(administrator=True)
async def setDetectionTime(interaction: discord.Interaction, duration: float):
    runtime_settings[interaction.guild.id]['DETECTION_WINDOW'] = duration

    await bot.db.execute("""
        INSERT INTO settings (guild_id, det_win)
        VALUES ($2, $1)
        ON CONFLICT (guild_id)
        DO UPDATE SET det_win = $1
    """, duration, interaction.guild.id)

    await interaction.response.send_message(f'Detection time set to {duration} seconds')


@bot.tree.command(name='setchannelthreshold', description='Set the number of channels an account must send the same message to to get flagged')
@app_commands.checks.has_permissions(administrator=True)
async def setChannelThreshold(interaction: discord.Interaction, n: int):
    runtime_settings[interaction.guild.id]['CHANNEL_THRESHOLD'] = n

    await bot.db.execute("""
        INSERT INTO settings (guild_id, chan_thres)
        VALUES ($2, $1)
        ON CONFLICT (guild_id)
        DO UPDATE SET chan_thres = $1
    """, n, interaction.guild.id)

    await interaction.response.send_message(f'Channel threshold set to {n}')


@bot.tree.command(name='setactiontype', description='Set the action to be taken for flagged accounts')
@app_commands.checks.has_permissions(administrator=True)
async def setActionType(interaction: discord.Interaction, action_type: ActionType):
    runtime_settings[interaction.guild.id]['ACTION_TYPE'] = action_type

    await bot.db.execute("""
        INSERT INTO settings (guild_id, action_type)
        VALUES ($2, $1)
        ON CONFLICT (guild_id)
        DO UPDATE SET action_type = $1
    """, action_type.value, interaction.guild.id)

    await interaction.response.send_message(f'Set action type to {action_type.name}')


@bot.tree.command(name='sync', description='Sync commands')
@app_commands.checks.has_permissions(administrator=True)
async def sync(interaction: discord.Interaction):
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()
    await interaction.response.send_message('Commands synced')


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return


@bot.event
async def on_ready():
    await initialize_db()

    bot.tree.copy_global_to(guild=discord.Object(id=967959755861671967))
    await bot.tree.sync(guild=discord.Object(id=967959755861671967))

    for guild in bot.guilds:
        settings = await retrieve_settings(guild.id)
        if settings:
            runtime_settings[guild.id] = settings

    if not clear_cache.is_running():
        clear_cache.start()

    print("Aegis is ready!")


bot.run(os.getenv("AEGIS_TOKEN"))