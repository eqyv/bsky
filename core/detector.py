# core/detector.py
from typing import List, Dict, Any
from utils.logger import logger


def get_new_posts(source) -> List[Dict[str, Any]]:
    """
    Fetch all unprocessed posts from the source.
    Returns a list of post data dicts, or empty list if none.
    """
    try:
        return source.get_unprocessed_posts()
    except Exception as e:
        logger.error(f"Error while checking for new posts: {e}")
        return []
