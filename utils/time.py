# utils/time.py
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
TAIPEI_TZ = ZoneInfo("Asia/Taipei")

STADIUM_TIMEZONES = {
    "1": "America/Mexico_City",   # 墨西哥城 - Estadio Azteca (CST, UTC-6)
    "2": "America/Mexico_City",   # 瓜達拉哈拉 - Estadio Akron (CST, UTC-6)
    "3": "America/Monterrey",     # 蒙特雷 - Estadio BBVA (CST, UTC-6)
    "4": "America/Chicago",       # 達拉斯 - AT&T Stadium (CDT, UTC-5)
    "5": "America/Chicago",       # 休士頓 - NRG Stadium (CDT, UTC-5)
    "6": "America/Chicago",       # 堪薩斯城 - Arrowhead Stadium (CDT, UTC-5)
    "7": "America/New_York",      # 亞特蘭大 - Mercedes-Benz Stadium (EDT, UTC-4)
    "8": "America/New_York",      # 邁阿密 - Hard Rock Stadium (EDT, UTC-4)
    "9": "America/New_York",      # 波士頓 - Gillette Stadium (EDT, UTC-4)
    "10": "America/New_York",     # 費城 - Lincoln Financial Field (EDT, UTC-4)
    "11": "America/New_York",     # 紐約 - MetLife Stadium (EDT, UTC-4)
    "12": "America/Toronto",      # 多倫多 - BMO Field (EDT, UTC-4)
    "13": "America/Vancouver",    # 溫哥華 - BC Place (PDT, UTC-7)
    "14": "America/Los_Angeles",  # 西雅圖 - Lumen Field (PDT, UTC-7)
    "15": "America/Los_Angeles",  # 舊金山 - Levi's Stadium (PDT, UTC-7)
    "16": "America/Los_Angeles",  # 洛杉磯 - SoFi Stadium (PDT, UTC-7)
}


def parse_api_datetime(date_str: str, stadium_id: str | int = "1") -> datetime:
    # 確保 stadium_id 是字串
    st_id = str(stadium_id)
    # 取得球場時區，若找不到則預設多倫多/紐約時區 (EDT)
    stadium_tz_name = STADIUM_TIMEZONES.get(st_id, "America/New_York")
    
    # 1. 讀取無時區的原始時間
    dt = datetime.strptime(date_str, "%m/%d/%Y %H:%M")
    
    # 2. 標記為球場當地的時區
    dt_local = dt.replace(tzinfo=ZoneInfo(stadium_tz_name))
    
    # 3. 轉換為標準 UTC 時間並回傳
    return dt_local.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def format_taipei_time(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(TAIPEI_TZ).strftime("%Y/%m/%d %H:%M")