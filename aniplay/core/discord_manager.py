import time
import logging  # noqa: F401
import asyncio  # noqa: F401
from pypresence import AioPresence
from typing import Optional  # noqa: F401

class DiscordManager:
    CLIENT_ID = "1440472840578142381"

    def __init__(self):
        self.rpc = None
        self.connected = False
        self.current_series = ""
        self.current_episode = ""
        self.start_time = None
        self.vlc_image = "https://upload.wikimedia.org/wikipedia/commons/0/0d/VLC_for_iOS_Icon.png"
        self.mpv_image = "https://upload.wikimedia.org/wikipedia/commons/7/73/Mpv_logo_%28official%29.png"

    async def connect(self):
        if self.connected:
            return
        try:
            self.rpc = AioPresence(self.CLIENT_ID)
            await self.rpc.connect()
            self.connected = True
        except Exception as e:
            print(f"Could not connect to Discord: {e}")
            self.connected = False

    async def update_presence(self, series: str, episode: str, player: str):
        if not self.connected:
            await self.connect()
            if not self.connected:
                return

        if series != self.current_series or episode != self.current_episode:
            self.current_series = series
            self.current_episode = episode
            self.start_time = int(time.time())

        try:
            large_image = self.vlc_image if player.lower() == "vlc" else self.mpv_image
            
            await self.rpc.update(
                state=f"Watching: {episode}",
                details=series,
                start=self.start_time,
                large_image=large_image,
                large_text=f"Playing in {player.upper()}",
            )
        except Exception as e:
            print(f"Error updating Discord presence: {e}")
            self.connected = False

    async def clear(self):
        if self.connected and self.rpc:
            try:
                await self.rpc.clear()
            except Exception:
                pass

    async def shutdown(self):
        if self.connected and self.rpc:
            try:
                await self.rpc.close()
            except Exception:
                pass
            self.connected = False
