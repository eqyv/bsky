import sys
from config import config
from utils.logger import logger
from core.state_manager import StateManager

def main():
    logger.info("🚀 Crosspost Bot starting up...")
    logger.info(f"📁 Log file: logs/bot_*.log")

    # Validate .env config
    if not config.validate():
        logger.error("❌ Configuration validation failed. Please fill in your .env file.")
        sys.exit(1)

    logger.info(f"✅ Configuration loaded successfully.")
    logger.info(f"⏱️  Poll interval: {config.POLL_INTERVAL_SECONDS} seconds")

    # Show current state
    last_uri = StateManager.get_last_post_uri()
    logger.info(f"📌 Last processed post URI: {last_uri}")

    logger.info("✨ Bot is initialized and ready. (More logic coming in Phase 1)")
    logger.info("ℹ️  Press Ctrl+C to stop.")

    # Keep the script alive (for now, we just sleep)
    import time
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        sys.exit(0)

if __name__ == "__main__":
    main()
