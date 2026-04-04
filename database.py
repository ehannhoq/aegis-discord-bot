import asyncpg
import os
from enums import ActionType

def default_settings():
    return {
        'LOGGING_CHANNEL': None,
        'ACTION_TYPE': ActionType.NONE.value,
        'TIMEOUT_DURATION': 7,
        'DETECTION_WINDOW': 1,
        'CHANNEL_THRESHOLD': 3,
        'ROLE_PING': None
    }

async def initialize_db(bot):
    bot.db = await asyncpg.create_pool(os.getenv('DATABASE_URI'))
    await bot.db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            guild_id        BIGINT  PRIMARY KEY,
            log_channel     BIGINT,
            action_type INTEGER DEFAULT 0,
            timeout_dur     FLOAT   DEFAULT 7,
            det_win         FLOAT   DEFAULT 1,
            chan_thres      INTEGER DEFAULT 3,
            role_ping       BIGINT
        )
    """)


async def retrieve_settings(bot, guildID):
    row = await bot.db.fetchrow(
        "SELECT log_channel, action_type, timeout_dur, det_win, chan_thres, role_ping FROM settings WHERE guild_id = $1",
        guildID
    )
    if row:
        return {
            "LOGGING_CHANNEL": row["log_channel"],
            "ACTION_TYPE": row["action_type"],
            "TIMEOUT_DURATION": row["timeout_dur"],
            "DETECTION_WINDOW": row["det_win"],
            "CHANNEL_THRESHOLD": row["chan_thres"],
            "ROLE_PING": row["role_ping"]
        }
    return None