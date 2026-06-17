# adapters/twitter.py
import asyncio
from typing import Optional, List, Dict, Any
from twikit import Client
from twikit.errors import Unauthorized, TwitterException
from utils.logger import logger
from adapters.base import SocialAdapter


class TwitterAdapter(SocialAdapter):
    """
    Adapter for X (Twitter) using the official twikit login method.
    This uses username/email + password and handles the authentication flow.
    """

    def __init__(self, username: str, email: str, password: str):
        self.username = username
        self.email = email
        self.password = password
        self.client: Optional[Client] = None
        self._is_authenticated = False

    def _get_client(self) -> Optional[Client]:
        if self.client is None:
            self.client = Client(language='en-US')
        return self.client

    def validate_credentials(self) -> bool:
        """
        Authenticates with X (Twitter) using username/email and password.
        twikit handles the session cookies automatically.
        """
        client = self._get_client()
        if not client:
            return False

        try:
            # Using asyncio.run() because twikit's login is async
            # If we're already in an async loop, handle gracefully
            try:
                loop = asyncio.get_running_loop()
                # If we're in an async loop, we can't use asyncio.run() again.
                # We'll create a new event loop or use a workaround.
                # For simplicity, we'll just run it in a new loop.
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(client.login(self.username, self.email, self.password))
                loop.close()
            except RuntimeError:
                # No running loop, use asyncio.run()
                asyncio.run(client.login(self.username, self.email, self.password))

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
                    # upload_media is synchronous in recent twikit
                    media_id = client.upload_media(path)
                    media_ids.append(media_id)
                    logger.debug(f"Uploaded media for X: {path} -> ID: {media_id}")

            # Create the tweet (async)
            try:
                loop = asyncio.get_running_loop()
                # If already in an async loop, we need to handle it differently.
                # For now, we'll use a new loop.
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                tweet = loop.run_until_complete(client.create_tweet(text=text, media_ids=media_ids))
                loop.close()
            except RuntimeError:
                tweet = asyncio.run(client.create_tweet(text=text, media_ids=media_ids))

            tweet_id = tweet.id
            tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"

            logger.info(f"✅ Posted to X (Twitter): {tweet_url}")
            return {"success": True, "url": tweet_url, "error": None}

        except Unauthorized as e:
            logger.error(f"❌ X (Twitter) Unauthorized (session expired?): {e}")
            self._is_authenticated = False
            return {"success": False, "url": None, "error": "X (Twitter) session expired. Re-login required."}
        except TwitterException as e:
            logger.error(f"❌ X (Twitter) API error: {e}")
            return {"success": False, "url": None, "error": f"X (Twitter) API error: {e}"}
        except Exception as e:
            logger.error(f"❌ Unexpected error posting to X (Twitter): {e}")
            return {"success": False, "url": None, "error": f"Unexpected error: {e}"}
