import discord

from database import predictions as predictions_db
from database import leaderboard as leaderboard_db
from utils import format_taipei_time
from database.games import MatchRow


def build_match_embed(match: MatchRow) -> discord.Embed:
    stage = match.match_type.upper()
    group = f"Group {match.group_name}" if match.group_name else stage

    embed = discord.Embed(
        title=f"⚽ {match.home_team} vs {match.away_team}",
        description="點擊下方 `[🎮 進入預測中心]` 提交預測、修改、或看大家預測！",
        color=discord.Color.green(),
    )
    embed.add_field(name="階段", value=group, inline=True)
    embed.add_field(name="開賽時間 (台北)", value=format_taipei_time(match.start_time), inline=True)
    embed.add_field(name="賽事 ID", value=str(match.fixture_id), inline=True)
    embed.set_footer(text="預測勝負 +1 分｜比分全對 +3 分")
    return embed


async def build_private_hub_embed(fixture_id: int, home_team: str, away_team: str, user_pred, preds: list) -> discord.Embed:
    if not user_pred:
        user_pred_str = "❌ *您尚未對本場賽事進行任何預測。*"
    else:
        winner_display = "和局"
        if user_pred.predict_winner == "HOME":
            winner_display = f"{home_team} 勝"
        elif user_pred.predict_winner == "AWAY":
            winner_display = f"{away_team} 勝"
        user_pred_str = f"🎯 比分：**{home_team} {user_pred.predict_home_score} - {user_pred.predict_away_score} {away_team}** ({winner_display})"

    if not preds:
        all_preds_str = "📊 *目前尚無任何人進行過預測。*"
    else:
        lines = []
        for p in preds:
            w_disp = "和局"
            if p.predict_winner == "HOME":
                w_disp = f"{home_team} 勝"
            elif p.predict_winner == "AWAY":
                w_disp = f"{away_team} 勝"
            lines.append(f"• **{p.username}**：{p.predict_home_score} - {p.predict_away_score} ({w_disp})")
        all_preds_str = "\n".join(lines)

    is_locked = predictions_db.is_match_locked(fixture_id)
    status_note = "*(🔒 比賽已開始，預測已鎖定無法再修改)*" if is_locked else "*(⏳ 比賽尚未開始，開賽前您隨時可以再次點選按鈕修改預測)*"

    embed = discord.Embed(
        title=f"🎮 {home_team} vs {away_team} — 預測控制中心",
        description=status_note,
        color=discord.Color.blue(),
    )
    embed.add_field(name="👤 您的目前預測", value=user_pred_str, inline=False)
    embed.add_field(name="📊 大家的預測清單", value=all_preds_str, inline=False)
    embed.set_footer(text=f"賽事 ID: {fixture_id} | 點擊下方 [🔄 重新整理] 獲取最新資料")
    return embed


async def build_leaderboard_embed() -> discord.Embed:
    """動態組裝並回傳【積分排行榜】Embed"""
    rows = leaderboard_db.get_top_n(limit=10)
    embed = discord.Embed(
        title="🏆 世界盃預測 — 積分排行榜",
        color=discord.Color.gold(),
    )

    if not rows:
        embed.description = "目前尚無積分紀錄，快來進行第一次預測吧！"
    else:
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for idx, row in enumerate(rows, start=1):
            prefix = medals[idx - 1] if idx <= 3 else f"{idx}."
            lines.append(f"{prefix} **{row.username}** — {row.points} 分")
        embed.description = "\n".join(lines)
    
    embed.set_footer(text="積分規則：勝負正確 +1 分 ｜ 比分全對 +3 分")
    return embed


