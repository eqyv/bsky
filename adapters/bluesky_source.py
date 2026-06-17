# adapters/bluesky_source.py (only the modified method, the rest stays the same)
from typing import Optional, List, Dict, Any
from atproto import Client, IdResolver
from atproto.exceptions import AtProtocolError
from atproto_client.models import AppBskyEmbedImages, AppBskyEmbedVideo
from utils.logger import logger
from core.state_manager import StateManager


class BlueskySource:
    # ... (__init__, validate_credentials, _ensure_logged_in, _resolve_did, _extract_media, _format_post remain exactly the same) ...

    def get_unprocessed_posts(self) -> List[Dict[str, Any]]:
        """
        Fetch a batch of recent posts and return only the ones that are NEWER than the last processed URI.
        Returns posts in chronological order (oldest unprocessed first).

        **Logic**:
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
            # We stop here because everything older than this is already processed.
            if current_uri == last_uri:
                break

            # This is a NEW post (newer than the seed), collect it.
            unprocessed_reversed.append(self._format_post(post))

        # 5. Reverse to get oldest → newest (so we post in order)
        unprocessed_reversed.reverse()

        if unprocessed_reversed:
            logger.info(f"📦 Found {len(unprocessed_reversed)} unprocessed post(s) from {self.handle}")

        return unprocessed_reversed
