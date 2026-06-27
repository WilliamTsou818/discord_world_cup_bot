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

        api_is_active = True
        games_lookup = {}
        try:
            all_games = api_client.fetch_games()
            games_lookup = {game.fixture_id: game for game in all_games}
        except Exception as exc:
            logger.warning("API offline. Switching to DB fallback: %s", exc)
            api_is_active = False

        settled_count = 0
        for match in pending:
            home_score = None
            away_score = None

            if api_is_active:
                game = games_lookup.get(match.fixture_id)
                if game is None or not api_client.is_game_finished(game):
                    continue
                home_score = game.home_score
                away_score = game.away_score
            else:
                db_match = games_db.get_match(match.fixture_id)
                if db_match is None or db_match.home_score is None or db_match.away_score is None:
                    continue
                home_score = db_match.home_score
                away_score = db_match.away_score

            actual_winner = api_client.determine_winner(
                home_score, away_score, match.match_type
            )
            predictions = predictions_db.get_predictions_for_fixture(match.fixture_id)
            scorers: list[str] = []

            for pred in predictions:
                points = _calculate_points(pred, actual_winner, home_score, away_score)
                if points > 0:
                    leaderboard_db.add_points(pred.user_id, pred.username, points)
                    reason = "比分全對" if points == 3 else "勝負正確"
                    scorers.append(f"• {pred.username} +{points} 分（{reason}）")

            games_db.update_match_result(match.fixture_id, home_score, away_score)
            embed = _build_settlement_embed(match, home_score, away_score, scorers)
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


@bot.tree.command(name="admin_init_all_matches", description="初始化世足全部 104 場賽事")
@app_commands.default_permissions(administrator=True)
async def admin_init_all_matches(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        all_games = api_client.fetch_games()
        inserted = games_db.sync_upcoming_games(all_games)
        await interaction.followup.send(
            f"✅ 初始化完成！共成功建立 {inserted} 場全新賽事，已建立的賽事未受影響。",
            ephemeral=True,
        )
    except Exception as exc:
        logger.exception("admin_init_all_matches failed")
        await interaction.followup.send(f"❌ 初始化失敗：{exc}", ephemeral=True)


@bot.tree.command(name="admin_set_teams", description="手動將淘汰賽 TBD 佔位符改為真實對陣國家")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(fixture_id="賽事 ID", home_team="主隊國家名稱", away_team="客隊國家名稱")
async def admin_set_teams(interaction: discord.Interaction, fixture_id: int, home_team: str, away_team: str):
    await interaction.response.defer(ephemeral=True)
    try:
        match = games_db.get_match(fixture_id)
        if not match:
            await interaction.followup.send(f"❌ 找不到賽事 ID {fixture_id} 的資料。", ephemeral=True)
            return

        games_db.update_match_teams(fixture_id, home_team, away_team)
        await interaction.followup.send(
            f"✅ 成功將賽事 ID {fixture_id} 的對陣更新為：**{home_team} vs {away_team}**！",
            ephemeral=True,
        )
    except Exception as exc:
        logger.exception("admin_set_teams failed")
        await interaction.followup.send(f"❌ 更新失敗：{exc}", ephemeral=True)

@bot.tree.command(name="admin_set_score", description="手動錄入特定賽事比分，供結算使用")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(fixture_id="賽事 ID", home_score="主隊實際得分", away_score="客隊實際得分")
async def admin_set_score(interaction: discord.Interaction, fixture_id: int, home_score: int, away_score: int):
    await interaction.response.defer(ephemeral=True)
    try:
        match = games_db.get_match(fixture_id)
        if not match:
            await interaction.followup.send(f"❌ 找不到賽事 ID {fixture_id} 的資料。", ephemeral=True)
            return

        with games_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE {TABLE_MATCHES} SET home_score = %s, away_score = %s WHERE fixture_id = %s".format(TABLE_MATCHES=games_db.TABLE_MATCHES),
                    (home_score, away_score, fixture_id),
                )
        await interaction.followup.send(
            f"✅ 成功手動錄入賽事 ID {fixture_id} 的實際比分為 {home_score} - {away_score}！請接續執行 /settle_predictions 指令發放積分。",
            ephemeral=True,
        )
    except Exception as exc:
        logger.exception("admin_set_score failed")
        await interaction.followup.send(f"❌ 錄入失敗：{exc}", ephemeral=True)

def main():
    server_thread = threading.Thread(target=run_fastapi, daemon=True)
    server_thread.start()
    logger.info("FastAPI health check running on port %s", PORT)
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()