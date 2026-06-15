import logging
import threading

import discord
import uvicorn
from discord import app_commands
from discord.ext import commands
from fastapi import FastAPI

import api_client
from config import DISCORD_TOKEN, PORT, TEST_MODE, get_channel_id
from database import games as games_db
from views import MatchPredictionView, build_match_embed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

app = FastAPI(title="World Cup Bot Health Check")


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


def main():
    server_thread = threading.Thread(target=run_fastapi, daemon=True)
    server_thread.start()
    logger.info("FastAPI health check running on port %s", PORT)
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
