import discord
from discord.ext import commands
from discord import app_commands

from utils import format_duration
from enums import ActionType


class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='setlogchannel', description='Set the channel for bot logs')
    @app_commands.checks.has_permissions(administrator=True)
    async def setLogChannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.bot.runtime_settings[interaction.guild.id]['LOGGING_CHANNEL'] = channel.id

        await self.bot.db.execute("""
            INSERT INTO SETTINGS (guild_id, log_channel)
            VALUES ($2, $1)
            ON CONFLICT (guild_id)
            DO UPDATE SET log_channel = $1
        """, channel.id, interaction.guild.id)

        await interaction.response.send_message(f'Log channel set to {channel.mention}')

    @app_commands.command(name='settimeoutduration', description='Set the timeout duration in days')
    @app_commands.checks.has_permissions(administrator=True)
    async def setTimeoutDuration(self, interaction: discord.Interaction, duration: float):
        self.bot.runtime_settings[interaction.guild.id]['TIMEOUT_DURATION'] = duration

        await self.bot.db.execute("""
            INSERT INTO SETTINGS (guild_id, timeout_dur)
            VALUES ($2, $1)
            ON CONFLICT (guild_id)
            DO UPDATE SET timeout_dur = $1
        """, duration, interaction.guild.id)

        await interaction.response.send_message(f'Timeout duration set to {format_duration(duration)}')

    @app_commands.command(name='setdetectiontime', description='Set the amount of time between messages to flag a user in seconds')
    @app_commands.checks.has_permissions(administrator=True)
    async def setDetectionTime(self, interaction: discord.Interaction, duration: float):
        self.bot.runtime_settings[interaction.guild.id]['DETECTION_WINDOW'] = duration

        await self.bot.db.execute("""
            INSERT INTO settings (guild_id, det_win)
            VALUES ($2, $1)
            ON CONFLICT (guild_id)
            DO UPDATE SET det_win = $1
        """, duration, interaction.guild.id)

        await interaction.response.send_message(f'Detection time set to {duration} seconds')

    @app_commands.command(name='setchannelthreshold', description='Set the number of channels an account must send the same message to to get flagged')
    @app_commands.checks.has_permissions(administrator=True)
    async def setChannelThreshold(self, interaction: discord.Interaction, n: int):
        self.bot.runtime_settings[interaction.guild.id]['CHANNEL_THRESHOLD'] = n

        await self.bot.db.execute("""
            INSERT INTO settings (guild_id, chan_thres)
            VALUES ($2, $1)
            ON CONFLICT (guild_id)
            DO UPDATE SET chan_thres = $1
        """, n, interaction.guild.id)

        await interaction.response.send_message(f'Channel threshold set to {n}')

    @app_commands.command(name='setactiontype', description='Set the action to be taken for flagged accounts')
    @app_commands.checks.has_permissions(administrator=True)
    async def setActionType(self, interaction: discord.Interaction, action_type: ActionType):
        self.bot.runtime_settings[interaction.guild.id]['ACTION_TYPE'] = action_type

        await self.bot.db.execute("""
            INSERT INTO settings (guild_id, action_type)
            VALUES ($2, $1)
            ON CONFLICT (guild_id)
            DO UPDATE SET action_type = $1
        """, action_type.value, interaction.guild.id)

        await interaction.response.send_message(f'Set action type to {action_type.name}')

    
    @app_commands.command(name='setroleping', description='Set the role that will get pinged for compromised/suspected accounts')
    @app_commands.checks.has_permissions(administrator=True)
    async def setRolePing(self, interaction: discord.Interaction, role: discord.Role):
        self.bot.runtime_settings[interaction.guild.id]['ROLE_PING'] = role.id

        await self.bot.db.execute("""
            INSERT INTO settings (guild_id, role_ping)
            VALUES ($2, $1)
            ON CONFLICT (guild_id)
            DO UPDATE SET role_ping = $1
        """, role.id, interaction.guild.id)

        await interaction.response.send_message(f'Set role ping to {role.name}')


    @app_commands.command(name='sync', description='Sync commands')
    @app_commands.checks.has_permissions(administrator=True)
    async def sync(self, interaction: discord.Interaction):
        self.bot.tree.clear_commands(guild=None)
        await self.bot.tree.sync()
        await interaction.response.send_message('Commands synced')

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return


async def setup(bot):
    await bot.add_cog(Commands(bot))