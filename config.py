import os

from dotenv import load_dotenv

load_dotenv()


def _parse_bool(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in ("true", "1", "yes", "on")


DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
DISCORD_CHANNEL_ID: int = int(os.getenv("DISCORD_CHANNEL_ID", "0") or "0")
TEST_CHANNEL_ID: int = int(os.getenv("TEST_CHANNEL_ID", "0") or "0")
TEST_MODE: bool = _parse_bool(os.getenv("TEST_MODE", "False"))
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
WORLDCUP_API_TOKEN: str = os.getenv("WORLDCUP_API_TOKEN", "")
PORT: int = int(os.getenv("PORT", "8000") or "8000")


def get_channel_id() -> int:
    return TEST_CHANNEL_ID if TEST_MODE else DISCORD_CHANNEL_ID
