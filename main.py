# main.py
import logging
import threading

import discord
import uvicorn
from discord import app_commands
from discord.ext import commands
from fastapi import FastAPI

import services as api_client
from config import DISCORD_TOKEN, PORT, TEST_MODE, get_channel_id
from database import games as games_db
from database import leaderboard as leaderboard_db
from database import predictions as predictions_db
from views import MatchPredictionView, build_match_embed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

app = FastAPI(title="World Cup Bot Health Check")


def _calculate_points(prediction, actual_winner: str, home_score: int, away_score: int) -> int:
    points = 0
    if prediction.predict_winner == actual_winner:
        points = 1
    if prediction.predict_home_score == home_score and prediction.predict_away_score == away_score:
        points = 3
    return points


def _build_settlement_embed(match, home_score: int, away_score: int, scorers: list[str]) -> discord.Embed:
    embed = discord.Embed(
        title=f"🏁 結算報告：{match.home_team} {home_score} - {away_score} {match.away_team}",
        color=discord.Color.gold(),
    )
    if scorers:
        embed.description = "\n".join(scorers)
    else:
        embed.description = "本場無人獲得積分。"
    return embed


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "bot_ready": bot.is_ready(),
        "test_mode": TEST_MODE,
    }

@app.head("/")
def health_check_head():
    return Response(status_code=200)


def run_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


@bot.event
async def on_ready():
    logger.info("Logged in as %s (TEST_MODE=%s)", bot.user, TEST_MODE)

    try:
        active_matches = games_db.get_active_matches()
        for match in active_matches:
            bot.add_view(MatchPredictionView(
                fixture_id=match.fixture_id,
                match_type=match.match_type,
                home_team=match.home_team,
                away_team=match.away_team
            ))
        logger.info("已成功重新載入 %d 場賽事的常駐按鈕監聽！", len(active_matches))
    except Exception:
        logger.exception("無法重新載入常駐按鈕監聽")

    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d slash command(s)", len(synced))
    except Exception:
        logger.exception("Failed to sync slash commands")


@bot.tree.command(name="sync_matches", description="同步未來 30 小時內的賽事並發布預測卡片")
@app_commands.default_permissions(administrator=True)
async def sync_matches(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    try:
        all_games = api_client.fetch_games()
        upcoming = api_client.filter_games_within_hours(all_games, hours=30)
        inserted = games_db.sync_upcoming_games(upcoming)
        unposted = games_db.get_unposted_matches_within_hours(hours=30)

        channel = bot.get_channel(get_channel_id())
        if channel is None:
            await interaction.followup.send("❌ 找不到目標頻道，請檢查 CHANNEL_ID 設定。", ephemeral=True)
            return

        posted = 0
        for match in unposted:
            embed = build_match_embed(match)
            view = MatchPredictionView(
                fixture_id=match.fixture_id,
                match_type=match.match_type,
                home_team=match.home_team,
                away_team=match.away_team,
            )
            await channel.send(embed=embed, view=view)
            games_db.mark_as_posted(match.fixture_id)
            posted += 1

        await interaction.followup.send(
            f"✅ 同步完成：新增 {inserted} 場，發布 {posted} 張預測卡片。",
            ephemeral=True,
        )
    except Exception as exc:
        logger.exception("sync_matches failed")
        await interaction.followup.send(f"❌ 同步失敗：{exc}", ephemeral=True)


@bot.tree.command(name="settle_predictions", description="結算已結束賽事的預測並發放積分")
@app_commands.default_permissions(administrator=True)
async def settle_predictions(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    try:
        pending = games_db.get_matches_ready_for_settlement(hours_after_start=2.5)
        if not pending:
            await interaction.followup.send("ℹ️ 目前沒有需要結算的賽事。", ephemeral=True)
            return

        channel = bot.get_channel(get_channel_id())
        if channel is None:
            await interaction.followup.send("❌ 找不到目標頻道，請檢查 CHANNEL_ID 設定。", ephemeral=True)
            return

        try:
            all_games = api_client.fetch_games()
            games_lookup = {game.fixture_id: game for game in all_games}
        except Exception as exc:
            logger.exception("Failed to fetch games from API during settlement")
            await interaction.followup.send(f"❌ 結算失敗，無法取得 API 賽事資料：{exc}", ephemeral=True)
            return
        
        settled_count = 0
        for match in pending:
            game = games_lookup.get(match.fixture_id)
            
            if game is None or not api_client.is_game_finished(game):
                continue
            if game.home_score is None or game.away_score is None:
                continue

            actual_winner = api_client.determine_winner(
                game.home_score, game.away_score, match.match_type
            )
            predictions = predictions_db.get_predictions_for_fixture(match.fixture_id)
            scorers: list[str] = []

            for pred in predictions:
                points = _calculate_points(pred, actual_winner, game.home_score, game.away_score)
                if points > 0:
                    leaderboard_db.add_points(pred.user_id, pred.username, points)
                    reason = "比分全對" if points == 3 else "勝負正確"
                    scorers.append(f"• {pred.username} +{points} 分（{reason}）")

            games_db.update_match_result(match.fixture_id, game.home_score, game.away_score)
            embed = _build_settlement_embed(match, game.home_score, game.away_score, scorers)
            await channel.send(embed=embed)
            settled_count += 1

        await interaction.followup.send(
            f"✅ 結算完成，共處理 {settled_count} 場賽事。",
            ephemeral=True,
        )
    except Exception as exc:
        logger.exception("settle_predictions failed")
        await interaction.followup.send(f"❌ 結算失敗：{exc}", ephemeral=True)


@bot.tree.command(name="leaderboard", description="查詢預測積分排行榜（前 10 名）")
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()

    try:
        rows = leaderboard_db.get_top_n(limit=10)
        embed = discord.Embed(
            title="🏆 預測積分排行榜",
            color=discord.Color.blue(),
        )

        if not rows:
            embed.description = "目前尚無積分紀錄，快來預測吧！"
        else:
            lines = []
            medals = ["🥇", "🥈", "🥉"]
            for idx, row in enumerate(rows, start=1):
                prefix = medals[idx - 1] if idx <= 3 else f"{idx}."
                lines.append(f"{prefix} **{row.username}** — {row.points} 分")
            embed.description = "\n".join(lines)

        await interaction.followup.send(embed=embed)
    except Exception as exc:
        logger.exception("leaderboard failed")
        await interaction.followup.send(f"❌ 查詢失敗：{exc}", ephemeral=True)


def main():
    server_thread = threading.Thread(target=run_fastapi, daemon=True)
    server_thread.start()
    logger.info("FastAPI health check running on port %s", PORT)
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()