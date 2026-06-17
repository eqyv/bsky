# main.py
import sys
import time
from config import config
from utils.logger import logger
from core.detector import get_new_posts
from core.orchestrator import Orchestrator
from core.state_manager import StateManager
from adapters.bluesky_source import BlueskySource
from adapters.twitter import TwitterAdapter
from adapters.instagram import InstagramAdapter


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

    # 3. Initialize the Orchestrator and register target adapters
    orchestrator = Orchestrator()

    # Register X (Twitter) adapter if credentials are present
    if config.X_AUTH_TOKEN and config.X_CT0:
        twitter_adapter = TwitterAdapter(
            auth_token=config.X_AUTH_TOKEN,
            ct0=config.X_CT0
        )
        orchestrator.register_adapter(twitter_adapter)
    else:
        logger.warning("⚠️  X (Twitter) credentials not found. Skipping X adapter.")

    # Register Instagram adapter if credentials are present
    if config.IG_SESSIONID and config.IG_CSRFTOKEN and config.IG_DS_USER_ID:
        instagram_adapter = InstagramAdapter(
            sessionid=config.IG_SESSIONID,
            csrftoken=config.IG_CSRFTOKEN,
            ds_user_id=config.IG_DS_USER_ID
        )
        orchestrator.register_adapter(instagram_adapter)
    else:
        logger.warning("⚠️  Instagram cookies not found. Skipping Instagram adapter.")

    # 4. Validate all target adapters (fail-fast if any are invalid)
    if not orchestrator.validate_all():
        logger.error("❌ One or more target adapters failed validation. Please check your credentials.")
        # We can choose to exit or continue with only the valid ones.
        # For now, let's continue with the ones that are valid.
        logger.warning("⚠️  Continuing with valid adapters only.")
        # If no adapters are valid, we should exit.
        if not orchestrator.adapters:
            logger.error("❌ No valid target adapters. Exiting.")
            sys.exit(1)

    # 5. Seeding logic (unchanged)
    last_uri = StateManager.get_last_post_uri()
    if last_uri is None:
        logger.info("🌱 First run detected. Seeding state with the latest existing post...")
        try:
            did = bsky_source._resolve_did()
            if did:
                response = bsky_source.client.get_author_feed(
                    actor=did,
                    limit=1,
                    filter="posts_no_replies"
                )
                if response.feed:
                    latest_seed_uri = response.feed[0].post.uri
                    StateManager.set_last_post_uri(latest_seed_uri)
                    logger.info(f"   ✅ Seeded with URI: {latest_seed_uri[:30]}...")
                    logger.info("   ℹ️  Only posts created AFTER this URI will be processed.")
                else:
                    logger.info("   ℹ️  No existing posts found. The bot will start fresh.")
            else:
                logger.warning("   ⚠️  Could not resolve DID to seed state. Proceeding anyway.")
        except Exception as e:
            logger.error(f"   ❌ Failed to seed initial state: {e}. Will try again on next poll.")

        last_uri = StateManager.get_last_post_uri()

    logger.info(f"📌 Last processed post URI: {last_uri}")
    logger.info("✨ Bot is ready. Starting polling loop...")
    logger.info("ℹ️  Press Ctrl+C to stop.")

    # 6. Polling loop
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

                    # --- Cross-post to all target platforms ---
                    results = orchestrator.crosspost(post)

                    # Check if any post succeeded
                    if any(r.get("success") for r in results):
                        # Update state only if at least one platform succeeded
                        try:
                            StateManager.set_last_post_uri(post['uri'])
                            logger.info(f"   ✅ State updated to: {post['uri'][:30]}...")
                        except Exception as e:
                            logger.error(f"   ❌ Failed to update state for {post['uri']}. Stopping batch to retry.")
                            break
                    else:
                        logger.error(f"   ❌ All platforms failed for post {post['uri']}. Not updating state.")
                        # We break here to retry this post on the next poll
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
