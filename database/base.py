from contextlib import contextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras

from config import DATABASE_URL, TEST_MODE

TABLE_MATCHES = "test_matches" if TEST_MODE else "matches"
TABLE_PREDICTIONS = "test_predictions" if TEST_MODE else "predictions"
TABLE_LEADERBOARD = "test_leaderboard" if TEST_MODE else "leaderboard"

UTC = timezone.utc
TAIPEI_TZ = ZoneInfo("Asia/Taipei")

psycopg2.extras.register_uuid()


def parse_api_datetime(date_str: str) -> datetime:
    """Parse API local_date (MM/DD/YYYY HH:mm) as UTC."""
    dt = datetime.strptime(date_str, "%m/%d/%Y %H:%M")
    return dt.replace(tzinfo=UTC)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def format_taipei_time(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(TAIPEI_TZ).strftime("%Y/%m/%d %H:%M")


@contextmanager
def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
