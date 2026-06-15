import discord

from database import predictions as predictions_db
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


class ScorePredictionModal(discord.ui.Modal, title="預測比分"):
    home_score_input = discord.ui.TextInput(
        label="主隊得分",
        placeholder="例如：2",
        min_length=1,
        max_length=2,
    )
    away_score_input = discord.ui.TextInput(
        label="客隊得分",
        placeholder="例如：1",
        min_length=1,
        max_length=2,
    )

    def __init__(self, fixture_id: int):
        super().__init__()
        self.fixture_id = fixture_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            home_score = int(self.home_score_input.value)
            away_score = int(self.away_score_input.value)
            if home_score < 0 or away_score < 0:
                raise ValueError("negative score")
        except ValueError:
            await interaction.response.send_message("❌ 請輸入有效的非負整數比分。", ephemeral=True)
            return

        if home_score > away_score:
            winner = "HOME"
        elif away_score > home_score:
            winner = "AWAY"
        else:
            winner = "DRAW"

        _, message = predictions_db.upsert_prediction(
            user_id=str(interaction.user.id),
            username=interaction.user.display_name,
            fixture_id=self.fixture_id,
            predict_winner=winner,
            predict_home_score=home_score,
            predict_away_score=away_score,
        )
        await interaction.response.send_message(message, ephemeral=True)


class WinnerChoiceView(discord.ui.View):
    def __init__(self, fixture_id: int, match_type: str, home_team: str, away_team: str):
        super().__init__(timeout=120)
        self.fixture_id = fixture_id
        self.match_type = match_type
        self.home_team = home_team
        self.away_team = away_team

        self.add_item(WinnerButton("HOME", f"{home_team} 勝", discord.ButtonStyle.success))
        if match_type == "group":
            self.add_item(WinnerButton("DRAW", "和局", discord.ButtonStyle.secondary))
        self.add_item(WinnerButton("AWAY", f"{away_team} 勝", discord.ButtonStyle.danger))


class WinnerButton(discord.ui.Button):
    def __init__(self, winner: str, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style)
        self.winner = winner

    async def callback(self, interaction: discord.Interaction):
        view: WinnerChoiceView = self.view
        _, message = predictions_db.upsert_prediction(
            user_id=str(interaction.user.id),
            username=interaction.user.display_name,
            fixture_id=view.fixture_id,
            predict_winner=self.winner,
        )
        await interaction.response.send_message(message, ephemeral=True)


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
        if predictions_db.is_match_locked(self.fixture_id):
            await interaction.response.send_message(predictions_db.LOCKED_MESSAGE, ephemeral=True)
            return

        view = WinnerChoiceView(
            fixture_id=self.fixture_id,
            match_type=self.match_type,
            home_team=self.home_team,
            away_team=self.away_team,
        )
        await interaction.response.send_message("請選擇預測結果：", view=view, ephemeral=True)

    async def _predict_score_callback(self, interaction: discord.Interaction):
        if predictions_db.is_match_locked(self.fixture_id):
            await interaction.response.send_message(predictions_db.LOCKED_MESSAGE, ephemeral=True)
            return
        await interaction.response.send_modal(ScorePredictionModal(self.fixture_id))
