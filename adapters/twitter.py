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


# A single, persistent event loop reused for every twikit call.
#
# We must NOT use asyncio.run() (which creates and *closes* a fresh loop each
# call): twikit's underlying httpx.AsyncClient binds its connection pool to the
# loop it first ran on. Closing the loop between calls — e.g. between
# upload_media() and create_tweet() when posting media — invalidates those
# connections and raises "Event loop is closed" on the next call. A persistent
# loop keeps the connection pool valid across calls.
_EVENT_LOOP: Optional[asyncio.AbstractEventLoop] = None


def _run_async(coro):
    """Run a coroutine to completion on a persistent, shared event loop."""
    global _EVENT_LOOP
    if _EVENT_LOOP is None or _EVENT_LOOP.is_closed():
        _EVENT_LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_EVENT_LOOP)
    return _EVENT_LOOP.run_until_complete(coro)


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
        """
        Confirm the current cookies are a live, authenticated session.

        We use the raw GraphQL user-by-screen-name endpoint instead of twikit's
        user_id()/user() helpers: those hit a dead v1.1 endpoint (404) or crash
        in twikit's object parsers against X's current response schema, which
        produces false "session invalid" results even when auth is fine.
        Reaching authenticated user data is what proves the cookies work.
        """
        if not self.username:
            # No handle to probe with; trust the cookies and let post() surface
            # any real auth error.
            return True
        try:
            data, _ = _run_async(client.gql.user_by_screen_name(self.username))
            result = (data or {}).get("data", {}).get("user", {}).get("result", {})
            screen_name = (
                result.get("legacy", {}).get("screen_name")
                or result.get("core", {}).get("screen_name")
            )
            return bool(screen_name)
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

    def _create_tweet_raw(self, client: Client, text: str, media_ids: List[str]) -> str:
        """
        Post a tweet via twikit's raw GraphQL layer and return the tweet id.

        We deliberately bypass twikit's high-level create_tweet() return value,
        which builds a Tweet object through parsers that crash on X's current
        response schema (the same class of bug that breaks user lookups). The
        raw call returns the posted tweet's id directly, so a parser bug can't
        make a *successful* post look like a failure (which would risk a
        duplicate post on retry).
        """
        media_entities = [
            {"media_id": media_id, "tagged_users": []} for media_id in media_ids
        ]
        # Positional args mirror twikit.client.gql.GQLClient.create_tweet:
        # is_note_tweet, text, media_entities, poll_uri, reply_to,
        # attachment_url, community_id, share_with_followers, richtext_options,
        # edit_tweet_id, limit_mode
        response, _ = _run_async(client.gql.create_tweet(
            False, text, media_entities, None, None,
            None, None, False, None, None, None,
        ))
        if isinstance(response, dict) and response.get("errors"):
            raise TwitterException(response["errors"])
        result = response["data"]["create_tweet"]["tweet_results"]["result"]
        return result["rest_id"]

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

            tweet_id = self._create_tweet_raw(client, text, media_ids)
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
