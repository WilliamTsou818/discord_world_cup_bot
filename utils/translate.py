# utils/text_formatter.py

TEAM_TRANSLATIONS = {
    # A組 - L組 完整 48 隊
    "Argentina": "阿根廷",
    "Algeria": "阿爾及利亞",
    "Australia": "澳洲",
    "Austria": "奧地利",
    "Belgium": "比利時",
    "Brazil": "巴西",
    "Bosnia and Herzegovina": "波士尼亞與赫塞哥維納",
    "Canada": "加拿大",
    "Cape Verde": "維德角",
    "Colombia": "哥倫比亞",
    "Croatia": "克羅埃西亞",
    "Curaçao": "庫拉索",
    "Czech Republic": "捷克",
    "Democratic Republic of the Congo": "剛果民主共和國",
    "Ecuador": "厄瓜多",
    "Egypt": "埃及",
    "England": "英格蘭",
    "France": "法國",
    "Germany": "德國",
    "Ghana": "迦納",
    "Haiti": "海地",
    "Iran": "伊朗",
    "Iraq": "伊拉克",
    "Ivory Coast": "象牙海岸",
    "Japan": "日本",
    "Jordan": "約旦",
    "Mexico": "墨西哥",
    "Morocco": "摩洛哥",
    "Netherlands": "荷蘭",
    "New Zealand": "紐西蘭",
    "Norway": "挪威",
    "Panama": "巴拿馬",
    "Paraguay": "巴拉圭",
    "Portugal": "葡萄牙",
    "Qatar": "卡達",
    "Saudi Arabia": "沙烏地阿拉伯",
    "Scotland": "蘇格蘭",
    "Senegal": "塞內加爾",
    "South Africa": "南非",
    "South Korea": "南韓",
    "Spain": "西班牙",
    "Sweden": "瑞典",
    "Switzerland": "瑞士",
    "Tunisia": "突尼西亞",
    "Turkey": "土耳其",
    "United States": "美國",
    "Uruguay": "烏拉圭",
    "Uzbekistan": "烏茲別克"
}


def translate_team_name(en_name: str) -> str:
    if not en_name:
        return "TBD"
    
    cleaned_name = en_name.strip()
    return TEAM_TRANSLATIONS.get(cleaned_name, cleaned_name)