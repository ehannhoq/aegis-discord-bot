import datetime
import discord


def format_duration(days):
    hours = days * 24
    if hours < 24:
        return f'{hours:g} {"hour" if hours == 1 else "hours"}'
    return f'{days:g} {"day" if days == 1 else "days"}'


async def send_embeded(bot, guildID: int, channel_id: int, title: str, description: str, color: int, timestamp:datetime.datetime):
    embeded: discord.Embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=timestamp
    )
    await bot.get_channel(channel_id).send(embed=embeded)