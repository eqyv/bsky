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

        # Check for images
        if isinstance(embed, AppBskyEmbedImages.View) or hasattr(embed, "images"):
            images = getattr(embed, "images", [])
            for img in images:
                # Images in Bluesky have 'fullsize' and 'thumb' URLs.
                # We prefer fullsize for higher quality uploads.
                url = getattr(img, "fullsize", None)
                alt = getattr(img, "alt", "")
                if url:
                    media_list.append({
                        "url": url,
                        "alt": alt,
                        "mime_type": "image/jpeg"  # default, but we can infer from URL later
                    })

        # Check for video
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

        # Check for external link with thumb
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

    def get_latest_post(self) -> Optional[Dict[str, Any]]:
        """
        Fetch the most recent original post (no replies, no reposts).
        Returns structured post data if a new post is found, otherwise None.

        Return structure:
        {
            "uri": "at://...",
            "cid": "...",
            "text": "Post text",
            "media": [{"url": "...", "alt": "...", "mime_type": "..."}],
            "author": "handle.bsky.social",
            "timestamp": "2026-06-16T14:30:00Z"
        }
        """
        # 1. Ensure we're logged in
        if not self._ensure_logged_in():
            return None

        # 2. Resolve DID
        did = self._resolve_did()
        if not did:
            return None

        # 3. Fetch the author feed (limit=5, filter out replies & reposts)
        try:
            # filter="posts_no_replies" also excludes reposts
            response = self.client.get_author_feed(
                actor=did,
                limit=5,
                filter="posts_no_replies"
            )
            feed = response.feed
        except AtProtocolError as e:
            logger.error(f"Failed to fetch feed for {self.handle}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching feed: {e}")
            return None

        if not feed:
            logger.warning(f"No posts found in feed for {self.handle}")
            return None

        # 4. Get the most recent post (index 0 is newest)
        latest_feed_view = feed[0]
        latest_post = latest_feed_view.post

        latest_uri = latest_post.uri
        latest_cid = latest_post.cid

        # 5. Check if we've already processed this post
        last_uri = StateManager.get_last_post_uri()
        if latest_uri == last_uri:
            logger.debug(f"No new posts from {self.handle} (last URI: {last_uri})")
            return None

        # 6. Extract text (posts may have no text, just images)
        text = ""
        if hasattr(latest_post, "record") and latest_post.record:
            if hasattr(latest_post.record, "text"):
                text = latest_post.record.text or ""
            elif hasattr(latest_post.record, "value") and hasattr(latest_post.record.value, "text"):
                # Some versions of the library nest the record
                text = latest_post.record.value.text or ""

        # 7. Extract media
        media = self._extract_media(latest_post)

        # 8. Build the result
        result = {
            "uri": latest_uri,
            "cid": latest_cid,
            "text": text,
            "media": media,
            "author": self.handle,
            "timestamp": str(latest_post.indexed_at) if hasattr(latest_post, "indexed_at") else "",
        }

        logger.info(f"📨 New post detected from {self.handle}: '{text[:50]}...' (URI: {latest_uri[:20]}...)")
        return result
