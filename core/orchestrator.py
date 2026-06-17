# core/orchestrator.py
from typing import List, Dict, Any
from adapters.base import SocialAdapter
from utils.logger import logger
from utils.media_downloader import download_media


class Orchestrator:
    """Manages and coordinates all target platform adapters."""

    def __init__(self):
        self.adapters: List[SocialAdapter] = []

    def register_adapter(self, adapter: SocialAdapter) -> None:
        """Registers a target platform adapter."""
        self.adapters.append(adapter)
        logger.info(f"Registered adapter: {adapter.__class__.__name__}")

    def validate_all(self) -> bool:
        """Validates credentials for all registered adapters."""
        all_valid = True
        for adapter in self.adapters:
            if not adapter.validate_credentials():
                all_valid = False
                logger.error(f"❌ Adapter {adapter.__class__.__name__} validation failed.")
            else:
                logger.info(f"✅ Adapter {adapter.__class__.__name__} validated.")
        return all_valid

    def crosspost(self, post_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Sends a post to all registered target adapters.

        Args:
            post_data: The post data from the source (Bluesky).

        Returns:
            A list of results from each adapter.
        """
        text = post_data.get("text", "")
        media_items = post_data.get("media", [])
        post_uri = post_data.get("uri", "")

        # Download media files
        media_paths = []
        if media_items:
            logger.info(f"📥 Downloading {len(media_items)} media item(s)...")
            media_paths = download_media(media_items, post_uri)
            if media_paths:
                logger.info(f"✅ Downloaded {len(media_paths)} media file(s)")
            else:
                logger.warning("⚠️  No media files were downloaded successfully")

        results = []
        for adapter in self.adapters:
            logger.info(f"📤 Posting to {adapter.__class__.__name__}...")
            result = adapter.post(text, media_paths)
            results.append(result)

            if result.get("success"):
                logger.success(f"✅ Successfully posted to {adapter.__class__.__name__}: {result.get('url')}")
            else:
                logger.error(f"❌ Failed to post to {adapter.__class__.__name__}: {result.get('error')}")

        return results
