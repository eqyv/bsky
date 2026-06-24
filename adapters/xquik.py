from typing import Optional, List, Dict, Any
import requests

from adapters.base import SocialAdapter
from utils.logger import logger


class XquikAdapter(SocialAdapter):
    """Target adapter for posting to X through the Xquik API."""

    def __init__(
        self,
        api_key: str,
        account: str,
        create_tweet_url: str = "https://xquik.com/api/v1/x/tweets",
    ):
        self.api_key = api_key
        self.account = account
        self.create_tweet_url = create_tweet_url

    def validate_credentials(self) -> bool:
        if not self.api_key:
            logger.error("❌ Xquik API key is missing.")
            return False
        if not self.account:
            logger.error("❌ Xquik account is missing.")
            return False
        return True

    def post(
        self,
        text: str,
        media_paths: Optional[List[str]] = None,
        media_urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Post to Xquik using text and public media URLs."""
        if not self.validate_credentials():
            return {"success": False, "url": None, "error": "Xquik credentials missing."}

        body: Dict[str, Any] = {
            "account": self.account,
            "text": text,
        }
        if media_urls:
            body["media"] = media_urls

        try:
            response = requests.post(
                self.create_tweet_url,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": self.api_key,
                },
                json=body,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            tweet_id = data.get("tweetId")
            tweet_url = (
                f"https://x.com/i/web/status/{tweet_id}"
                if tweet_id
                else None
            )
            logger.info(f"✅ Posted to Xquik: {tweet_url or 'tweet created'}")
            return {"success": True, "url": tweet_url, "error": None}
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Xquik request failed: {e}")
            return {"success": False, "url": None, "error": str(e)}
        except ValueError as e:
            logger.error(f"❌ Xquik returned invalid JSON: {e}")
            return {"success": False, "url": None, "error": str(e)}