async def build_history_embed(user_id: str, username: str) -> discord.Embed:
    history = predictions_db.get_user_prediction_history(user_id)
    embed = discord.Embed(
        title=f"📜 {username} 的預測歷史紀錄 (全場次)",
        color=discord.Color.teal(),
    )

    if not history:
        embed.description = "目前尚無任何預測歷史紀錄，快點擊 `[📝 進行預測]` 開始吧！"
    else:
        from utils.time import TAIPEI_TZ, UTC
        lines = []
        for h in history:
            pts_icon = "⏳"
            if h["is_settled"]:
                actual_winner = "DRAW"
                if h["actual_home"] > h["actual_away"]:
                    actual_winner = "HOME"
                elif h["actual_away"] > h["actual_home"]:
                    actual_winner = "AWAY"

                pts = 0
                if h["predict_winner"] == actual_winner:
                    pts = 1
                if h["predict_home"] == h["actual_home"] and h["predict_away"] == h["actual_away"]:
                    pts = 3

                if pts == 3:
                    pts_icon = "🎯 +3"
                elif pts == 1:
                    pts_icon = "🔺 +1"
                else:
                    pts_icon = "❌ +0"

            actual_score = f"{h['actual_home']}-{h['actual_away']}" if h["is_settled"] else "---"
            
            dt = h["start_time"]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            local_dt = dt.astimezone(TAIPEI_TZ)
            date_str = f"{local_dt.month}/{local_dt.day}"
            
            lines.append(
                f"`{date_str:<5}` {h['home_team']} vs {h['away_team']} "
                f"| 預測 `{h['predict_home']}-{h['predict_away']}` "
                f"| 賽果 `{actual_score}` {pts_icon}"
            )
        
        embed.description = "\n".join(lines[:95])
        
    embed.set_footer(text="🎯：比分全對 ｜ 🔺：勝負正確 ｜ ⏳：未開賽 ｜ ❌：未得分")
    return embed


class ScorePredictionModal(discord.ui.Modal):
    def __init__(self, fixture_id: int, home_team: str, away_team: str, existing_pred=None):
        super().__init__(title="預測比分")
        self.fixture_id = fixture_id
        self.home_team = home_team
        self.away_team = away_team
        
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
            placeholder="例如：1",
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

        success, message = predictions_db.upsert_prediction(
            user_id=str(interaction.user.id),
            username=interaction.user.display_name,
            fixture_id=self.fixture_id,
            predict_winner=winner,
            predict_home_score=home_score,
            predict_away_score=away_score,
        )

        if success:
            updated_pred = predictions_db.get_prediction(str(interaction.user.id), self.fixture_id)
            preds = predictions_db.get_predictions_for_fixture(self.fixture_id)
            
            new_embed = await build_private_hub_embed(
                self.fixture_id, self.home_team, self.away_team, updated_pred, preds
            )
            
            new_view = PrivateHubView(self.fixture_id, self.home_team, self.away_team, existing_pred=updated_pred)
            await interaction.edit_original_response(embed=new_embed, view=new_view)
        else:
            await interaction.followup.send(message, ephemeral=True)


