# database/predictions.py
from dataclasses import dataclass

from database.base import TABLE_PREDICTIONS, TABLE_MATCHES, get_connection
from database.games import get_match
from utils import utc_now

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

    match = get_match(fixture_id)
    if not match:
        return False, "❌ 找不到賽事資訊。"

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

    # 組合繁體中文最新預測結果確認報告
    winner_display = "和局"
    if winner == "HOME":
        winner_display = f"{match.home_team} 勝"
    elif winner == "AWAY":
        winner_display = f"{match.away_team} 勝"

    success_msg = (
        f"✅ **預測儲存成功！**\n"
        f"您目前的預測：**{match.home_team} {home_score} - {away_score} {match.away_team}** ({winner_display})\n"
        f"*(開賽前您隨時可以再次點擊按鈕修改預測)*"
    )
    return True, success_msg


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

def get_user_prediction_history(user_id: str) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT 
                    m.home_team, 
                    m.away_team, 
                    m.fixture_id,
                    m.home_score, 
                    m.away_score, 
                    m.is_settled,
                    p.predict_winner, 
                    p.predict_home_score, 
                    p.predict_away_score,
                    m.start_time
                FROM {TABLE_PREDICTIONS} p
                JOIN {TABLE_MATCHES} m ON p.fixture_id = m.fixture_id
                WHERE p.user_id = %s
                ORDER BY m.start_time DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
            
    history = []
    for r in rows:
        history.append({
            "home_team": r[0],
            "away_team": r[1],
            "fixture_id": r[2],
            "actual_home": r[3],
            "actual_away": r[4],
            "is_settled": r[5],
            "predict_winner": r[6],
            "predict_home": r[7],
            "predict_away": r[8],
            "start_time": r[9],
        })
    return history