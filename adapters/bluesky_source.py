# adapters/bluesky_source.py
from typing import Optional, List, Dict, Any
from atproto import Client, IdResolver
from atproto.exceptions import AtProtocolError
from atproto_client.models import AppBskyEmbedImages, AppBskyEmbedVideo
from utils.logger import logger
from core.state_manager import StateManager


class BlueskySource:
    """Source adapter that polls a Bluesky account for new posts."""

    def __init__(self, handle: str, app_password: str):
        self.handle = handle
        self.app_password = app_password
        self.client = Client()
        self.resolver = IdResolver()
        self._did: Optional[str] = None
        self._logged_in: bool = False

    def validate_credentials(self) -> bool:
        """Test login to Bluesky. Returns True if successful."""
        try:
            self.client.login(self.handle, self.app_password)
            self._logged_in = True
            logger.success(f"✅ Bluesky login successful for {self.handle}")
            return True
        except AtProtocolError as e:
            logger.error(f"❌ Bluesky login failed for {self.handle}: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error during Bluesky login: {e}")
            return False

    def _ensure_logged_in(self) -> bool:
        """Ensure we have a valid session, re-login if needed."""
        if not self._logged_in:
            return self.validate_credentials()
        return True

    def _resolve_did(self) -> Optional[str]:
        """Resolve handle to DID. Caches the result."""
        if self._did:
            return self._did
        try:
            self._did = self.resolver.handle.resolve(self.handle)
            logger.debug(f"Resolved {self.handle} → {self._did}")
            return self._did
        except Exception as e:
            logger.error(f"Failed to resolve handle {self.handle}: {e}")
            return None

    def _extract_media(self, post) -> List[Dict[str, str]]:
        """
        Extract media (images/videos) from a Bluesky post.
        Returns a list of dicts: [{"url": "...", "alt": "...", "mime_type": "..."}]
        """
        media_list = []

        if not hasattr(post, "embed") or post.embed is None:
            return media_list

        embed = post.embed

        # Images
        if isinstance(embed, AppBskyEmbedImages.View) or hasattr(embed, "images"):
            images = getattr(embed, "images", [])
            for img in images:
                url = getattr(img, "fullsize", None)
                alt = getattr(img, "alt", "")
                if url:
                    media_list.append({
                        "url": url,
                        "alt": alt,
                        "mime_type": "image/jpeg"
                    })

        # Video
        if isinstance(embed, AppBskyEmbedVideo.View) or hasattr(embed, "video"):
            video = getattr(embed, "video", None)
            if video:
                url = getattr(video, "ref", None) or getattr(video, "playlist", None)
                if url:
                    media_list.append({
                        "url": url,
                        "alt": "",
                        "mime_type": "video/mp4"
                    })

        # External link thumb
        if hasattr(embed, "external") and embed.external:
            ext = embed.external
            thumb_url = getattr(ext, "thumb", None)
            if thumb_url:
                media_list.append({
                    "url": thumb_url,
                    "alt": getattr(ext, "title", ""),
                    "mime_type": "image/jpeg"
                })

        if media_list:
            logger.debug(f"Extracted {len(media_list)} media items from post")
        return media_list

    def _format_post(self, post) -> Dict[str, Any]:
        """Extract structured data from a post object."""
        text = ""
        if hasattr(post, "record") and post.record:
            if hasattr(post.record, "text"):
                text = post.record.text or ""
            elif hasattr(post.record, "value") and hasattr(post.record.value, "text"):
                text = post.record.value.text or ""

        return {
            "uri": post.uri,
            "cid": post.cid,
            "text": text,
            "media": self._extract_media(post),
            "author": self.handle,
            "timestamp": str(post.indexed_at) if hasattr(post, "indexed_at") else "",
        }

    def get_unprocessed_posts(self) -> List[Dict[str, Any]]:
        """
        Fetch a batch of recent posts and return only the ones that are NEWER than the last processed URI.
        Returns posts in chronological order (oldest unprocessed first).

        Logic:
        1. Fetch the latest 10 posts (newest first).
        2. Iterate through them from newest → oldest.
        3. If we hit the `last_post_uri` (the seed), stop immediately.
        4. Collect all posts before that seed, then reverse to get oldest → newest.
        """
        # 1. Ensure login and resolve DID
        if not self._ensure_logged_in():
            return []
        did = self._resolve_did()
        if not did:
            return []

        # 2. Fetch the latest batch (limit=10 to catch bursts)
        try:
            response = self.client.get_author_feed(
                actor=did,
                limit=10,
                filter="posts_no_replies"
            )
            feed = response.feed
        except AtProtocolError as e:
            logger.error(f"Failed to fetch feed for {self.handle}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching feed: {e}")
            return []

        if not feed:
            return []

        # 3. Get the last processed URI from state (the seed)
        last_uri = StateManager.get_last_post_uri()
        unprocessed_reversed = []  # Posts collected newest → oldest

        # 4. Iterate from newest to oldest
        for item in feed:  # feed is already sorted newest-first
            post = item.post
            current_uri = post.uri

            # If we've already processed this exact URI (or it's the seed), stop.
            # Everything older than this is already processed.
            if current_uri == last_uri:
                break

            # This is a NEW post (newer than the seed), collect it.
            unprocessed_reversed.append(self._format_post(post))

        # 5. Reverse to get oldest → newest (so we post in order)
        unprocessed_reversed.reverse()

        if unprocessed_reversed:
            logger.info(f"📦 Found {len(unprocessed_reversed)} unprocessed post(s) from {self.handle}")

        return unprocessed_reversed
