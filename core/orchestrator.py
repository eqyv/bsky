# core/orchestrator.py
from typing import List, Dict, Any
from adapters.base import SocialAdapter
from utils.logger import logger

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
        # media will be a list of dicts with 'url', 'alt', etc. from Phase 1.
        # We need to download these files. For Phase 2, we'll handle this in the media downloader.
        # For now, we'll pass an empty list.
        # This will be fully implemented in Phase 4.
        media_paths = []  # Placeholder for Phase 4

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
