import time
import os
import hashlib
import logging
import httpx
from pypresence import AioPresence
from typing import Optional
from ..config import IMAGE_HOSTER, COPYPARTY_URL, COPYPARTY_USER, COPYPARTY_PWD, IMGUR_CLIENT_ID
from ..utils.logger import get_logger

logger = get_logger(__name__)

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
        """Upload thumbnail to configured hoster and return the public URL."""
        if not thumbnail_path or not os.path.exists(thumbnail_path):
            return None
            
        if thumbnail_path in self._upload_cache:
            return self._upload_cache[thumbnail_path]

        if IMAGE_HOSTER == "imgur":
            url = await self._upload_to_imgur(thumbnail_path)
        else:
            url = await self._upload_to_copyparty(thumbnail_path)
        
        if url:
            self._upload_cache[thumbnail_path] = url
        return url

    async def _upload_to_imgur(self, thumbnail_path: str) -> Optional[str]:
        """Upload thumbnail to Imgur."""
        if not IMGUR_CLIENT_ID:
            logger.error("Imgur Client ID not configured!")
            return None
            
        try:
            async with httpx.AsyncClient() as client:
                with open(thumbnail_path, "rb") as f:
                    content = f.read()
                
                headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}
                files = {"image": content}
                
                response = await client.post("https://api.imgur.com/3/image", headers=headers, files=files)
                
                if response.status_code == 200:
                    data = response.json()
                    url = data.get("data", {}).get("link")
                    if url:
                        logger.info(f"Successfully uploaded thumbnail to Imgur: {url}")
                        return url
                
                logger.error(f"Failed to upload to Imgur: {response.status_code} {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error during Imgur upload: {e}")
            return None

    async def _upload_to_copyparty(self, thumbnail_path: str) -> Optional[str]:
        """Upload thumbnail to Copyparty."""
        try:
            # Generate a unique filename based on content to avoid duplicates
            with open(thumbnail_path, "rb") as f:
                content = f.read()
                file_hash = hashlib.md5(content).hexdigest()
                ext = os.path.splitext(thumbnail_path)[1]
                filename = f"rpc_{file_hash}{ext}"

            # Prepare Copyparty upload
            base_url = COPYPARTY_URL.rstrip("/")
            upload_url = f"{base_url}/{filename}?want=url"
            
            headers = {"replace": "1"}
            auth = (COPYPARTY_USER, COPYPARTY_PWD) if COPYPARTY_USER and COPYPARTY_PWD else None

            async with httpx.AsyncClient() as client:
                response = await client.put(upload_url, content=content, auth=auth, headers=headers)
                
                if response.status_code in [200, 201]:
                    returned_url = response.text.strip()
                    if returned_url.startswith("/"):
                        from urllib.parse import urlparse
                        parsed_base = urlparse(COPYPARTY_URL)
                        final_url = f"{parsed_base.scheme}://{parsed_base.netloc}{returned_url}"
                    elif "://" not in returned_url:
                        final_url = f"{base_url}/{returned_url}"
                    else:
                        final_url = returned_url

                    logger.info(f"Successfully uploaded thumbnail to Copyparty: {final_url}")
                    return final_url
                else:
                    logger.error(f"Failed to upload to Copyparty: {response.status_code} {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Error during Copyparty upload: {e}")
            return None

    async def update_presence(self, series: str, episode: str, player: str, 
                               thumbnail_path: Optional[str] = None,
                               cached_thumbnail_url: Optional[str] = None,
                               duration: float = 0,
                               start_offset: float = 0,
                               is_paused: bool = False) -> Optional[str]:
        """Update Discord presence and return the uploaded thumbnail URL if any."""
        if not self.connected:
            await self.connect()
            if not self.connected:
                return None

        logger.debug(f"Updating Discord presence: {series} - {episode}")
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
            
            final_thumbnail_url = cached_thumbnail_url

            # Attempt to use thumbnail as large image
            if not final_thumbnail_url and thumbnail_path:
                final_thumbnail_url = await self._upload_thumbnail(thumbnail_path)
            
            if final_thumbnail_url:
                large_image = final_thumbnail_url
                large_text = f"Watching: {series}"
                small_image = player_icon
                small_text = f"Playing in {player.upper()}"
            
            # Timestamps
            start_timestamp = None
            end_timestamp = None
            
            state_prefix = ""
            if is_paused:
                state_prefix = "(Paused) "
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
            return final_thumbnail_url
        except Exception as e:
            logger.error(f"Error updating Discord presence: {e}")
            self.connected = False
            return None

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
