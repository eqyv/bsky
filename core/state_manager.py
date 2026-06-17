import json
import os
from typing import Optional

STATE_FILE = "storage/state.json"

class StateManager:
    @staticmethod
    def load() -> dict:
        """Load the entire state JSON."""
        if not os.path.exists(STATE_FILE):
            return {"last_post_uri": None}
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"last_post_uri": None}

    @staticmethod
    def save(state: dict) -> None:
        """Save the entire state JSON."""
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    @staticmethod
    def get_last_post_uri() -> Optional[str]:
        """Convenience method to get the last posted URI."""
        state = StateManager.load()
        return state.get("last_post_uri")

    @staticmethod
    def set_last_post_uri(uri: str) -> None:
        """Convenience method to update the last posted URI."""
        state = StateManager.load()
        state["last_post_uri"] = uri
        StateManager.save(state)

# Test if it works (can be removed later)
if __name__ == "__main__":
    print("Testing state manager...")
    print(f"Current last_post_uri: {StateManager.get_last_post_uri()}")
    StateManager.set_last_post_uri("at://test/uri")
    print(f"Updated to: {StateManager.get_last_post_uri()}")
