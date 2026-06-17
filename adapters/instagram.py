# adapters/instagram.py
import requests
from typing import Optional, List, Dict, Any
from utils.logger import logger
from adapters.base import SocialAdapter

class InstagramAdapter(SocialAdapter):
    """Adapter for Instagram using the official Graph API."""

    def __init__(self, user_id: str, access_token: str):
        self.user_id = user_id
        self.access_token = access_token
        self.api_version = "v19.0"  # Using a recent version

    def validate_credentials(self) -> bool:
        """Validates the Instagram access token by attempting to get the user's media."""
        url = f"https://graph.facebook.com/{self.api_version}/{self.user_id}/media"
        params = {
            "access_token": self.access_token,
            "limit": 1
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if "data" in data:
                logger.success("✅ Instagram credentials validated successfully.")
                return True
            else:
                logger.error(f"❌ Instagram validation failed: {data}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Instagram validation request failed: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error validating Instagram credentials: {e}")
            return False

    def post(self, text: str, media_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Posts an image to Instagram."""
        if not media_paths:
            logger.error("Instagram API requires at least one media file.")
            return {"success": False, "url": None, "error": "No media provided for Instagram post."}

        # Instagram Graph API requires posting via URL, not direct file upload.
        # We need to host the image somewhere. For a simple bot, we can use a public URL.
        # Since we're downloading from Bluesky, we already have a URL.
        # We'll need to re-upload or use a temporary hosting service.
        # For Phase 2, we'll assume the media_paths are URLs.
        # In Phase 4, we'll implement a proper media hosting solution.
        # For now, we'll use the first media path as a URL.
        # Note: This is a simplification. In production, you'd need to upload to a hosting service.
        image_url = media_paths[0]

        # Step 1: Create a media container
        create_url = f"https://graph.facebook.com/{self.api_version}/{self.user_id}/media"
        create_payload = {
            "image_url": image_url,
            "caption": text,
            "access_token": self.access_token
        }

        try:
            create_response = requests.post(create_url, data=create_payload)
            create_response.raise_for_status()
            create_result = create_response.json()

            if "id" not in create_result:
                logger.error(f"❌ Instagram media container creation failed: {create_result}")
                return {"success": False, "url": None, "error": f"Container creation failed: {create_result}"}

            creation_id = create_result["id"]
            logger.debug(f"Instagram media container created: {creation_id}")

            # Step 2: Publish the container
            publish_url = f"https://graph.facebook.com/{self.api_version}/{self.user_id}/media_publish"
            publish_payload = {
                "creation_id": creation_id,
                "access_token": self.access_token
            }

            publish_response = requests.post(publish_url, data=publish_payload)
            publish_response.raise_for_status()
            publish_result = publish_response.json()

            if "id" in publish_result:
                post_id = publish_result["id"]
                post_url = f"https://www.instagram.com/p/{post_id}/"
                logger.info(f"✅ Posted to Instagram: {post_url}")
                return {"success": True, "url": post_url, "error": None}
            else:
                logger.error(f"❌ Instagram publish failed: {publish_result}")
                return {"success": False, "url": None, "error": f"Publish failed: {publish_result}"}

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Instagram API request failed: {e}")
            return {"success": False, "url": None, "error": f"API request failed: {e}"}
        except Exception as e:
            logger.error(f"❌ Unexpected error posting to Instagram: {e}")
            return {"success": False, "url": None, "error": f"Unexpected error: {e}"}
