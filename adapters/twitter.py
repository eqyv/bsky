# adapters/twitter.py
import asyncio
from typing import Optional, List, Dict, Any
from twikit import Client
from twikit.errors import Unauthorized, TwitterException, NotFound
from utils.logger import logger
from adapters.base import SocialAdapter


class TwitterAdapter(SocialAdapter):
    """Adapter for X (Twitter) using the unofficial twikit library."""

    def __init__(self, auth_token: str, ct0: str, username: str):
        self.auth_token = auth_token
        self.ct0 = ct0
        self.username = username
        self.client: Optional[Client] = None
        self._is_authenticated = False
        self._user_id: Optional[str] = None

    def _get_client(self) -> Optional[Client]:
        """Initializes and returns a twikit Client with a realistic User-Agent."""
        if self.client is None:
            # Set a realistic User-Agent to avoid being blocked
            # Using a recent Chrome on Windows User-Agent
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            self.client = Client(language='en-US', user_agent=user_agent)
        return self.client

    def validate_credentials(self) -> bool:
        """
        Validates X cookies by fetching your own user profile using the username.
        This works around the broken client.user() endpoint.
        """
        client = self._get_client()
        if not client:
            return False

        cookies = {
            'auth_token': self.auth_token,
            'ct0': self.ct0
        }

        try:
            client.set_cookies(cookies)

            # Workaround: use get_user_by_screen_name with your own username
            # instead of client.user() which is currently broken (returns 404)
            try:
                loop = asyncio.get_running_loop()
                user = asyncio.run(client.get_user_by_screen_name(self.username))
            except RuntimeError:
                user = asyncio.run(client.get_user_by_screen_name(self.username))

            if user and hasattr(user, 'id'):
                self._user_id = user.id
                self._is_authenticated = True
                logger.success(f"✅ X (Twitter) cookies valid. User: @{user.screen_name} (ID: {user.id})")
                return True
            else:
                logger.error("❌ X (Twitter) cookies invalid (could not fetch user)")
                return False

        except NotFound as e:
            logger.error(f"❌ X (Twitter) username '{self.username}' not found: {e}")
            return False
        except Unauthorized as e:
            logger.error(f"❌ X (Twitter) cookies expired or invalid: {e}")
            return False
        except TwitterException as e:
            logger.error(f"❌ X (Twitter) API error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ X (Twitter) validation error: {e}")
            return False

    def post(self, text: str, media_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Posts a tweet with optional media."""
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
                    media_id = client.upload_media(path)
                    media_ids.append(media_id)
                    logger.debug(f"Uploaded media for X: {path} -> ID: {media_id}")

            # Create the tweet
            try:
                loop = asyncio.get_running_loop()
                tweet = asyncio.run(client.create_tweet(text=text, media_ids=media_ids))
            except RuntimeError:
                tweet = asyncio.run(client.create_tweet(text=text, media_ids=media_ids))

            tweet_id = tweet.id
            tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"

            logger.info(f"✅ Posted to X (Twitter): {tweet_url}")
            return {"success": True, "url": tweet_url, "error": None}

        except Unauthorized as e:
            logger.error(f"❌ X (Twitter) Unauthorized (cookies expired?): {e}")
            self._is_authenticated = False
            return {"success": False, "url": None, "error": "X (Twitter) authentication failed. Cookies may be expired."}
        except TwitterException as e:
            logger.error(f"❌ X (Twitter) API error: {e}")
            return {"success": False, "url": None, "error": f"X (Twitter) API error: {e}"}
        except Exception as e:
            logger.error(f"❌ Unexpected error posting to X (Twitter): {e}")
            return {"success": False, "url": None, "error": f"Unexpected error: {e}"}
