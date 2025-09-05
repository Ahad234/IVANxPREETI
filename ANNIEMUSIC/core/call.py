import asyncio
from typing import Optional, List

from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired

import config
from ANNIEMUSIC import LOGGER
from pytgcalls import GroupCallFactory
from pytgcalls.types.input_stream import AudioPiped, VideoPiped


class Call:
    """
    Multi-assistant voice client manager.
    - Starts up to 5 userbot clients (from STRING1..STRING5)
    - Starts matching GroupCallFactory instances
    - Provides helpers to check VC status and stream audio/video
    """

    def __init__(self) -> None:
        self.userbots: List[Optional[Client]] = []
        self.calls: List[Optional[object]] = []
        self.active_calls: set[int] = set()

        strings = [
            ("AnnieXAssis1", config.STRING1),
            ("AnnieXAssis2", config.STRING2),
            ("AnnieXAssis3", config.STRING3),
            ("AnnieXAssis4", config.STRING4),
            ("AnnieXAssis5", config.STRING5),
        ]

        for name, sess in strings:
            if sess:
                cli = Client(
                    name=name,
                    api_id=config.API_ID,
                    api_hash=config.API_HASH,
                    session_string=sess,
                )
                self.userbots.append(cli)

                # New way to create group call client
                call_client = GroupCallFactory(cli).get_group_call()
                self.calls.append(call_client)
            else:
                self.userbots.append(None)
                self.calls.append(None)

    async def start(self) -> None:
        """Start all userbots and their call clients."""
        LOGGER(__name__).info("Starting assistants with GroupCallFactory backend...")

        for cli in self.userbots:
            if cli and not cli.is_connected:
                await cli.start()

        for call in self.calls:
            if call:
                await call.start()

        LOGGER(__name__).info("✅ All assistants and call engines started.")

    async def stop(self) -> None:
        """Stop all calls and clients."""
        for call in self.calls:
            if call:
                try:
                    await call.stop()
                except Exception:
                    pass
        for cli in self.userbots:
            if cli:
                try:
                    await cli.stop()
                except Exception:
                    pass

    def _pick_call(self):
        """Pick the first available call engine."""
        for call in self.calls:
            if call is not None:
                return call
        return None

    async def get_call(self, chat_id: int):
        """Return call info for this chat, or None if inactive."""
        call = self._pick_call()
        if not call:
            return None
        try:
            return await call.get_call(chat_id)
        except Exception:
            return None

    async def ensure_vc(self, chat_id: int) -> bool:
        """Check if a VC is active in the chat."""
        info = await self.get_call(chat_id)
        return bool(info)

    async def join(self, chat_id: int, source: str, video: bool = False) -> bool:
        """Join a VC and start streaming an audio or video source."""
        call = self._pick_call()
        if not call:
            LOGGER(__name__).error("No available GroupCall client.")
            return False

        try:
            stream = VideoPiped(source) if video else AudioPiped(source)
            await call.join_group_call(chat_id, stream)
            self.active_calls.add(chat_id)
            return True
        except FloodWait as e:
            await asyncio.sleep(e.value)
            return await self.join(chat_id, source, video)
        except ChatAdminRequired:
            LOGGER(__name__).error("Assistant lacks 'Manage Video Chats' permission.")
            return False
        except Exception as e:
            LOGGER(__name__).error(f"Failed to join VC in {chat_id}: {e}")
            return False

    async def change_stream(self, chat_id: int, source: str, video: bool = False) -> bool:
        """Change the active stream in the VC."""
        call = self._pick_call()
        if not call:
            return False
        try:
            stream = VideoPiped(source) if video else AudioPiped(source)
            await call.change_stream(chat_id, stream)
            return True
        except Exception as e:
            LOGGER(__name__).error(f"Failed to change stream in {chat_id}: {e}")
            return False

    async def leave(self, chat_id: int) -> bool:
        """Leave the VC for a chat."""
        call = self._pick_call()
        if not call:
            return False
        try:
            await call.leave_group_call(chat_id)
            self.active_calls.discard(chat_id)
            return True
        except Exception as e:
            LOGGER(__name__).error(f"Failed to leave VC in {chat_id}: {e}")
            return False

    async def stream_call(self, source: str, chat_id: Optional[int] = None, video: bool = False) -> bool:
        """Start or switch stream in the given chat or default log group."""
        if chat_id is None and hasattr(config, "LOGGER_ID"):
            chat_id = int(getattr(config, "LOGGER_ID"))

        if chat_id is None:
            LOGGER(__name__).warning("No chat_id provided and config.LOGGER_ID is missing.")
            return False

        if await self.ensure_vc(chat_id):
            return await self.change_stream(chat_id, source, video)
        return await self.join(chat_id, source, video)

    async def decorators(self):
        """Hook for event handlers if needed in the future."""
        return


JARVIS = Call()