class MatchSelect(discord.ui.Select):
    def __init__(self, open_matches: list[MatchRow], current_fixture_id: int):
        options = []
        for m in open_matches:
            label = f"{m.home_team} vs {m.away_team}"
            description = f"賽事 ID: {m.fixture_id}"
            
            is_current = m.fixture_id == current_fixture_id
            
            options.append(discord.SelectOption(
                label=label, 
                value=str(m.fixture_id),
                description=description,
                default=is_current 
            ))
        super().__init__(
            placeholder="🔽 跨賽事快速預測通道...", 
            min_values=1, 
            max_values=1, 
            options=options,
            row=2
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected_id = int(self.values[0])
        
        from database.games import get_match
        match = get_match(selected_id)
        if not match:
            await interaction.followup.send("❌ 找不到該場賽事資訊。", ephemeral=True)
            return
        
        pred = predictions_db.get_prediction(str(interaction.user.id), selected_id)
        preds = predictions_db.get_predictions_for_fixture(selected_id)
        
        new_view = PrivateHubView(selected_id, match.home_team, match.away_team, existing_pred=pred)
        new_embed = await build_private_hub_embed(selected_id, match.home_team, match.away_team, pred, preds)
        await interaction.edit_original_response(embed=new_embed, view=new_view)


class PrivateHubView(discord.ui.View):
    def __init__(self, fixture_id: int, home_team: str, away_team: str, existing_pred=None):
        super().__init__(timeout=180)
        self.fixture_id = fixture_id
        self.home_team = home_team
        self.away_team = away_team
        self.existing_pred = existing_pred
        
        from database.games import get_predictable_matches
        open_matches = get_predictable_matches()
        if len(open_matches) > 1:
            self.add_item(MatchSelect(open_matches, fixture_id))

    @discord.ui.button(label="📝 進行預測 / 修改", style=discord.ButtonStyle.primary, row=0)
    async def predict_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if predictions_db.is_match_locked(self.fixture_id):
            await interaction.response.send_message(predictions_db.LOCKED_MESSAGE, ephemeral=True)
            return
        
        await interaction.response.send_modal(
            ScorePredictionModal(
                fixture_id=self.fixture_id,
                home_team=self.home_team,
                away_team=self.away_team,
                existing_pred=self.existing_pred
            )
        )

    @discord.ui.button(label="🔄 重新整理數據", style=discord.ButtonStyle.secondary, row=0)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        updated_pred = predictions_db.get_prediction(str(interaction.user.id), self.fixture_id)
        preds = predictions_db.get_predictions_for_fixture(self.fixture_id)
        self.existing_pred = updated_pred
        
        new_embed = await build_private_hub_embed(
            self.fixture_id, self.home_team, self.away_team, updated_pred, preds
        )
        await interaction.edit_original_response(embed=new_embed, view=self)

    @discord.ui.button(label="🏆 查看積分榜", style=discord.ButtonStyle.secondary, row=1)
    async def leaderboard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        leaderboard_embed = await build_leaderboard_embed()
        view = LeaderboardPageView(self.fixture_id, self.home_team, self.away_team, existing_pred=self.existing_pred)
        await interaction.edit_original_response(embed=leaderboard_embed, view=view)

    @discord.ui.button(label="📜 預測歷史", style=discord.ButtonStyle.secondary, row=1)
    async def history_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        history_embed = await build_history_embed(str(interaction.user.id), interaction.user.display_name)
        view = HistoryPageView(self.fixture_id, self.home_team, self.away_team, existing_pred=self.existing_pred)
        
        await interaction.edit_original_response(embed=history_embed, view=view)

    @discord.ui.button(label="❌ 關閉", style=discord.ButtonStyle.danger, row=1)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()


class LeaderboardPageView(discord.ui.View):
    def __init__(self, fixture_id: int, home_team: str, away_team: str, existing_pred=None):
        super().__init__(timeout=180)
        self.fixture_id = fixture_id
        self.home_team = home_team
        self.away_team = away_team
        self.existing_pred = existing_pred

    @discord.ui.button(label="⬅️ 返回預測中心", style=discord.ButtonStyle.primary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        preds = predictions_db.get_predictions_for_fixture(self.fixture_id)
        hub_embed = await build_private_hub_embed(
            self.fixture_id, self.home_team, self.away_team, self.existing_pred, preds
        )
        view = PrivateHubView(self.fixture_id, self.home_team, self.away_team, existing_pred=self.existing_pred)
        await interaction.edit_original_response(embed=hub_embed, view=view)

    @discord.ui.button(label="❌ 關閉", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()


class HistoryPageView(discord.ui.View):
    def __init__(self, fixture_id: int, home_team: str, away_team: str, existing_pred=None):
        super().__init__(timeout=180)
        self.fixture_id = fixture_id
        self.home_team = home_team
        self.away_team = away_team
        self.existing_pred = existing_pred

    @discord.ui.button(label="⬅️ 返回預測中心", style=discord.ButtonStyle.primary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        preds = predictions_db.get_predictions_for_fixture(self.fixture_id)
        hub_embed = await build_private_hub_embed(
            self.fixture_id, self.home_team, self.away_team, self.existing_pred, preds
        )
        view = PrivateHubView(self.fixture_id, self.home_team, self.away_team, existing_pred=self.existing_pred)
        await interaction.edit_original_response(embed=hub_embed, view=view)

    @discord.ui.button(label="❌ 關閉", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()


class MatchPredictionView(discord.ui.View):
    def __init__(self, fixture_id: int, match_type: str, home_team: str, away_team: str):
        super().__init__(timeout=None)
        self.fixture_id = fixture_id
        self.match_type = match_type
        self.home_team = home_team
        self.away_team = away_team

        hub_btn = discord.ui.Button(
            label="🎮 進入預測中心",
            style=discord.ButtonStyle.primary,
            custom_id=f"predict_hub:{fixture_id}",
        )
        hub_btn.callback = self._predict_hub_callback
        self.add_item(hub_btn)

    async def _predict_hub_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        pred = predictions_db.get_prediction(str(interaction.user.id), self.fixture_id)
        preds = predictions_db.get_predictions_for_fixture(self.fixture_id)

        embed = await build_private_hub_embed(
            self.fixture_id, self.home_team, self.away_team, pred, preds
        )
        
        view = PrivateHubView(self.fixture_id, self.home_team, self.away_team, existing_pred=pred)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)