# adapters/instagram.py
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
from utils.logger import logger
from adapters.base import SocialAdapter

try:
    from instagrapi import Client
    from instagrapi.exceptions import LoginRequired, ClientError
except ImportError:
    logger.error("instagrapi not installed. Run: pip install instagrapi")
    raise


class InstagramAdapter(SocialAdapter):
    """Adapter for Instagram using instagrapi (unofficial, cookie-based)."""

    def __init__(
        self,
        sessionid: str,
        csrftoken: str,
        ds_user_id: str,
        settings_file: Optional[str] = None
    ):
        """
        Initialize Instagram adapter with cookies.

        Args:
            sessionid: The sessionid cookie from browser
            csrftoken: The csrftoken cookie from browser
            ds_user_id: The ds_user_id cookie from browser
            settings_file: Optional path to save/load session settings
        """
        self.sessionid = sessionid
        self.csrftoken = csrftoken
        self.ds_user_id = ds_user_id
        self.settings_file = settings_file or "storage/instagram_settings.json"
        self.client: Optional[Client] = None
        self._is_authenticated = False

    def _get_client(self) -> Client:
        """Get or create instagrapi client."""
        if self.client is None:
            self.client = Client()
        return self.client

    def validate_credentials(self) -> bool:
        """Validate Instagram cookies by attempting to load session."""
        client = self._get_client()

        # Try to load saved settings first (session persistence)
        if Path(self.settings_file).exists():
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                client.set_settings(settings)
                logger.debug("Loaded Instagram session from settings file")
            except Exception as e:
                logger.warning(f"Failed to load Instagram settings: {e}")

        # Set cookies directly on the client
        # instagrapi uses a cookie jar; we need to set them properly
        try:
            # Method 1: Use login with sessionid (recommended)
            # instagrapi can login using just the sessionid
            client.login_by_sessionid(self.sessionid)
            self._is_authenticated = True
            logger.success("✅ Instagram login successful (via sessionid)")

            # Save settings for future use
            self._save_settings(client)
            return True

        except LoginRequired as e:
            logger.error(f"❌ Instagram login required (session expired): {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Instagram login failed: {e}")
            return False

    def _save_settings(self, client: Client) -> None:
        """Save session settings to file for persistence."""
        try:
            settings = client.get_settings()
            Path(self.settings_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2, default=str)
            logger.debug(f"Saved Instagram session settings to {self.settings_file}")
        except Exception as e:
            logger.warning(f"Failed to save Instagram settings: {e}")

    def post(self, text: str, media_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Post to Instagram using instagrapi.

        Supports:
        - Single photo
        - Single video
        - Album (carousel) with multiple photos/videos
        """
        if not self._is_authenticated:
            if not self.validate_credentials():
                return {"success": False, "url": None, "error": "Instagram authentication failed"}

        client = self._get_client()

        try:
            if not media_paths:
                # Text-only post (Instagram requires media, so this will fail)
                logger.error("Instagram requires at least one media file")
                return {"success": False, "url": None, "error": "No media provided"}

            if len(media_paths) == 1:
                # Single photo or video
                path = media_paths[0]
                if path.lower().endswith(('.mp4', '.mov', '.avi', '.webm')):
                    result = client.video_upload(path, caption=text)
                else:
                    result = client.photo_upload(path, caption=text)
                media_id = result.id
                logger.info(f"✅ Posted to Instagram: https://www.instagram.com/p/{media_id}/")
                return {
                    "success": True,
                    "url": f"https://www.instagram.com/p/{media_id}/",
                    "error": None
                }

            else:
                # Album (carousel) with multiple media
                # instagrapi supports album_upload with list of paths
                result = client.album_upload(media_paths, caption=text)
                media_id = result.id
                logger.info(f"✅ Posted album to Instagram: https://www.instagram.com/p/{media_id}/")
                return {
                    "success": True,
                    "url": f"https://www.instagram.com/p/{media_id}/",
                    "error": None
                }

        except LoginRequired as e:
            logger.error(f"❌ Instagram session expired: {e}")
            self._is_authenticated = False
            return {"success": False, "url": None, "error": "Session expired, please re-authenticate"}
        except ClientError as e:
            logger.error(f"❌ Instagram client error: {e}")
            return {"success": False, "url": None, "error": str(e)}
        except Exception as e:
            logger.error(f"❌ Unexpected error posting to Instagram: {e}")
            return {"success": False, "url": None, "error": str(e)}
