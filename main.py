import asyncio
import logging
import threading

import discord
import uvicorn
from discord.ext import commands
from fastapi import FastAPI

from config import DISCORD_TOKEN, PORT, TEST_MODE

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


def main():
    server_thread = threading.Thread(target=run_fastapi, daemon=True)
    server_thread.start()
    logger.info("FastAPI health check running on port %s", PORT)
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
