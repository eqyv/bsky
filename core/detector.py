# core/detector.py
from typing import Optional, Dict, Any
from utils.logger import logger
from core.state_manager import StateManager


def check_for_new_post(source) -> Optional[Dict[str, Any]]:
    """
    Check the Bluesky source for a new post.
    If a new post is found, it updates the state and returns the post data.
    If no new post, returns None.
    """
    try:
        post_data = source.get_latest_post()
    except Exception as e:
        logger.error(f"Error while checking for new post: {e}")
        return None

    if post_data is None:
        return None

    # Update state to mark this post as processed
    try:
        StateManager.set_last_post_uri(post_data["uri"])
        logger.debug(f"State updated: last_post_uri = {post_data['uri']}")
    except Exception as e:
        logger.error(f"Failed to update state: {e}")
        # Even if state update fails, we return the post so the orchestrator can try to post.
        # But we should log it loudly.

    return post_data
