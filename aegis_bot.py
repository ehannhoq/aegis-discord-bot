import io
import datetime
import os
from collections import defaultdict

import discord
from discord.ext import tasks
from discord.ext import commands
from discord import app_commands
import numpy as np
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

cached_messages = defaultdict(list)
processing_users = set()

LOG_CHANNEL = 967959760274088009
CHANNEL_THRESHOLD = 2
TIME_WINDOW = 5
TIMEOUT_DURATION = 7


def format_duration(days):
    hours = days * 24
    if hours < 24:
        return f'{hours:g} {"hour" if hours == 1 else "hours"}'
    return f'{days:g} {"day" if days == 1 else "days"}'


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
        await user.timeout(datetime.timedelta(days=TIMEOUT_DURATION))
    except:
        pass

    embeded: discord.Embed = discord.Embed(
        title='Compromised Account Detected',
        description=f'**User:** {user.global_name}\n**Reason:** Sent {len(messages)} messages in {channels_used} channels within {TIME_WINDOW} seconds.\n**Action Taken:** User timed out for {format_duration(TIMEOUT_DURATION)}',
        color=0xff0000,
        timestamp=datetime.datetime.now()
    )
    await bot.get_channel(LOG_CHANNEL).send(embed=embeded)


@tasks.loop(seconds=1)
async def check_cache():
    now = datetime.datetime.now(datetime.timezone.utc)
    keys = list(cached_messages.keys())

    for key in keys:
        if key in processing_users:
            continue

        cached_messages[key] = [
            msg for msg in cached_messages[key]
            if (now - msg.created_at) <= datetime.timedelta(seconds=TIME_WINDOW)
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
    if len(channels_used) >= CHANNEL_THRESHOLD and key not in processing_users:
        processing_users.add(key)
        try:
            await handle_compromised_account(*key, len(channels_used))
        finally:
            processing_users.discard(key)

    await bot.process_commands(message)


@bot.tree.command(name='setlogchannel', description='Set the channel for bot logs')
@app_commands.checks.has_permissions(administrator=True)
async def setLogChannel(interaction: discord.Interaction, channel: discord.TextChannel):
    global LOG_CHANNEL
    LOG_CHANNEL = channel.id
    await interaction.response.send_message(f'Log channel set to {channel.mention}')


@bot.tree.command(name='settimeoutduration', description='Set the timeout duration in days')
@app_commands.checks.has_permissions(administrator=True)
async def setTimeoutDuration(interaction: discord.Interaction, duration: float):
    global TIMEOUT_DURATION
    TIMEOUT_DURATION = duration
    await interaction.response.send_message(f'Timeout duration set to {format_duration(duration)}')


@bot.tree.command(name='setdetectiontime', description='Set the amount of time between messages to flag a user in seconds')
@app_commands.checks.has_permissions(administrator=True)
async def setDetectionTime(interaction: discord.Interaction, duration: float):
    global TIME_WINDOW
    TIME_WINDOW = duration
    await interaction.response.send_message(f'Detection time set to {duration} seconds')


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
    if not check_cache.is_running():
        check_cache.start()

    print(f"Logged in as: {bot.user}, Status: Ready!")


bot.run(os.getenv("AEGIS_TOKEN"))