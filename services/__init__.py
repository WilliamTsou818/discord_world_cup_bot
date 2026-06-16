# services/__init__.py
from services.worldcup_api import (
    Game,
    fetch_games,
    filter_games_within_hours,
    get_game_by_id,
    is_game_finished,
    determine_winner
)