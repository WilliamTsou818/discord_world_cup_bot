# views.py
import discord

from database import predictions as predictions_db
from utils import format_taipei_time
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


class ScorePredictionModal(discord.ui.Modal):
    def __init__(self, fixture_id: int, home_team: str, away_team: str, existing_pred=None):
        super().__init__(title="預測比分")
        self.fixture_id = fixture_id
        
        default_home = str(existing_pred.predict_home_score) if existing_pred else ""
        default_away = str(existing_pred.predict_away_score) if existing_pred else ""

        self.home_score_input = discord.ui.TextInput(
            label=f"{home_team} 的預測得分",
            placeholder="例如：2",
            default=default_home,
            min_length=1,
            max_length=2,
        )
        self.away_score_input = discord.ui.TextInput(
            label=f"{away_team} 的預測得分",
            placeholder="placeholder：1",
            default=default_away,
            min_length=1,
            max_length=2,
        )
        self.add_item(self.home_score_input)
        self.add_item(self.away_score_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            home_score = int(self.home_score_input.value)
            away_score = int(self.away_score_input.value)
            if home_score < 0 or away_score < 0:
                raise ValueError("negative score")
        except ValueError:
            await interaction.followup.send("❌ 請輸入有效的非負整數比分。", ephemeral=True)
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
        await interaction.followup.send(message, ephemeral=True)


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
        
        await interaction.response.defer(ephemeral=True)
        
        _, message = predictions_db.upsert_prediction(
            user_id=str(interaction.user.id),
            username=interaction.user.display_name,
            fixture_id=view.fixture_id,
            predict_winner=self.winner,
        )
        await interaction.followup.send(message, ephemeral=True)


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

        # 🔍 我的預測查詢按鈕
        check_btn = discord.ui.Button(
            label="🔍 我的預測",
            style=discord.ButtonStyle.success,
            custom_id=f"check_prediction:{fixture_id}",
        )
        check_btn.callback = self._check_prediction_callback
        self.add_item(check_btn)

        # 📊 大家預測查詢按鈕
        all_preds_btn = discord.ui.Button(
            label="📊 大家預測",
            style=discord.ButtonStyle.secondary,
            custom_id=f"all_predictions:{fixture_id}",
        )
        all_preds_btn.callback = self._all_predictions_callback
        self.add_item(all_preds_btn)

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
            
        existing_pred = predictions_db.get_prediction(str(interaction.user.id), self.fixture_id)
        
        await interaction.response.send_modal(
            ScorePredictionModal(
                fixture_id=self.fixture_id,
                home_team=self.home_team,
                away_team=self.away_team,
                existing_pred=existing_pred
            )
        )

    async def _check_prediction_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        pred = predictions_db.get_prediction(str(interaction.user.id), self.fixture_id)
        
        if not pred:
            await interaction.followup.send(
                f"🔍 **你尚未對 {self.home_team} vs {self.away_team} (賽事 ID {self.fixture_id}) 進行預測！**\n"
                f"請點擊下方 `[預測勝負]` 或 `[預測比分]` 開始預測。",
                ephemeral=True
            )
            return

        winner_display = "和局"
        if pred.predict_winner == "HOME":
            winner_display = f"{self.home_team} 勝"
        elif pred.predict_winner == "AWAY":
            winner_display = f"{self.away_team} 勝"

        await interaction.followup.send(
            f"🔍 **您在 {self.home_team} vs {self.away_team} (賽事 ID {self.fixture_id}) 的預測紀錄：**\n"
            f"• 預測勝負：**{winner_display}**\n"
            f"• 預測比分：**{self.home_team} {pred.predict_home_score} - {pred.predict_away_score} {self.away_team}**\n\n"
            f"*(開賽前您隨時可以再次點擊預測按鈕進行修改)*",
            ephemeral=True
        )

    async def _all_predictions_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        preds = predictions_db.get_predictions_for_fixture(self.fixture_id)
        
        if not preds:
            await interaction.followup.send(
                f"📊 **目前尚未有任何人對 {self.home_team} vs {self.away_team} (賽事 ID {self.fixture_id}) 進行預測。**\n"
                f"快來搶先按下預測按鈕，當第一個預測的人吧！",
                ephemeral=True
            )
            return

        lines = []
        for p in preds:
            winner_display = "和局"
            if p.predict_winner == "HOME":
                winner_display = f"{self.home_team} 勝"
            elif p.predict_winner == "AWAY":
                winner_display = f"{self.away_team} 勝"
            
            lines.append(f"• **{p.username}**：{self.home_team} {p.predict_home_score} - {p.predict_away_score} {self.away_team} ({winner_display})")

        preds_list_str = "\n".join(lines)
        
        is_locked = predictions_db.is_match_locked(self.fixture_id)
        status_note = "*(🔒 比賽已開始，預測已鎖定無法再修改)*" if is_locked else "*(⏳ 比賽尚未開始，開賽前您隨時可以再次點選按鈕修改預測)*"

        await interaction.followup.send(
            f"📊 **{self.home_team} vs {self.away_team} (賽事 ID {self.fixture_id}) 的大家預測清單：**\n"
            f"{status_note}\n\n"
            f"{preds_list_str}",
            ephemeral=True
        )