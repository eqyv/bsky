# adapters/twitter.py
import asyncio
import os
from typing import Optional, List, Dict, Any
from twikit import Client
from twikit.errors import Unauthorized, TwitterException
from utils.logger import logger
from adapters.base import SocialAdapter
from adapters import twitter_patch

# Patch twikit's client-transaction-id logic for X's current page format.
twitter_patch.apply()


def _run_async(coro):
    """
    Run an async coroutine from sync code, whether or not an event loop is
    already running in this thread.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop in this thread — the normal case.
        return asyncio.run(coro)

    # A loop is already running; we can't reuse it from sync code, so run the
    # coroutine to completion on a fresh, isolated loop.
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TwitterAdapter(SocialAdapter):
    """
    Adapter for X (Twitter) using the twikit login method.
    Uses username/email + password (and optional TOTP) and persists the
    session to a cookies file so subsequent runs reuse it instead of logging
    in fresh every time.
    """

    def __init__(
        self,
        username: str,
        email: str,
        password: str,
        totp_secret: str = "",
        cookies_file: str = "storage/twitter_cookies.json",
    ):
        self.username = username
        self.email = email
        self.password = password
        self.totp_secret = totp_secret or None
        self.cookies_file = cookies_file
        self.client: Optional[Client] = None
        self._is_authenticated = False

    def _get_client(self) -> Optional[Client]:
        if self.client is None:
            self.client = Client(language='en-US')
        return self.client

    def validate_credentials(self) -> bool:
        """
        Authenticate with X (Twitter). If a saved cookies file exists, reuse
        that session; otherwise log in with credentials and save the cookies.
        """
        client = self._get_client()
        if not client:
            return False

        # 1. Try reusing a saved session (no login request).
        if os.path.exists(self.cookies_file):
            try:
                client.load_cookies(self.cookies_file)
                self._is_authenticated = True
                logger.success(f"✅ X (Twitter) session loaded for @{self.username}")
                return True
            except Exception as e:
                logger.warning(f"Saved X session invalid, will re-login: {e}")

        # 2. Fresh login with credentials.
        try:
            _run_async(client.login(
                auth_info_1=self.username,
                auth_info_2=self.email,
                password=self.password,
                totp_secret=self.totp_secret,
            ))

            os.makedirs(os.path.dirname(self.cookies_file) or ".", exist_ok=True)
            client.save_cookies(self.cookies_file)

            self._is_authenticated = True
            logger.success(f"✅ X (Twitter) login successful for @{self.username}")
            return True

        except Unauthorized as e:
            logger.error(f"❌ X (Twitter) login failed (unauthorized): {e}")
            return False
        except TwitterException as e:
            logger.error(f"❌ X (Twitter) API error during login: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ X (Twitter) unexpected error during login: {e}")
            return False

    def post(self, text: str, media_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Posts a tweet with optional media.
        """
        if not self._is_authenticated:
            if not self.validate_credentials():
                return {"success": False, "url": None, "error": "X (Twitter) authentication failed."}

        client = self._get_client()
        if not client:
            return {"success": False, "url": None, "error": "X (Twitter) client not initialized."}

        try:
            media_ids = []
            if media_paths:
                for path in media_paths:
                    media_id = _run_async(client.upload_media(path))
                    media_ids.append(media_id)
                    logger.debug(f"Uploaded media for X: {path} -> ID: {media_id}")

            tweet = _run_async(client.create_tweet(text=text, media_ids=media_ids))

            tweet_id = tweet.id
            tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"

            logger.info(f"✅ Posted to X (Twitter): {tweet_url}")
            return {"success": True, "url": tweet_url, "error": None}

        except Unauthorized as e:
            logger.error(f"❌ X (Twitter) Unauthorized (session expired?): {e}")
            self._is_authenticated = False
            # Drop the stale cookies so the next attempt logs in fresh.
            try:
                if os.path.exists(self.cookies_file):
                    os.remove(self.cookies_file)
            except OSError:
                pass
            return {"success": False, "url": None, "error": "X (Twitter) session expired. Re-login required."}
        except TwitterException as e:
            logger.error(f"❌ X (Twitter) API error: {e}")
            return {"success": False, "url": None, "error": f"X (Twitter) API error: {e}"}
        except Exception as e:
            logger.error(f"❌ Unexpected error posting to X (Twitter): {e}")
            return {"success": False, "url": None, "error": f"Unexpected error: {e}"}
