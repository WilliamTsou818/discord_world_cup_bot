from contextlib import contextmanager
import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

from config import DATABASE_URL, TEST_MODE

TABLE_MATCHES = "test_matches" if TEST_MODE else "matches"
TABLE_PREDICTIONS = "test_predictions" if TEST_MODE else "predictions"
TABLE_LEADERBOARD = "test_leaderboard" if TEST_MODE else "leaderboard"

psycopg2.extras.register_uuid()
_connection_pool = ThreadedConnectionPool(1, 10, DATABASE_URL)


@contextmanager
def get_connection():
    conn = _connection_pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _connection_pool.putconn(conn)