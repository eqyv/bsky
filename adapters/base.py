# adapters/base.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

class SocialAdapter(ABC):
    """
    Abstract Base Class for all social media platform adapters.
    Every target platform (Twitter, Instagram, etc.) must implement this.
    """

    @abstractmethod
    def validate_credentials(self) -> bool:
        """
        Called at startup to ensure the provided credentials/tokens are valid.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def post(
        self,
        text: str,
        media_paths: Optional[List[str]] = None,
        media_urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Posts content to the platform.

        Args:
            text: The text content of the post.
            media_paths: An optional list of local file paths to images/videos to upload.
            media_urls: An optional list of public media URLs from the source post.

        Returns:
            A dictionary containing the result of the operation:
            {
                "success": bool,
                "url": Optional[str],  # URL to the published post, if available
                "error": Optional[str] # Error message if success is False
            }
        """
        pass
