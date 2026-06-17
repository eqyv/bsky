import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Config:
    # Bluesky
    BSKY_HANDLE: str = os.getenv("BSKY_HANDLE", "")
    BSKY_APP_PASSWORD: str = os.getenv("BSKY_APP_PASSWORD", "")

    # X / Twitter
    X_AUTH_TOKEN: str = os.getenv("X_AUTH_TOKEN", "")
    X_CT0: str = os.getenv("X_CT0", "")

    # Instagram
    IG_SESSIONID: str = os.getenv("IG_SESSIONID", "")
    IG_CSRFTOKEN: str = os.getenv("IG_CSRFTOKEN", "")
    IG_DS_USER_ID: str = os.getenv("IG_DS_USER_ID", "")

    # Bot Settings
    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "180"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> bool:
        """Quick check to ensure critical variables are set."""
        missing = []
        if not cls.BSKY_HANDLE:
            missing.append("BSKY_HANDLE")
        if not cls.BSKY_APP_PASSWORD:
            missing.append("BSKY_APP_PASSWORD")
        if missing:
            print(f"⚠️  WARNING: Missing .env variables: {', '.join(missing)}")
            print("The bot will not work until these are filled.")
            return False
        return True

# Singleton instance for easier importing
config = Config()
