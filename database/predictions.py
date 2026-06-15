from dataclasses import dataclass

from database.base import TABLE_PREDICTIONS, get_connection, utc_now
from database.games import get_match

LOCKED_MESSAGE = "❌ 比賽已開始，無法再提交或修改預測！"


@dataclass
class PredictionRow:
    prediction_id: int
    user_id: str
    username: str
    fixture_id: int
    predict_winner: str | None
    predict_home_score: int
    predict_away_score: int


def is_match_locked(fixture_id: int) -> bool:
    match = get_match(fixture_id)
    if match is None:
        return True
    start_time = match.start_time
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=utc_now().tzinfo)
    return utc_now() >= start_time


def get_prediction(user_id: str, fixture_id: int) -> PredictionRow | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT prediction_id, user_id, username, fixture_id,
                       predict_winner, predict_home_score, predict_away_score
                FROM {TABLE_PREDICTIONS}
                WHERE user_id = %s AND fixture_id = %s
                """,
                (user_id, fixture_id),
            )
            row = cur.fetchone()
    return _row_to_prediction(row) if row else None


def upsert_prediction(
    user_id: str,
    username: str,
    fixture_id: int,
    predict_winner: str | None = None,
    predict_home_score: int | None = None,
    predict_away_score: int | None = None,
) -> tuple[bool, str]:
    if is_match_locked(fixture_id):
        return False, LOCKED_MESSAGE

    existing = get_prediction(user_id, fixture_id)
    winner = predict_winner if predict_winner is not None else (existing.predict_winner if existing else "HOME")
    home_score = predict_home_score if predict_home_score is not None else (existing.predict_home_score if existing else 0)
    away_score = predict_away_score if predict_away_score is not None else (existing.predict_away_score if existing else 0)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {TABLE_PREDICTIONS} (
                    user_id, username, fixture_id,
                    predict_winner, predict_home_score, predict_away_score, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id, fixture_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    predict_winner = EXCLUDED.predict_winner,
                    predict_home_score = EXCLUDED.predict_home_score,
                    predict_away_score = EXCLUDED.predict_away_score,
                    updated_at = NOW()
                """,
                (user_id, username, fixture_id, winner, home_score, away_score),
            )

    return True, "✅ 預測已儲存！"


def get_predictions_for_fixture(fixture_id: int) -> list[PredictionRow]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT prediction_id, user_id, username, fixture_id,
                       predict_winner, predict_home_score, predict_away_score
                FROM {TABLE_PREDICTIONS}
                WHERE fixture_id = %s
                """,
                (fixture_id,),
            )
            rows = cur.fetchall()
    return [_row_to_prediction(row) for row in rows]


def _row_to_prediction(row) -> PredictionRow:
    return PredictionRow(
        prediction_id=row[0],
        user_id=row[1],
        username=row[2],
        fixture_id=row[3],
        predict_winner=row[4],
        predict_home_score=row[5],
        predict_away_score=row[6],
    )
