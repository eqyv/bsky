# adapters/instagram.py
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from utils.logger import logger
from adapters.base import SocialAdapter

try:
    from instagrapi import Client
    from instagrapi.exceptions import LoginRequired, ClientError
except ImportError:
    logger.error("instagrapi not installed. Run: pip install instagrapi")
    raise


class InstagramAdapter(SocialAdapter):
    """
    Instagram adapter using instagrapi with session persistence.
    No login on startup – we load a saved session.
    """

    def __init__(
        self,
        username: str,
        password: str,
        settings_file: str = "storage/instagram_settings.json"
    ):
        self.username = username
        self.password = password
        self.settings_file = Path(settings_file)
        self.client: Optional[Client] = None
        self._is_authenticated = False

    def _get_client(self) -> Client:
        if self.client is None:
            self.client = Client()
        return self.client

    def _save_session(self, client: Client) -> None:
        """Save session settings to file for future runs."""
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            settings = client.get_settings()
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2, default=str)
            logger.debug(f"Saved Instagram session to {self.settings_file}")
        except Exception as e:
            logger.warning(f"Failed to save Instagram session: {e}")

    def _load_session(self, client: Client) -> bool:
        """Load saved settings into the client. Returns True if successful."""
        if not self.settings_file.exists():
            return False
        try:
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
            client.set_settings(settings)
            logger.debug("Loaded Instagram session from settings file")
            return True
        except Exception as e:
            logger.warning(f"Failed to load Instagram settings: {e}")
            return False

    def validate_credentials(self) -> bool:
        """
        Attempt to restore session from saved settings.
        If that fails, fall back to a one-time login (first run).
        """
        client = self._get_client()

        # 1. Try loading saved session (no login)
        if self._load_session(client):
            # Validate with a light API call
            try:
                # Fetch own user ID (does not count as login)
                user_id = client.user_id
                if user_id:
                    self._is_authenticated = True
                    logger.success(f"✅ Instagram session restored successfully (user_id: {user_id})")
                    return True
            except Exception as e:
                logger.warning(f"Loaded session invalid, will re-login: {e}")
                # fall through to login

        # 2. No valid session – perform a one-time login (first run)
        logger.info("🔐 Performing one-time Instagram login to get fresh session...")
        try:
            client.login(self.username, self.password)
            # Save session for future runs
            self._save_session(client)
            self._is_authenticated = True
            logger.success(f"✅ Instagram login successful. Session saved.")
            return True
        except LoginRequired as e:
            logger.error(f"❌ Instagram login required (2FA or challenge): {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Instagram login failed: {e}")
            return False

    def post(
        self,
        text: str,
        media_paths: Optional[List[str]] = None,
        media_urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Post to Instagram using the authenticated session."""
        if not self._is_authenticated:
            if not self.validate_credentials():
                return {"success": False, "url": None, "error": "Instagram not authenticated"}

        client = self._get_client()

        try:
            # (same as before)
            if not media_paths:
                return {"success": False, "url": None, "error": "No media provided"}

            if len(media_paths) == 1:
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
                result = client.album_upload(media_paths, caption=text)
                media_id = result.id
                return {"success": True, "url": f"https://www.instagram.com/p/{media_id}/", "error": None}

        except LoginRequired as e:
            logger.error(f"❌ Instagram session expired: {e}")
            self._is_authenticated = False
            # Delete stale settings file to force re-login next time
            if self.settings_file.exists():
                self.settings_file.unlink()
            return {"success": False, "url": None, "error": "Session expired, please restart bot"}
        except ClientError as e:
            logger.error(f"❌ Instagram client error: {e}")
            return {"success": False, "url": None, "error": str(e)}
        except Exception as e:
            logger.error(f"❌ Unexpected error posting to Instagram: {e}")
            return {"success": False, "url": None, "error": str(e)}
