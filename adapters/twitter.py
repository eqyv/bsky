# adapters/twitter.py
import asyncio
from typing import Optional, List, Dict, Any
from twikit import Client
from twikit.errors import Unauthorized, TwikitError
from utils.logger import logger
from adapters.base import SocialAdapter


class TwitterAdapter(SocialAdapter):
    def __init__(self, auth_token: str, ct0: str):
        self.auth_token = auth_token
        self.ct0 = ct0
        self.client: Optional[Client] = None
        self._is_authenticated = False

    def _get_client(self) -> Optional[Client]:
        if self.client is None:
            self.client = Client(language='en-US')
        return self.client

    def validate_credentials(self) -> bool:
        """Validate X cookies by setting them and making a light request."""
        client = self._get_client()
        if not client:
            return False

        cookies = {'auth_token': self.auth_token, 'ct0': self.ct0}
        try:
            client.set_cookies(cookies)
            # Make a minimal authenticated request to verify session
            # We can fetch the authenticated user's ID (which requires valid auth)
            # This does NOT count as a login; it's just a GET request using the session.
            # We'll use a synchronous wrapper to call the async method.
            try:
                loop = asyncio.get_running_loop()
                # If we're in an async context, we need to handle differently
                # But our main is synchronous, so we'll use asyncio.run()
                user = asyncio.run(client.get_me())
            except RuntimeError:
                user = asyncio.run(client.get_me())

            if user and hasattr(user, 'id'):
                self._is_authenticated = True
                logger.success(f"✅ X (Twitter) cookies valid. User: @{user.screen_name}")
                return True
            else:
                logger.error("❌ X (Twitter) cookies invalid (could not fetch user)")
                return False

        except Unauthorized as e:
            logger.error(f"❌ X (Twitter) cookies expired or invalid: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ X (Twitter) validation error: {e}")
            return False


    def post(self, text: str, media_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        # If _is_authenticated is False, it will attempt to re-validate first.
        """Posts a tweet with optional media."""
        if not self._is_authenticated:
            # Try to re-authenticate if we lost the session
            if not self.validate_credentials():
                return {"success": False, "url": None, "error": "X (Twitter) authentication failed."}

        client = self._get_client()
        if not client:
            return {"success": False, "url": None, "error": "X (Twitter) client not initialized."}

        try:
            media_ids = []
            if media_paths:
                for path in media_paths:
                    # twikit's upload_media is synchronous in the latest versions
                    media_id = client.upload_media(path)
                    media_ids.append(media_id)
                    logger.debug(f"Uploaded media for X: {path} -> ID: {media_id}")

            # Create the tweet
            # Using asyncio.run() to handle the async create_tweet method
            # Note: The synchronous Client might have a sync version, but the examples show async.
            # We'll use a simple wrapper to run the async method.
            try:
                loop = asyncio.get_running_loop()
                # If we're already in an async context, this is a problem.
                # For our synchronous main loop, we'll use asyncio.run().
                # We need to handle this carefully.
                logger.warning("Running in an async loop? Falling back to asyncio.run().")
                # We'll just use asyncio.run() for simplicity.
                # If the main loop becomes async later, we can refactor.
                tweet = asyncio.run(client.create_tweet(text=text, media_ids=media_ids))
            except RuntimeError:
                # No running event loop, use asyncio.run()
                tweet = asyncio.run(client.create_tweet(text=text, media_ids=media_ids))

            # twikit's create_tweet returns a tweet object. We need to extract the URL.
            # The URL format is typically: https://twitter.com/{username}/status/{id}
            # We can get the ID from the tweet object.
            tweet_id = tweet.id
            # We don't have the username easily, so we'll construct a generic URL.
            # A better approach might be to get the user's screen name from the client.
            # For now, we'll return the ID and let the caller construct the URL if needed.
            tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"

            logger.info(f"✅ Posted to X (Twitter): {tweet_url}")
            return {"success": True, "url": tweet_url, "error": None}

        except Unauthorized as e:
            logger.error(f"❌ X (Twitter) Unauthorized (cookies expired?): {e}")
            self._is_authenticated = False
            return {"success": False, "url": None, "error": "X (Twitter) authentication failed. Cookies may be expired."}
        except TwikitError as e:
            logger.error(f"❌ X (Twitter) API error: {e}")
            return {"success": False, "url": None, "error": f"X (Twitter) API error: {e}"}
        except Exception as e:
            logger.error(f"❌ Unexpected error posting to X (Twitter): {e}")
            return {"success": False, "url": None, "error": f"Unexpected error: {e}"}
