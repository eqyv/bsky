# main.py
import sys
import time
from config import config
from utils.logger import logger
from core.detector import get_new_posts
from core.state_manager import StateManager
from adapters.bluesky_source import BlueskySource


def main():
    logger.info("🚀 Crosspost Bot starting up...")
    logger.info(f"📁 Log file: logs/bot_*.log")

    # 1. Validate config
    if not config.validate():
        logger.error("❌ Configuration validation failed. Please fill in your .env file.")
        sys.exit(1)

    logger.info("✅ Configuration loaded successfully.")
    logger.info(f"⏱️  Poll interval: {config.POLL_INTERVAL_SECONDS} seconds")

    # 2. Initialize Bluesky source
    logger.info(f"🔐 Initializing Bluesky source for {config.BSKY_HANDLE}...")
    bsky_source = BlueskySource(
        handle=config.BSKY_HANDLE,
        app_password=config.BSKY_APP_PASSWORD
    )

    if not bsky_source.validate_credentials():
        logger.error("❌ Bluesky authentication failed.")
        sys.exit(1)

    last_uri = StateManager.get_last_post_uri()
    logger.info(f"📌 Last processed post URI: {last_uri}")
    logger.info("✨ Bot is ready. Starting polling loop...")
    logger.info("ℹ️  Press Ctrl+C to stop.")

    try:
        while True:
            logger.debug("Polling Bluesky for new posts...")
            new_posts = get_new_posts(bsky_source)

            if new_posts:
                # Process posts one by one, oldest first
                for post in new_posts:
                    logger.success(f"🎯 Processing new post: {post['uri']}")
                    logger.info(f"   Text: {post['text'][:100]}...")
                    logger.info(f"   Media: {len(post['media'])} item(s)")

                    # --- PHASE 1 ONLY: Just log it.
                    # In Phase 2, we will call: orchestrator.crosspost(post)
                    # For now, we simulate success.

                    # --- CRITICAL: Update state only AFTER successfully handling this post.
                    # If we fail here, we DON'T update state, so it retries next poll.
                    try:
                        StateManager.set_last_post_uri(post['uri'])
                        logger.info(f"   ✅ State updated to: {post['uri'][:30]}...")
                    except Exception as e:
                        logger.error(f"   ❌ Failed to update state for {post['uri']}. Stopping batch to retry.")
                        # Break out of the for loop so we don't mark newer posts as processed
                        # when the older one failed.
                        break
            else:
                logger.debug("No new posts found.")

            time.sleep(config.POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Unhandled exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
