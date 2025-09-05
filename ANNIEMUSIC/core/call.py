# ANNlEMUSIC/core/call.py
# Compatible with PyTgCalls 3.x (and falls back to ntgcalls if present)

import asyncio
from typing import Optional, List

from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired

import config
from ANNIEMUSIC import LOGGER

# --- Dynamic import for pytgcalls v3 / ntgcalls ------------------------------
# We try the PyTgCalls 3.x API first. If not available, try ntgcalls with the
# same surface API. We also handle where AudioPiped/VideoPiped are exposed.
PYTG_BACKEND = "pytgcalls"

try:
    from pytgcalls import PyTgCalls
    try:
        from pytgcalls import AudioPiped, VideoPiped
    except Exception:
        # some builds keep these under types.input_stream
        from pytgcalls.types.input_stream import AudioPiped, VideoPiped
except Exception:
    # fallback to ntgcalls
    from ntgcalls import PyTgCalls  # type: ignore
    try:
        from ntgcalls import AudioPiped, VideoPiped  # type: ignore
    except Exception:
        from ntgcalls.types.input_stream import AudioPiped, VideoPiped  # type: ignore
    PYTG_BACKEND = "ntgcalls"


class Call:
    """
    Multi-assistant voice client manager.
    - Starts up to 5 userbot clients (from STRING1..STRING5)
    - Starts matching PyTgCalls/ntgcalls instances
    - Provides helpers to check VC status and stream audio/video
    """

    def __init__(self) -> None:
        self.userbots: List[Optional[Client]] = []
        self.calls: List[Optional[PyTgCalls]] = []

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
                self.calls.append(PyTgCalls(cli))
            else:
                self.userbots.append(None)
                self.calls.append(None)

        self.active_calls: set[int] = set()

    # ---------------- Core lifecycle ----------------

    async def start(self) -> None:
        """Start all available userbots and their group call clients."""
        LOGGER(__name__).info(f"Starting assistants using backend: {PYTG_BACKEND}")
        # Start pyrogram clients
        for cli in self.userbots:
            if cli and not cli.is_connected:
                await cli.start()

        # Start group call engines
        for call in self.calls:
            if call:
                await call.start()

        LOGGER(__name__).info("All available assistants and call engines started.")

    async def stop(self) -> None:
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

    # ---------------- Helpers ----------------

    def _pick_call(self) -> Optional[PyTgCalls]:
        """Pick the first available call engine."""
        for call in self.calls:
            if call is not None:
                return call
        return None

    async def get_call(self, chat_id: int):
        """
        Return call info for this chat, or None if there is no active VC.
        PyTgCalls 3.x exposes `get_call`. ntgcalls mirrors it; if not,
        we treat absence as 'no call'.
        """
        call = self._pick_call()
        if not call:
            return None
        try:
            return await call.get_call(chat_id)  # type: ignore[attr-defined]
        except AttributeError:
            # backend lacks get_call — consider no active call
            return None
        except Exception:
            return None

    async def ensure_vc(self, chat_id: int) -> bool:
        """Check if a VC is active in the chat (without relying on old exceptions)."""
        info = await self.get_call(chat_id)
        return bool(info)

    # ---------------- Streaming ----------------

    async def join(self, chat_id: int, source: str, video: bool = False) -> bool:
        """
        Join a VC and start streaming an audio (default) or video source.
        `source` can be a local file path or a URL handled by ffmpeg.
        """
        call = self._pick_call()
        if not call:
            LOGGER(__name__).error("No available call client (PyTgCalls/ntgcalls not initialized).")
            return False

        try:
            if video:
                stream = VideoPiped(source)
            else:
                stream = AudioPiped(source)

            await call.join_group_call(chat_id, stream)
            self.active_calls.add(chat_id)
            return True
        except FloodWait as e:
            await asyncio.sleep(e.value)
            return await self.join(chat_id, source, video)
        except ChatAdminRequired:
            LOGGER(__name__).error("Bot/assistant is not admin or lacks 'Manage Video Chats' permission.")
            return False
        except Exception as e:
            LOGGER(__name__).error(f"Failed to join/stream in chat {chat_id}: {e}")
            return False

    async def change_stream(self, chat_id: int, source: str, video: bool = False) -> bool:
        """
        Change the active stream in the VC.
        """
        call = self._pick_call()
        if not call:
            return False

        try:
            if video:
                stream = VideoPiped(source)
            else:
                stream = AudioPiped(source)

            # v3 exposes change_stream; if missing, re-join instead.
            if hasattr(call, "change_stream"):
                await call.change_stream(chat_id, stream)  # type: ignore[attr-defined]
            else:
                # Fallback: leave and re-join
                await self.leave(chat_id)
                await self.join(chat_id, source, video)
            return True
        except Exception as e:
            LOGGER(__name__).error(f"Failed to change stream in chat {chat_id}: {e}")
            return False

    async def leave(self, chat_id: int) -> bool:
        """
        Leave the VC for a chat.
        """
        call = self._pick_call()
        if not call:
            return False
        try:
            # Some backends expose leave_group_call, others stop_stream
            if hasattr(call, "leave_group_call"):
                await call.leave_group_call(chat_id)  # type: ignore[attr-defined]
            elif hasattr(call, "stop_stream"):
                await call.stop_stream(chat_id)  # type: ignore[attr-defined]
            self.active_calls.discard(chat_id)
            return True
        except Exception as e:
            LOGGER(__name__).error(f"Failed to leave VC in chat {chat_id}: {e}")
            return False

    # ---------------- High-level convenience used by your main.py ----------------

    async def stream_call(self, source: str, chat_id: Optional[int] = None, video: bool = False) -> bool:
        """
        High-level helper that either starts or switches the stream
        in the configured log chat (or provided chat_id).
        """
        # If you have a configured log group/channel ID for auto start:
        if chat_id is None and hasattr(config, "LOGGER_ID"):
            chat_id = int(getattr(config, "LOGGER_ID"))

        if chat_id is None:
            LOGGER(__name__).warning("No chat_id provided and config.LOGGER_ID is missing.")
            return False

        # If VC is already active, change the stream; else, join fresh
        if await self.ensure_vc(chat_id):
            return await self.change_stream(chat_id, source, video)
        return await self.join(chat_id, source, video)

    async def decorators(self):
        """
        Hook to register any event handlers / decorators you need elsewhere.
        Kept for interface compatibility with your existing code.
        """
        # You can add update listeners here if needed, e.g.:
        # call = self._pick_call()
        # if call and hasattr(call, "on_update"):
        #     @call.on_update()
        #     async def _(update):
        #         ...
        return


# Export singleton as in your original code
JARVIS = Call()
