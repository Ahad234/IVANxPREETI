import asyncio
import importlib

from pyrogram import idle

import config
from ANNIEMUSIC import LOGGER, app, userbot
from ANNIEMUSIC.core.call import JARVIS
from ANNIEMUSIC.misc import sudo
from ANNIEMUSIC.plugins import ALL_MODULES
from ANNIEMUSIC.utils.database import get_banned_users, get_gbanned
from ANNIEMUSIC.utils.cookie_handler import fetch_and_store_cookies
from config import BANNED_USERS


async def init():
    # ✅ Check Pyrogram session strings
    if not any([config.STRING1, config.STRING2, config.STRING3, config.STRING4, config.STRING5]):
        LOGGER(__name__).error(
            "Assistant session not filled! Please provide at least one Pyrogram session string."
        )
        exit()

    # ✅ Load cookies at startup
    try:
        await fetch_and_store_cookies()
        LOGGER("preetixmusic").info("✅ YouTube cookies loaded successfully")
    except Exception as e:
        LOGGER("preetixmusic").warning(f"⚠️ Cookie loading failed: {e}")

    # ✅ Load sudo users
    await sudo()

    # ✅ Load banned users
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except Exception as e:
        LOGGER("preetixmusic").warning(f"⚠️ Failed to load banned users: {e}")

    # ✅ Start Pyrogram clients
    await app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("ANNIEMUSIC.plugins." + all_module)

    LOGGER("ANNIEMUSIC.plugins").info("✅ All modules loaded successfully")
    await userbot.start()
    await JARVIS.start()

    # ✅ Attempt to stream startup media
    call = await JARVIS.get_call(config.LOGGER_ID) if hasattr(config, "LOGGER_ID") else None
    if call:
        try:
            await JARVIS.stream_call(
                "https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4"
            )
        except Exception as e:
            LOGGER("preetixmusic").error(f"⚠️ Could not stream startup media: {e}")
    else:
        LOGGER("preetixmusic").warning(
            "⚠️ No active voice chat found in your log group/channel. Please start a VC manually."
        )

    # ✅ Register decorators
    await JARVIS.decorators()
    LOGGER("preetixmusic").info("🎶Ivan Baby started successfully!")

    # ✅ Keep bot running
    await idle()

    # ✅ Stop services
    await app.stop()
    await userbot.stop()
    LOGGER("preetixmusic").info("🛑 Ivan Music Bot stopped.")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
