# main.py
import sys
import time
from config import config
from utils.logger import logger
from core.detector import check_for_new_post
from adapters.bluesky_source import BlueskySource


def main():
    logger.info("🚀 Crosspost Bot starting up...")
    logger.info(f"📁 Log file: logs/bot_*.log")

    # 1. Validate .env config
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

    # 3. Validate Bluesky credentials (fail-fast)
    if not bsky_source.validate_credentials():
        logger.error("❌ Bluesky authentication failed. Check your handle and app password.")
        sys.exit(1)

    # 4. Show current state
    from core.state_manager import StateManager
    last_uri = StateManager.get_last_post_uri()
    logger.info(f"📌 Last processed post URI: {last_uri}")

    logger.info("✨ Bot is ready. Starting polling loop...")
    logger.info("ℹ️  Press Ctrl+C to stop.")

    # 5. Polling loop
    try:
        while True:
            logger.debug("Polling Bluesky for new posts...")
            post_data = check_for_new_post(bsky_source)

            if post_data:
                # For Phase 1, we just log the detected post.
                # In Phase 2+, we'll pass this to the orchestrator.
                logger.success(f"🎯 New post detected!")
                logger.info(f"   Text: {post_data['text'][:100]}...")
                logger.info(f"   Media: {len(post_data['media'])} item(s)")
                logger.info(f"   URI: {post_data['uri']}")
                # TODO: Phase 2 — send to orchestrator for cross-posting
            else:
                logger.debug("No new posts found.")

            # Wait before next poll
            time.sleep(config.POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Unhandled exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
