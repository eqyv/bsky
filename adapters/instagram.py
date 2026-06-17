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
        self.api_version = "v19.0"

    def validate_credentials(self) -> bool:
        """Validates the Instagram access token."""
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

    def _upload_local_file(self, file_path: str) -> Optional[str]:
        """
        Upload a local file to a hosting service to get a public URL.
        For Phase 3, we'll log a warning and return None.
        In Phase 4, we'll implement a proper solution.
        """
        # For now, we can't upload local files directly to Instagram's API.
        # Instagram requires a publicly accessible URL.
        # We have a few options:
        # 1. Use imgbb.com or similar free image hosting API
        # 2. Use our own server/CDN
        # 3. Use the Bluesky CDN URL directly (it's publicly accessible)
        logger.error("Instagram does not support local file uploads directly.")
        logger.error("You need to host the image at a public URL.")
        logger.error("For now, please ensure your Bluesky images have public URLs.")
        return None

    def post(self, text: str, media_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Posts an image to Instagram."""
        if not media_paths:
            logger.error("Instagram API requires at least one media file.")
            return {"success": False, "url": None, "error": "No media provided for Instagram post."}

        # Instagram Graph API requires a publicly accessible URL
        # For now, we'll assume media_paths[0] is already a URL (from Bluesky's CDN)
        # In Phase 3, media_paths will be local files, but we'll handle that.

        image_url = media_paths[0]

        # Check if it's a local file path
        if not image_url.startswith(('http://', 'https://')):
            logger.warning(f"Media path is not a URL: {image_url}")
            uploaded_url = self._upload_local_file(image_url)
            if not uploaded_url:
                return {"success": False, "url": None, "error": "Cannot upload local file. Need a public URL."}
            image_url = uploaded_url

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
