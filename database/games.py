# database/games.py
from dataclasses import dataclass
from datetime import timedelta

from services import Game
from database.base import TABLE_MATCHES, get_connection
from utils import utc_now


@dataclass
class MatchRow:
    fixture_id: int
    home_team: str
    away_team: str
    group_name: str | None
    match_type: str
    start_time: object
    is_posted: bool
    is_settled: bool
    home_score: int | None
    away_score: int | None


def sync_upcoming_games(games: list[Game]) -> int:
    inserted = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for game in games:
                cur.execute(
                    f"""
                    INSERT INTO {TABLE_MATCHES} (
                        fixture_id, home_team, away_team, group_name,
                        match_type, start_time, is_posted, is_settled
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, FALSE, FALSE)
                    ON CONFLICT (fixture_id) DO NOTHING
                    """,
                    (
                        game.fixture_id,
                        game.home_team,
                        game.away_team,
                        game.group_name,
                        game.match_type,
                        game.start_time,
                    ),
                )
                if cur.rowcount:
                    inserted += 1
    return inserted


def get_unposted_matches_within_hours(hours: float = 30) -> list[MatchRow]:
    now = utc_now()
    window_end = now + timedelta(hours=hours)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT fixture_id, home_team, away_team, group_name, match_type,
                       start_time, is_posted, is_settled, home_score, away_score
                FROM {TABLE_MATCHES}
                WHERE is_posted = FALSE
                  AND start_time >= %s
                  AND start_time <= %s
                ORDER BY start_time
                """,
                (now, window_end),
            )
            rows = cur.fetchall()
    return [_row_to_match(row) for row in rows]


def mark_as_posted(fixture_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {TABLE_MATCHES} SET is_posted = TRUE WHERE fixture_id = %s",
                (fixture_id,),
            )


def get_match(fixture_id: int) -> MatchRow | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT fixture_id, home_team, away_team, group_name, match_type,
                       start_time, is_posted, is_settled, home_score, away_score
                FROM {TABLE_MATCHES}
                WHERE fixture_id = %s
                """,
                (fixture_id,),
            )
            row = cur.fetchone()
    return _row_to_match(row) if row else None


def get_matches_ready_for_settlement(hours_after_start: float = 2.5) -> list[MatchRow]:
    cutoff = utc_now() - timedelta(hours=hours_after_start)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT fixture_id, home_team, away_team, group_name, match_type,
                       start_time, is_posted, is_settled, home_score, away_score
                FROM {TABLE_MATCHES}
                WHERE is_settled = FALSE
                  AND start_time <= %s
                ORDER BY start_time
                """,
                (cutoff,),
            )
            rows = cur.fetchall()
    return [_row_to_match(row) for row in rows]


def get_active_matches() -> list[MatchRow]:
    """取得資料庫中所有『尚未結算』的賽事紀錄 (用於機器人啟動時加載按鈕監聽)"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT fixture_id, home_team, away_team, group_name, match_type,
                       start_time, is_posted, is_settled, home_score, away_score
                FROM {TABLE_MATCHES}
                WHERE is_settled = FALSE
                """
            )
            rows = cur.fetchall()
    return [_row_to_match(row) for row in rows]


def update_match_result(
    fixture_id: int,
    home_score: int,
    away_score: int,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {TABLE_MATCHES}
                SET home_score = %s, away_score = %s, is_settled = TRUE
                WHERE fixture_id = %s
                """,
                (home_score, away_score, fixture_id),
            )


def _row_to_match(row) -> MatchRow:
    return MatchRow(
        fixture_id=row[0],
        home_team=row[1],
        away_team=row[2],
        group_name=row[3],
        match_type=row[4],
        start_time=row[5],
        is_posted=row[6],
        is_settled=row[7],
        home_score=row[8],
        away_score=row[9],
    )

def get_predictable_matches() -> list[MatchRow]:
    now = utc_now()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT fixture_id, home_team, away_team, group_name, match_type,
                       start_time, is_posted, is_settled, home_score, away_score
                FROM {TABLE_MATCHES}
                WHERE start_time > %s
                ORDER BY start_time ASC
                """,
                (now,),
            )
            rows = cur.fetchall()
    return [_row_to_match(row) for row in rows]

def update_match_teams(fixture_id: int, home_team: str, away_team: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE {TABLE_MATCHES}
                SET home_team = %s, away_team = %s
                WHERE fixture_id = %s
                """.format(TABLE_MATCHES=TABLE_MATCHES),
                (home_team, away_team, fixture_id),
            )