import time
import os
import hashlib
import logging
import httpx
from pypresence import AioPresence
from typing import Optional
from ..config import COPYPARTY_URL, COPYPARTY_USER, COPYPARTY_PWD

logger = logging.getLogger(__name__)

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
        self._upload_cache = {} # path -> url

    async def connect(self):
        if self.connected:
            return
        try:
            self.rpc = AioPresence(self.CLIENT_ID)
            await self.rpc.connect()
            self.connected = True
        except Exception as e:
            logger.error(f"Could not connect to Discord: {e}")
            self.connected = False

    async def _upload_thumbnail(self, thumbnail_path: str) -> Optional[str]:
        """Upload thumbnail to Copyparty and return the public URL."""
        if not thumbnail_path or not os.path.exists(thumbnail_path):
            return None
            
        if thumbnail_path in self._upload_cache:
            return self._upload_cache[thumbnail_path]

        try:
            # Generate a unique filename based on content to avoid duplicates
            with open(thumbnail_path, "rb") as f:
                content = f.read()
                file_hash = hashlib.md5(content).hexdigest()
                ext = os.path.splitext(thumbnail_path)[1]
                filename = f"rpc_{file_hash}{ext}"

            # Prepare Copyparty upload
            # Adding want=url to get back the confirmation
            base_url = COPYPARTY_URL.rstrip("/")
            upload_url = f"{base_url}/{filename}?want=url"
            
            headers = {
                "replace": "1"  # Overwrite if exists
            }
            
            auth = None
            if COPYPARTY_USER and COPYPARTY_PWD:
                auth = (COPYPARTY_USER, COPYPARTY_PWD)

            async with httpx.AsyncClient() as client:
                # Copyparty accepts PUT for direct file creation
                response = await client.put(upload_url, content=content, auth=auth, headers=headers)
                
                if response.status_code in [200, 201]:
                    # want=url should return the URL of the uploaded file
                    returned_url = response.text.strip()
                    
                    # If it's a relative URL, prepend the domain/scheme
                    if returned_url.startswith("/"):
                        from urllib.parse import urlparse
                        parsed_base = urlparse(COPYPARTY_URL)
                        final_url = f"{parsed_base.scheme}://{parsed_base.netloc}{returned_url}"
                    elif "://" not in returned_url:
                        # Probably just the filename
                        final_url = f"{base_url}/{returned_url}"
                    else:
                        final_url = returned_url

                    logger.info(f"Successfully uploaded thumbnail to {final_url}")
                    self._upload_cache[thumbnail_path] = final_url
                    return final_url
                else:
                    logger.error(f"Failed to upload thumbnail to Copyparty: {response.status_code} {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Error during thumbnail upload: {e}")
            return None

    async def update_presence(self, series: str, episode: str, player: str, 
                              thumbnail_path: Optional[str] = None,
                              duration: float = 0,
                              start_offset: float = 0,
                              is_paused: bool = False):
        if not self.connected:
            await self.connect()
            if not self.connected:
                return

        if series != self.current_series or episode != self.current_episode:
            self.current_series = series
            self.current_episode = episode
            self.start_time = int(time.time())

        try:
            player_icon = self.vlc_image if "vlc" in player.lower() else self.mpv_image
            
            # Default images
            large_image = player_icon
            small_image = None
            large_text = f"Playing in {player.upper()}"
            small_text = None

            # Attempt to use thumbnail as large image
            if thumbnail_path:
                uploaded_url = await self._upload_thumbnail(thumbnail_path)
                if uploaded_url:
                    large_image = uploaded_url
                    large_text = f"Watching: {series}"
                    small_image = player_icon
                    small_text = f"Playing in {player.upper()}"
            
            # Timestamps (start=end style)
            start_timestamp = None
            end_timestamp = None
            
            state_prefix = ""
            if is_paused:
                state_prefix = "(Paused) "
                # No timestamps when paused to "stop" the clock
            elif duration > 0:
                now = int(time.time())
                start_timestamp = now - int(start_offset)
                end_timestamp = now + int(duration - start_offset)
            else:
                start_timestamp = self.start_time

            await self.rpc.update(
                state=f"{state_prefix}Watching: {episode}",
                details=series,
                start=start_timestamp,
                end=end_timestamp,
                large_image=large_image,
                large_text=large_text,
                small_image=small_image,
                small_text=small_text
            )
        except Exception as e:
            logger.error(f"Error updating Discord presence: {e}")
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
