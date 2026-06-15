import discord

from database.base import format_taipei_time
from database.games import MatchRow


def build_match_embed(match: MatchRow) -> discord.Embed:
    stage = match.match_type.upper()
    group = f"Group {match.group_name}" if match.group_name else stage

    embed = discord.Embed(
        title=f"⚽ {match.home_team} vs {match.away_team}",
        description="點擊下方按鈕提交或修改你的預測（開賽前可重複修改）",
        color=discord.Color.green(),
    )
    embed.add_field(name="階段", value=group, inline=True)
    embed.add_field(name="開賽時間 (台北)", value=format_taipei_time(match.start_time), inline=True)
    embed.add_field(name="賽事 ID", value=str(match.fixture_id), inline=True)
    embed.set_footer(text="預測勝負 +1 分｜比分全對 +3 分")
    return embed


class MatchPredictionView(discord.ui.View):
    def __init__(self, fixture_id: int, match_type: str, home_team: str, away_team: str):
        super().__init__(timeout=None)
        self.fixture_id = fixture_id
        self.match_type = match_type
        self.home_team = home_team
        self.away_team = away_team

        winner_btn = discord.ui.Button(
            label="預測勝負",
            style=discord.ButtonStyle.primary,
            custom_id=f"predict_winner:{fixture_id}",
        )
        winner_btn.callback = self._predict_winner_callback
        self.add_item(winner_btn)

        score_btn = discord.ui.Button(
            label="預測比分",
            style=discord.ButtonStyle.secondary,
            custom_id=f"predict_score:{fixture_id}",
        )
        score_btn.callback = self._predict_score_callback
        self.add_item(score_btn)

    async def _predict_winner_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("預測功能即將開放，請稍後再試。", ephemeral=True)

    async def _predict_score_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("預測功能即將開放，請稍後再試。", ephemeral=True)
