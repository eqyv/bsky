# utils/media_downloader.py
import os
import re
import time
import shutil
import tempfile
import requests
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
from utils.logger import logger


class MediaDownloader:
    """Handles downloading and managing media files from URLs."""

    def __init__(self, temp_dir: Optional[str] = None, max_age_hours: int = 24):
        """
        Initialize the media downloader.

        Args:
            temp_dir: Directory to store downloaded files. Defaults to /tmp/crosspost_bot/
            max_age_hours: Files older than this will be cleaned up automatically.
        """
        if temp_dir is None:
            # Use a subdirectory in /tmp
            self.temp_dir = Path(tempfile.gettempdir()) / "crosspost_bot"
        else:
            self.temp_dir = Path(temp_dir)

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_seconds = max_age_hours * 3600
        logger.debug(f"Media downloader initialized. Temp dir: {self.temp_dir}")

    def _get_extension(
        self,
        url: str,
        content_type: Optional[str] = None,
        mime_hint: Optional[str] = None,
    ) -> str:
        """
        Determine file extension from URL, Content-Type, or a caller-provided
        mime hint (used when the server returns a generic/octet-stream type,
        e.g. getBlob for videos).
        """
        # Try to get extension from URL
        parsed = urlparse(url)
        path = parsed.path
        if path:
            # Check for common image extensions
            ext_match = re.search(r'\.(jpe?g|png|gif|webp|mp4|mov|avi|webm)$', path, re.I)
            if ext_match:
                return ext_match.group(1).lower()

        # Prefer a real Content-Type, but fall back to the caller's mime hint
        # when the response type is missing or uninformative.
        if not content_type or 'octet-stream' in content_type.lower():
            content_type = mime_hint or content_type

        # Fallback to Content-Type
        if content_type:
            if 'jpeg' in content_type or 'jpg' in content_type:
                return 'jpg'
            elif 'png' in content_type:
                return 'png'
            elif 'gif' in content_type:
                return 'gif'
            elif 'webp' in content_type:
                return 'webp'
            elif 'mp4' in content_type:
                return 'mp4'
            elif 'quicktime' in content_type or 'mov' in content_type:
                return 'mov'

        # Default fallback
        return 'jpg'

    def _generate_filename(self, url: str, post_uri: str) -> str:
        """
        Generate a unique filename based on post URI and URL.
        """
        # Use post URI as a base (clean it up)
        uri_clean = re.sub(r'[^a-zA-Z0-9]', '_', post_uri)[:30]
        # Get last part of URL path as a unique identifier
        parsed = urlparse(url)
        path_parts = parsed.path.split('/')
        url_id = path_parts[-1] if path_parts else 'file'
        # Remove query params
        url_id = url_id.split('?')[0]
        # Use a timestamp for uniqueness
        timestamp = int(time.time())
        return f"{uri_clean}_{url_id}_{timestamp}"

    def download(
        self,
        url: str,
        post_uri: str,
        alt_text: str = "",
        mime_type: str = "",
    ) -> Optional[Path]:
        """
        Download a single media file from a URL.

        Args:
            url: The URL of the media file.
            post_uri: The URI of the post (for filename generation).
            alt_text: Alt text for the media (not used for download, but we keep it).
            mime_type: Known mime type hint (e.g. "video/mp4"), used to pick the
                correct extension when the server returns a generic Content-Type.

        Returns:
            Path to the downloaded file, or None if download failed.
        """
        if not url:
            logger.warning("Empty URL provided for download")
            return None

        try:
            logger.debug(f"Downloading: {url[:80]}...")

            # Make request with timeout
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()

            # Determine file extension
            content_type = response.headers.get('Content-Type', '')
            ext = self._get_extension(url, content_type, mime_hint=mime_type)

            # Generate filename
            base_name = self._generate_filename(url, post_uri)
            filename = f"{base_name}.{ext}"
            file_path = self.temp_dir / filename

            # Write the file
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            logger.debug(f"Downloaded: {file_path} ({file_path.stat().st_size} bytes)")
            return file_path

        except requests.exceptions.Timeout:
            logger.error(f"Timeout downloading {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading {url}: {e}")
            return None

    def download_batch(
        self,
        media_items: List[Dict[str, str]],
        post_uri: str
    ) -> List[Path]:
        """
        Download multiple media files.

        Args:
            media_items: List of dicts with 'url', 'alt' keys.
            post_uri: The URI of the post.

        Returns:
            List of Path objects for successfully downloaded files.
        """
        if not media_items:
            return []

        downloaded_paths = []
        for item in media_items:
            url = item.get('url', '')
            alt = item.get('alt', '')
            mime_type = item.get('mime_type', '')
            if url:
                path = self.download(url, post_uri, alt, mime_type=mime_type)
                if path:
                    downloaded_paths.append(path)

        if downloaded_paths:
            logger.info(f"Downloaded {len(downloaded_paths)} media items for post {post_uri[:20]}...")
        else:
            logger.warning(f"No media items could be downloaded for post {post_uri[:20]}...")

        return downloaded_paths

    def cleanup(self, force: bool = False) -> int:
        """
        Remove old files from the temp directory.

        Args:
            force: If True, delete all files regardless of age.

        Returns:
            Number of files deleted.
        """
        if not self.temp_dir.exists():
            return 0

        deleted_count = 0
        now = time.time()

        for file_path in self.temp_dir.iterdir():
            if file_path.is_file():
                file_age = now - file_path.stat().st_mtime
                if force or file_age > self.max_age_seconds:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted old file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete {file_path}: {e}")

        if deleted_count:
            logger.info(f"Cleaned up {deleted_count} old media file(s)")
        return deleted_count

    def clear_all(self) -> int:
        """Delete all files in the temp directory."""
        return self.cleanup(force=True)

    def get_file_size(self, path: Path) -> int:
        """Get file size in bytes."""
        try:
            return path.stat().st_size
        except Exception:
            return 0


# Singleton instance for easy importing
_downloader: Optional[MediaDownloader] = None


def get_downloader(
    temp_dir: Optional[str] = None,
    max_age_hours: int = 24
) -> MediaDownloader:
    """Get or create the singleton MediaDownloader instance."""
    global _downloader
    if _downloader is None:
        _downloader = MediaDownloader(temp_dir, max_age_hours)
    return _downloader


def download_media(
    media_items: List[Dict[str, str]],
    post_uri: str
) -> List[str]:
    """
    Convenience function to download media and return string paths.

    Args:
        media_items: List of dicts with 'url', 'alt' keys.
        post_uri: The URI of the post.

    Returns:
        List of string paths to downloaded files.
    """
    downloader = get_downloader()
    paths = downloader.download_batch(media_items, post_uri)
    return [str(p) for p in paths]
