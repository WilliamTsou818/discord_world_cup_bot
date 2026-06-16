# services/worldcup_api.py
from dataclasses import dataclass
from datetime import datetime, timedelta
import requests
import ssl
from requests.adapters import HTTPAdapter

from config import WORLDCUP_API_TOKEN
from utils import parse_api_datetime, utc_now, translate_team_name

API_BASE_URL = "https://worldcup26.ir"
GAMES_ENDPOINT = f"{API_BASE_URL}/get/games"


class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)


@dataclass
class Game:
    fixture_id: int
    home_team: str
    away_team: str
    group_name: str | None
    match_type: str
    start_time: datetime
    finished: bool
    time_elapsed: str
    home_score: int | None
    away_score: int | None


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    if WORLDCUP_API_TOKEN:
        headers["Authorization"] = f"Bearer {WORLDCUP_API_TOKEN}"
    return headers


def fetch_games() -> list[Game]:
    session = requests.Session()
    session.mount("https://", TLSAdapter())
    
    response = session.get(GAMES_ENDPOINT, headers=_headers(), timeout=30)
    response.raise_for_status()
    payload = response.json()
    return [parse_game(raw) for raw in payload.get("games", [])]


def parse_game(raw: dict) -> Game:
    home = raw.get("home_team_name_en") or raw.get("home_team_label") or "TBD"
    away = raw.get("away_team_name_en") or raw.get("away_team_label") or "TBD"

    home_translated = translate_team_name(home)
    away_translated = translate_team_name(away)

    home_score = _to_int_or_none(raw.get("home_score"))
    away_score = _to_int_or_none(raw.get("away_score"))

    return Game(
        fixture_id=int(raw["id"]),
        home_team=home_translated,    
        away_team=away_translated,    
        group_name=raw.get("group"),
        match_type=raw.get("type", "group"),
        start_time=parse_api_datetime(raw["local_date"], raw.get("stadium_id", "1")),
        finished=str(raw.get("finished", "")).upper() == "TRUE",
        time_elapsed=str(raw.get("time_elapsed", "")),
        home_score=home_score,
        away_score=away_score,
    )


def filter_games_within_hours(games: list[Game], hours: float) -> list[Game]:
    now = utc_now()
    window_end = now + timedelta(hours=hours)
    return [game for game in games if now <= game.start_time <= window_end]


def get_game_by_id(fixture_id: int) -> Game | None:
    for game in fetch_games():
        if game.fixture_id == fixture_id:
            return game
    return None


def is_game_finished(game: Game) -> bool:
    return game.finished and game.time_elapsed.lower() == "finished"


def determine_winner(home_score: int, away_score: int, match_type: str) -> str:
    if home_score > away_score:
        return "HOME"
    if away_score > home_score:
        return "AWAY"
    if match_type == "group":
        return "DRAW"
    raise ValueError("Knockout match ended in a draw without a winner")


def _to_int_or_none(value) -> int | None:
    if value is None or value == "null":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None