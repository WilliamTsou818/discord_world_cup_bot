from dataclasses import dataclass

from database.base import TABLE_LEADERBOARD, get_connection


@dataclass
class LeaderboardRow:
    user_id: str
    username: str
    points: int


def add_points(user_id: str, username: str, points: int) -> None:
    if points <= 0:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {TABLE_LEADERBOARD} (user_id, username, points)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    points = {TABLE_LEADERBOARD}.points + EXCLUDED.points
                """,
                (user_id, username, points),
            )


def get_top_n(limit: int = 10) -> list[LeaderboardRow]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT user_id, username, points
                FROM {TABLE_LEADERBOARD}
                ORDER BY points DESC, username ASC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [LeaderboardRow(user_id=row[0], username=row[1], points=row[2]) for row in rows]
