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
    """Initialize and start Annie Music bot."""

    # 🔹 Validate Pyrogram session strings
    if not any([config.STRING1, config.STRING2, config.STRING3, config.STRING4, config.STRING5]):
        LOGGER(__name__).error("❌ Assistant session not filled! Please provide at least one Pyrogram session string.")
        exit()

    # 🔹 Load YouTube cookies (optional)
    try:
        await fetch_and_store_cookies()
        LOGGER("ANNIEMUSIC").info("✅ YouTube cookies loaded successfully")
    except Exception as e:
        LOGGER("ANNIEMUSIC").warning(f"⚠️ Cookie loading failed: {e}")

    # 🔹 Load sudo users
    await sudo()

    # 🔹 Load banned users into memory
    try:
        for user_id in await get_gbanned():
            BANNED_USERS.add(user_id)
        for user_id in await get_banned_users():
            BANNED_USERS.add(user_id)
        LOGGER("ANNIEMUSIC").info(f"✅ Loaded {len(BANNED_USERS)} banned users.")
    except Exception as e:
        LOGGER("ANNIEMUSIC").warning(f"⚠️ Failed to load banned users: {e}")

    # 🔹 Start main Pyrogram bot client
    await app.start()

    # 🔹 Load all modules dynamically
    for module in ALL_MODULES:
        importlib.import_module("ANNIEMUSIC.plugins." + module)
    LOGGER("ANNIEMUSIC.plugins").info("✅ All modules loaded successfully")

    # 🔹 Start assistant userbot and voice call engine
    await userbot.start()
    await JARVIS.start()
    LOGGER("ANNIEMUSIC").info("🎧 Assistants and voice engine started successfully")

    # 🔹 Try streaming a startup video if VC is active
    log_chat = getattr(config, "LOGGER_ID", None)
    if log_chat:
        try:
            if await JARVIS.ensure_vc(log_chat):
                await JARVIS.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4", chat_id=log_chat)
                LOGGER("ANNIEMUSIC").info("✅ Startup media streaming in log VC")
            else:
                LOGGER("ANNIEMUSIC").warning("⚠️ No active VC in log group/channel. Start VC manually to stream.")
        except Exception as e:
            LOGGER("ANNIEMUSIC").error(f"⚠️ Failed to start stream: {e}")
    else:
        LOGGER("ANNIEMUSIC").warning("⚠️ No LOGGER_ID found in config. Skipping startup media streaming.")

    # 🔹 Register decorators (event listeners)
    await JARVIS.decorators()
    LOGGER("ANNIEMUSIC").info("🎶 Annie Music Bot started successfully!")

    # 🔹 Idle to keep running
    await idle()

    # 🔹 Graceful shutdown
    await app.stop()
    await userbot.stop()
    LOGGER("ANNIEMUSIC").info("🛑 Annie Music Bot stopped.")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
