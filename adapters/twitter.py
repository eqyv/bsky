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
        auth_token: str = "",
        ct0: str = "",
    ):
        self.username = username
        self.email = email
        self.password = password
        self.totp_secret = totp_secret or None
        self.cookies_file = cookies_file
        self.auth_token = auth_token
        self.ct0 = ct0
        self.client: Optional[Client] = None
        self._is_authenticated = False

    def _verify_session(self, client: Client) -> bool:
        """Confirm the current cookies are a live, authenticated session."""
        try:
            user_id = _run_async(client.user_id())
            return bool(user_id)
        except Exception as e:
            logger.warning(f"X session check failed: {e}")
            return False

    def _get_client(self) -> Optional[Client]:
        if self.client is None:
            self.client = Client(language='en-US')
        return self.client

    def _save_cookies(self, client: Client) -> None:
        os.makedirs(os.path.dirname(self.cookies_file) or ".", exist_ok=True)
        client.save_cookies(self.cookies_file)

    def validate_credentials(self) -> bool:
        """
        Authenticate with X (Twitter), preferring cookie-based auth (which
        avoids X's Cloudflare-protected login endpoint — important on
        datacenter/VPS IPs). Order:
          1. Reuse a previously saved cookies file.
          2. Use auth_token + ct0 supplied via env (browser-exported cookies).
          3. Fall back to username/email/password login.
        """
        client = self._get_client()
        if not client:
            return False

        # 1. Reuse a saved session file (no network login).
        if os.path.exists(self.cookies_file):
            try:
                client.load_cookies(self.cookies_file)
                if self._verify_session(client):
                    self._is_authenticated = True
                    logger.success(f"✅ X (Twitter) session loaded for @{self.username}")
                    return True
                logger.warning("Saved X session expired; trying other methods.")
            except Exception as e:
                logger.warning(f"Saved X session invalid: {e}")

        # 2. Browser-exported cookies (auth_token + ct0) — bypasses login.
        if self.auth_token and self.ct0:
            try:
                client.set_cookies(
                    {"auth_token": self.auth_token, "ct0": self.ct0},
                    clear_cookies=True,
                )
                if self._verify_session(client):
                    self._save_cookies(client)
                    self._is_authenticated = True
                    logger.success(f"✅ X (Twitter) authenticated via cookies for @{self.username}")
                    return True
                logger.error("❌ X (Twitter) cookies (auth_token/ct0) are invalid or expired.")
            except Exception as e:
                logger.error(f"❌ X (Twitter) cookie auth failed: {e}")

        # 3. Fall back to credential login (may be Cloudflare-blocked on VPS IPs).
        if not self.password:
            logger.error("❌ X (Twitter) no valid cookies and no password set. Cannot authenticate.")
            return False
        logger.info("Attempting X (Twitter) password login (may be blocked on datacenter IPs)...")
        try:
            _run_async(client.login(
                auth_info_1=self.username,
                auth_info_2=self.email,
                password=self.password,
                totp_secret=self.totp_secret,
            ))

            self._save_cookies(client)
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
