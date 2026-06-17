import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bluesky
    BSKY_HANDLE: str = os.getenv("BSKY_HANDLE", "")
    BSKY_APP_PASSWORD: str = os.getenv("BSKY_APP_PASSWORD", "")

    # X / Twitter (Login method)
    X_USERNAME: str = os.getenv("X_USERNAME", "")
    X_EMAIL: str = os.getenv("X_EMAIL", "")
    X_PASSWORD: str = os.getenv("X_PASSWORD", "")
    X_TOTP_SECRET: str = os.getenv("X_TOTP_SECRET", "")
    X_COOKIES_FILE: str = os.getenv("X_COOKIES_FILE", "storage/twitter_cookies.json")
    # Cookie-based auth (preferred on datacenter/VPS IPs where login is Cloudflare-blocked).
    # Export these from a browser logged into X (see .env.example).
    X_AUTH_TOKEN: str = os.getenv("X_AUTH_TOKEN", "")
    X_CT0: str = os.getenv("X_CT0", "")

    # Instagram
    IG_USERNAME: str = os.getenv("IG_USERNAME", "")
    IG_PASSWORD: str = os.getenv("IG_PASSWORD", "")
    IG_SETTINGS_FILE: str = os.getenv("IG_SETTINGS_FILE", "storage/instagram_settings.json")

    # Bot Settings
    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "180"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> bool:
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

config = Config()
