import os
import sys
import string
import random
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from sqlalchemy import or_

# パス設定
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from app import models
from app.database import Base, engine
from app.utils.security import get_password_hash

# --- [1. 識別コード生成関数] ---
def generate_code(length=7, prefix=""):
    chars = string.ascii_letters + string.digits
    random_len = length - len(prefix)
    random_str = ''.join(random.choice(chars) for _ in range(random_len))
    return f"{prefix}{random_str}"

# --- [2. 地域データの定義] ---
TOKYO_23_WARDS = [
    "千代田区 (Chiyoda-ku)", "中央区 (Chuo-ku)", "港区 (Minato-ku)", "新宿区 (Shinjuku-ku)",
    "文京区 (Bunkyo-ku)", "台東区 (Taito-ku)", "墨田区 (Sumida-ku)", "江東区 (Koto-ku)",
    "品川区 (Shinagawa-ku)", "目黒区 (Meguro-ku)", "大田区 (Ota-ku)", "世田谷区 (Setagaya-ku)",
    "渋谷区 (Shibuya-ku)", "中野区 (Nakano-ku)", "杉並区 (Suginami-ku)", "豊島区 (Toshima-ku)",
    "北区 (Kita-ku)", "荒川区 (Arakawa-ku)", "板橋区 (Itabashi-ku)", "練馬区 (Nerima-ku)",
    "足立区 (Adachi-ku)", "葛飾区 (Katsushika-ku)", "江戸川区 (Edogawa-ku)"
]

JAPAN_REGIONS_DATA = [
    {"name": "北海道 (Hokkaido)", "cities": ["札幌市 (Sapporo)"]},
    {"name": "石川県 (Ishikawa)", "cities": ["金沢市 (Kanazawa)"]},
    {"name": "富山県 (Toyama)", "cities": ["富山市 (Toyama)", "高岡市 (Takaoka)"]},
    {"name": "東京都 (Tokyo)", "cities": TOKYO_23_WARDS},
    {"name": "沖縄県 (Okinawa)", "cities": ["那覇市 (Naha)", "石垣島 (Ishigaki)"]}
]

# --- [3. 階層データの構築ロジック] ---
def build_hierarchy():
    japan_children = []
    for pref in JAPAN_REGIONS_DATA:
        cities = []
        for city in pref["cities"]:
            city_item = {"name": city, "prefix": "R", "children": []}
            # 千川エリア（豊島区）の個別ロジックを維持
            if "豊島区" in city:
                city_item["children"].append({
                    "name": "千川エリア (Senkawa Area)", 
                    "prefix": "R", 
                    "alias": "千川"
                })
            cities.append(city_item)
        japan_children.append({"name": pref["name"], "prefix": "R", "children": cities})

    # リストの先頭に GUIDE を配置
    return [

        # 0. GUIDE (一番上に表示)
# 0. GUIDE (一番上に表示)
        {
            "name": "GUIDE （推し道の歩き方）", 
            "prefix": "G",
            "is_public": True,
            "children": [
                {"name": "🏠 HOME", "is_public": True},
                {"name": "💬 コミュニティ COMMUNITY", "is_public": True},
                {"name": "👥 ともだち FRIENDS", "is_public": True},
                {"name": "👤 MY PAGE", "is_public": True},
                {"name": "📧 Contact (お問い合わせ)", "is_public": True}
            ]
        },

        # 0. REGION
        {
            "name": "REGION （地域）", "prefix": "R",
            "children": [
                {"name": "APAC", "children": [
                    {"name": "Japan (日本)", "children": japan_children},
                    {"name": "Korea (韓国)"},
                    {"name": "China (中国)"},
                    {"name": "Taiwan (台湾)"},
                    {"name": "Australia (オーストラリア)"}
                ]},
                {"name": "EMEA", "children": [
                    {"name": "UK (イギリス)"},
                    {"name": "France (フランス)"},
                    {"name": "Germany (ドイツ)"},
                    {"name": "Spain (スペイン)"}
                ]},
                {"name": "North America", "children": [
                    {"name": "USA (アメリカ)"},
                    {"name": "Canada (カナダ)"}
                ]},
                {"name": "LATAM", "children": [
                    {"name": "Brazil (ブラジル)"},
                    {"name": "Mexico (メキシコ)"}
                ]}
            ]
        },

        # 1. MUSIC
        {
            "name": "MUSIC （音楽）", "prefix": "M",
            "children": [
                {"name": "POP", "children": [
                    {"name": "Doers (演奏・歌唱)", "children": [
                        {"name": "Karaoke (カラオケ)"},
                        {"name": "Band (バンド演奏)", "children": [
                            {"name": "Acoustic guitar"}, {"name": "Electric guitar"},
                            {"name": "Drums"}, {"name": "Bass"}, {"name": "Vocal"}, {"name": "Keyboard"}
                        ]}
                    ]},
                    {"name": "FANs (推し・リスナー)", "children": [
                        {"name": "Bruno Mars", "is_master": True},
                        {"name": "Maroon 5", "is_master": True},
                        {"name": "Taylor Swift", "is_master": True},
                        {"name": "Lady Gaga", "is_master": True},
                        {"name": "J-POP", "children": [
                            {"name": "サザンオールスターズ", "alias": "Southern All Stars, サザン", "is_master": True, "children": [
                                {"name": "桑田佳祐", "is_master": True}
                            ]},
                            {"name": "藤井風", "is_master": True},
                            {"name": "Official髭男dism", "alias": "ヒゲダン", "is_master": True},
                            {"name": "福山雅治", "is_master": True},
                            {"name": "KinKi Kids", "alias": "キンキ", "is_master": True, "children": [
                                {"name": "堂本光一", "is_master": True},
                                {"name": "堂本剛", "is_master": True}
                            ]},
                            {"name": "中森明菜", "is_master": True},
                            {"name": "Mr. Children", "alias": "ミスチル", "is_master": True},
                            {"name": "Mrs. GREEN APPLE", "alias": "ミセス", "is_master": True},
                            {"name": "斉藤和義", "is_master": True, "children": [
                                {"name": "岡村和義", "is_master": True}
                            ]},
                            {"name": "岡村靖幸", "is_master": True, "children": [
                                {"name": "岡村和義", "is_master": True}
                            ]},
                            {"name": "IDOL", "is_master": False}
                        ]},
                        {"name": "K-POP", "children": [{"name": "BTS", "is_master": True}]},
                        {"name": "Funk", "children": [{"name": "Bruno Mars", "is_master": True}]}
                    ]}
                ]},
                {"name": "ROCK", "children": [
                    {"name": "Doers", "children": [
                        {"name": "Band", "children": [
                            {"name": "Guitar"}, {"name": "Drums"}, {"name": "Bass"}, {"name": "Vocal"}, {"name": "Keyboard"}
                        ]}
                    ]},
                    {"name": "FANs", "children": [
                        {"name": "U2", "is_master": True},
                        {"name": "Aerosmith", "is_master": True},
                        {"name": "The Beatles", "is_master": True},
                        {"name": "Maroon 5", "is_master": True},
                        {"name": "ONE OK ROCK", "alias": "ワンオク", "is_master": True},
                        {"name": "J-ROCK", "children": [
                            {"name": "UNICORN", "is_master": True, "children": [{"name": "奥田民生", "is_master": True}]},
                            {"name": "B'z", "is_master": True},
                            {"name": "King Gnu", "is_master": True}
                        ]},
                        {"name": "METAL"},
                        {"name": "Grunge", "children": [{"name": "Nirvana", "is_master": True}]}
                    ]}
                ]},
                {"name": "CLASSIC", "children": [
                    {"name": "Doers", "children": [
                        {"name": "Orchestra", "children": [
                            {"name": "Strings", "children": [{"name": "Violin"}, {"name": "Viola"}, {"name": "Cello"}, {"name": "Double Bass"}]},
                            {"name": "Brass", "children": [{"name": "Trumpet"}, {"name": "French Horn"}, {"name": "Trombone"}, {"name": "Tuba"}]},
                            {"name": "Woodwinds", "children": [{"name": "Flute"}, {"name": "Oboe"}, {"name": "Clarinet"}, {"name": "Bassoon"}]},
                            {"name": "Percussion", "children": [{"name": "Timpani"}, {"name": "Snare Drum"}, {"name": "Cymbals"}, {"name": "Xylophone"}]}
                        ]}
                    ]},
                    {"name": "FANs", "children": [
                        {"name": "Bach", "is_master": True},
                        {"name": "Tchaikovsky", "is_master": True},
                        {"name": "Stravinsky", "is_master": True},
                        {"name": "Brahms", "is_master": True},
                        {"name": "Beethoven", "is_master": True},
                        {"name": "Vivaldi", "is_master": True}
                    ]}
                ]},
                {"name": "JAZZ", "children": [
                    {"name": "Doers", "children": [
                        {"name": "Band", "children": [
                            {"name": "Sax"}, {"name": "Trumpet"}, {"name": "Piano"},
                            {"name": "Bass"}, {"name": "Drums"}, {"name": "Guitar"}
                        ]}
                    ]},
                    {"name": "FANs", "children": [
                        {"name": "Gershwin", "is_master": True}
                    ]}
                ]}
            ]
        },

        # 2. VIDEO & STREAMING
        {
            "name": "VIDEO & STREAMING （映像・配信）", "prefix": "V",
            "children": [
                {"name": "Doers", "children": [
                    {"name": "Short Video Platform", "children": [{"name": "YouTube"}, {"name": "TikTok"}]}
                ]},
                {"name": "Fans", "children": [
                    {"name": "MOVIE", "children": [
                        {"name": "Star Wars", "is_master": True},
                        {"name": "The Lord of the Rings", "is_master": True},
                        {"name": "Harry Potter", "is_master": True},
                        {"name": "MCU", "children": [
                            {"name": "Iron Man"}, {"name": "Captain America"}, {"name": "Thor"},
                            {"name": "Spider-Man", "children": [{"name": "Spider-Man: No Way Home"}]},
                            {"name": "Avengers", "children": [
                                {"name": "Avengers: Endgame"}, {"name": "Avengers: Infinity War"},
                                {"name": "The Avengers"}, {"name": "Avengers: Age of Ultron"}
                            ]}
                        ]},
                        {"name": "るろうに剣心", "children": [
                            {"name": "るろうに剣心 (1作目)", "alias": "佐藤健"},
                            {"name": "るろうに剣心 京都大火編", "alias": "佐藤健"},
                            {"name": "るろうに剣心 伝説の最期編", "alias": "佐藤健"},
                            {"name": "るろうに剣心 最終章 The Final", "alias": "佐藤健"},
                            {"name": "るろうに剣心 The Beginning", "alias": "佐藤健"}
                        ]},
                        {"name": "映画版『ガリレオ』", "children": [
                            {"name": "容疑者Xの献身", "alias": "福山雅治"},
                            {"name": "真夏の方程式", "alias": "福山雅治"},
                            {"name": "沈黙のパレード", "alias": "福山雅治"}
                        ]},
                        {"name": "『トリック』劇場版", "children": [
                            {"name": "トリック劇場版"}, {"name": "トリック劇場版2"},
                            {"name": "劇場版TRICK 霊能力者バトルロイヤル"}, {"name": "トリック劇場版 ラストステージ"}
                        ]}
                    ]},
                    {"name": "TV", "children": [
                        {"name": "Star Trek"}, {"name": "Game of Thrones"}, {"name": "Friends"},
                        {"name": "The X-Files"}, {"name": "Breaking Bad"}
                    ]},
                    {"name": "Streaming Service", "children": [
                        {"name": "Netflix", "children": [
                            {"name": "Stranger Things"}, {"name": "The Crown"}, {"name": "Money Heist"},
                            {"name": "Squid Game"}, {"name": "Wednesday"}
                        ]},
                        {"name": "YouTube", "children": [
                            {"name": "OTAKING (岡田斗司夫ゼミ)", "alias": "オタキング", "is_master": True, "children": [
                                {"name": "岡田斗司夫"}
                            ]},
                            {"name": "ひろゆき / hiroyuki", "alias": "ひろゆき", "is_master": True},
                            {"name": "メンタリスト Daigo", "alias": "Daigo", "is_master": True},
                            {"name": "HIKAKIN"}, {"name": "Fischer's"}, {"name": "Comdot"}, {"name": "Hajime Shacho"}
                        ]},
                        {"name": "Amazon Prime Video", "children": [{"name": "The Boys"}]},
                        {"name": "Disney+", "children": [{"name": "The Mandalorian"}, {"name": "Loki"}]}
                    ]}
                ]}
            ]
        },

        # 3. TRADITION
        {
            "name": "TRADITION （伝統）", "prefix": "T",
            "children": [
                {"name": "Festival (祭り)", "children": [
                    {"name": "Religious Festivals (宗教的祭礼)", "children": [
                        {"name": "Japan", "children": [
                            {"name": "祇園祭", "children": [{"name": "Doers"}]},
                            {"name": "神田祭", "children": [{"name": "Doers"}]},
                            {"name": "葵祭", "children": [{"name": "Doers"}]}
                        ]}
                    ]},
                    {"name": "Fire Festivals (火祭り)", "children": [
                        {"name": "Japan", "children": [
                            {"name": "那智の火祭り", "children": [{"name": "Doers"}]},
                            {"name": "鬼夜", "children": [{"name": "Doers"}]},
                            {"name": "左義長まつり", "children": [{"name": "Doers"}]}
                        ]},
                        {"name": "Spain", "children": [{"name": "Las Fallas (バレンシアの火祭り)", "children": [{"name": "Doers"}]}]}
                    ]},
                    {"name": "Procession & Carnival (行列・カーニバル)", "children": [
                        {"name": "Japan", "children": [
                            {"name": "盛岡さんさ踊り", "children": [{"name": "盛岡さんさ踊り（踊り）"}, {"name": "Doers"}]},
                            {"name": "阿波踊り", "children": [{"name": "阿波踊り（踊り）"}, {"name": "Doers"}]},
                            {"name": "青森ねぶた祭", "children": [{"name": "Doers"}]},
                            {"name": "高山祭", "children": [{"name": "Doers"}]},
                            {"name": "岸和田だんじり祭", "children": [{"name": "Doers"}]},
                            {"name": "仙台七夕", "children": [{"name": "Doers"}]}
                        ]},
                        {"name": "Brazil", "children": [{"name": "Rio Carnival", "children": [{"name": "Doers"}]}]},
                        {"name": "UK", "children": [{"name": "Notting Hill Carnival", "children": [{"name": "Doers"}]}]}
                    ]},
                    {"name": "Harvest & Season (収穫・季節)", "children": [
                        {"name": "Japan", "children": [
                            {"name": "よさこい", "children": [{"name": "よさこい（踊り）"}, {"name": "Doers"}]},
                            {"name": "盆踊り", "children": [{"name": "盆踊り（踊り）"}, {"name": "Doers"}]},
                            {"name": "新嘗祭", "children": [{"name": "Doers"}]},
                            {"name": "大原はだか祭り", "children": [{"name": "Doers"}]},
                            {"name": "おわら風の盆", "children": [{"name": "おわら風の盆（踊り）"}, {"name": "Doers"}]},
                            {"name": "西馬音内盆踊り", "children": [{"name": "西馬音内盆踊り（踊り）"}, {"name": "Doers"}]},
                            {"name": "YOSAKOIソーラン祭り", "children": [{"name": "YOSAKOI（踊り）"}, {"name": "Doers"}]}
                        ]},
                        {"name": "Mexico", "children": [{"name": "Dia de los Muertos (死者の日)", "children": [{"name": "Doers"}]}]},
                        {"name": "USA / Canada", "children": [{"name": "Thanksgiving (感謝祭)"}]},
                        {"name": "Germany", "children": [{"name": "Oktoberfest (オクトーバーフェスト)"}]}
                    ]},
                    {"name": "Fireworks & Light (花火・光)", "children": [
                        {"name": "Japan", "children": [
                            {"name": "隅田川花火大会"}, {"name": "長岡まつり"}, {"name": "なにわ淀川花火大会"}
                        ]},
                        {"name": "France", "children": [{"name": "Bastille Day Fireworks (パリ祭)"}]},
                        {"name": "India", "children": [{"name": "Diwali (光の祭)"}]},
                        {"name": "Global / Islam", "children": [{"name": "Eid al-Fitr (断食明けの祭)"}]},
                        {"name": "USA", "children": [{"name": "Burning Man"}]}
                    ]}
                ]},
                {"name": "Folk Music & Dance (民族音楽・舞踊)", "children": [
                    {"name": "East Asia", "children": [
                        {"name": "Japan", "children": [
                            {"name": "和太鼓 (Wadaiko)", "children": [{"name": "Doers"}]},
                            {"name": "雅楽 (Gagaku)", "children": [{"name": "Doers"}]},
                            {"name": "三味線 (Shamisen)", "children": [{"name": "Doers"}]},
                            {"name": "エイサー (Eisa)", "children": [{"name": "Doers"}]},
                            {"name": "おわら風の盆（踊り）", "children": [{"name": "Doers"}]},
                            {"name": "西馬音内盆踊り（踊り）", "children": [{"name": "Doers"}]},
                            {"name": "阿波踊り（踊り）", "children": [{"name": "Doers"}]},
                            {"name": "盛岡さんさ踊り（踊り）", "children": [{"name": "Doers"}]},
                            {"name": "よさこい（踊り）", "children": [{"name": "Doers"}]},
                            {"name": "盆踊り（踊り）", "children": [{"name": "Doers"}]},
                            {"name": "YOSAKOI（踊り）", "children": [{"name": "Doers"}]}
                        ]},
                        {"name": "China", "children": [
                            {"name": "古筝 (Guzheng)", "children": [{"name": "Doers"}]},
                            {"name": "京劇音楽 (Peking Opera Music)", "children": [{"name": "Doers"}]}
                        ]},
                        {"name": "Korea", "children": [
                            {"name": "국악 / Gugak", "children": [{"name": "Doers"}]},
                            {"name": "한국무용 / Hanguk Muyong", "children": [{"name": "Doers"}]}
                        ]}
                    ]},
                    {"name": "Southeast Asia", "children": [
                        {"name": "Indonesia", "children": [
                            {"name": "Gamelan", "children": [{"name": "Doers"}]},
                            {"name": "Tari Bali", "children": [{"name": "Doers"}]}
                        ]},
                        {"name": "Thailand", "children": [
                            {"name": "ดนตรีไทย / Dontri Thai", "children": [{"name": "Doers"}]},
                            {"name": "รำไทย / Ram Thai", "children": [{"name": "Doers"}]}
                        ]}
                    ]},
                    {"name": "South Asia", "children": [
                        {"name": "India", "children": [
                            {"name": "हिन्दुस्तानी शास्त्रीय संगीत / Hindustani Sangeet", "children": [{"name": "Doers"}]},
                            {"name": "कर्नाटक संगीत / Carnatic Sangeet", "children": [{"name": "Doers"}]}
                        ]}
                    ]},
                    {"name": "Europe", "children": [
                        {"name": "Spain", "children": [{"name": "Flamenco", "is_master": True, "children": [{"name": "Doers"}]}]},
                        {"name": "Ireland", "children": [{"name": "Irish Dance and Music", "is_master": True, "children": [{"name": "Doers"}]}]}
                    ]},
                    {"name": "Polynesia", "children": [
                        {"name": "Hawaii", "children": [
                            {"name": "Hula", "children": [
                                {"name": "Chant", "children": [{"name": "Doers"}]},
                                {"name": "Hula Dance", "is_master": True, "children": [{"name": "Doers"}]}
                            ]}
                        ]}
                    ]}
                ]},
                {"name": "Craft (工芸)", "children": [
                    {"name": "Ceramics (陶磁器)", "children": [
                        {"name": "Porcelain (磁器)", "children": [
                            {"name": "有田焼", "children": [{"name": "Doers"}, {"name": "Repair"}]},
                            {"name": "備前焼", "children": [{"name": "Doers"}, {"name": "Repair"}]},
                            {"name": "九谷焼", "children": [{"name": "Doers"}, {"name": "Repair"}]}
                        ]},
                        {"name": "Pottery (陶器)", "children": [{"name": "Doers"}]}
                    ]},
                    {"name": "Glass", "children": [
                        {"name": "Cut Glass", "children": [{"name": "江戸切子", "children": [{"name": "Doers"}]}]},
                        {"name": "Blown Glass", "children": [{"name": "ムラーノガラス / Murano Glass", "children": [{"name": "Doers"}]}]}
                    ]},
                    {"name": "Textile", "children": [
                        {"name": "西陣織", "children": [{"name": "Doers"}]},
                        {"name": "ペルシャ絨毯", "children": [{"name": "Doers"}]},
                        {"name": "加賀友禅", "children": [{"name": "Doers"}]},
                        {"name": "小千谷縮", "children": [{"name": "Doers"}]},
                        {"name": "京友禅", "children": [{"name": "Doers"}]},
                        {"name": "久留米絣", "children": [{"name": "Doers"}]},
                        {"name": "博多織", "children": [{"name": "Doers"}]}
                    ]},
                    {"name": "Wood & Bamboo craft", "children": [
                        {"name": "Wooden craft", "children": [
                            {"name": "箱根寄木細工", "children": [{"name": "Doers"}, {"name": "Repair"}]}
                        ]},
                        {"name": "Carving", "children": [
                            {"name": "井波彫刻", "children": [{"name": "Doers"}, {"name": "Repair"}]}
                        ]}
                    ]},
                    {"name": "Lacquerware (漆工)", "children": [
                        {"name": "輪島塗", "children": [{"name": "Doers"}, {"name": "Repair"}]},
                        {"name": "鎌倉彫", "children": [{"name": "Doers"}, {"name": "Repair"}]},
                        {"name": "津軽塗", "children": [{"name": "Doers"}, {"name": "Repair"}]}
                    ]},
                    {"name": "Stationery and Paper", "children": [
                        {"name": "和紙 (Washi)", "children": [{"name": "Doers"}]},
                        {"name": "筆 (Fude Brush)", "children": [
                            {"name": "熊野筆", "children": [{"name": "Doers"}]},
                            {"name": "川尻筆", "children": [{"name": "Doers"}]},
                            {"name": "奈良筆", "children": [{"name": "Doers"}]}
                        ]},
                        {"name": "Fountain Pen (万年筆)", "children": [
                            {"name": "Pilot", "children": [{"name": "Custom 823"}, {"name": "Custom 74"}, {"name": "キャップレス"}]},
                            {"name": "Sailor", "children": [{"name": "プロフェッショナルギア"}, {"name": "21Kニブモデル"}]},
                            {"name": "Platinum", "children": [{"name": "#3776 Century"}]},
                            {"name": "Nakaya"},
                            {"name": "Montblanc", "children": [{"name": "Meisterstück 149"}]},
                            {"name": "Pelikan", "children": [{"name": "Souverän M800 / M1000"}]},
                            {"name": "Lamy", "children": [{"name": "Lamy 2000"}, {"name": "Safari"}]},
                            {"name": "Kaweco", "children": [{"name": "Sport"}]}
                        ]},
                        {"name": "Ballpoint/Other Pen", "children": [
                            {"name": "Uni Jetstream"}, {"name": "Pilot Dr. Grip"}, {"name": "Zebra Sarasa"},
                            {"name": "Pentel EnerGel"}, {"name": "Rotring 600"}, {"name": "Parker Jotter"},
                            {"name": "Caran d'Ache 849"}
                        ]}
                    ]},
                    {"name": "Metal & Precision Craft", "children": [
                        {"name": "Swords (刀剣)", "children": [{"name": "Doers"}]},
                        {"name": "南部鉄器", "children": [{"name": "Doers"}]},
                        {"name": "鎚起銅器", "children": [{"name": "Doers"}]},
                        {"name": "Swiss watches (精密時計)"}
                    ]},
                    {"name": "Altars & Dolls", "children": [
                        {"name": "博多人形", "children": [{"name": "Doers"}, {"name": "Repair"}]}
                    ]}
                ]},
                {"name": "Accomplishments (たしなみ)", "children": [
                    {"name": "Tea Ceremony (茶道)", "children": [{"name": "Doers"}]},
                    {"name": "Flower Arrangement (華道)", "children": [{"name": "Doers"}]},
                    {"name": "Calligraphy (書道)", "children": [{"name": "Doers"}]},
                    {"name": "Traditional Dance (日本舞踊)", "children": [{"name": "Doers"}]}
                ]}
            ]
        },

        # 4. SPORTS
        {
            "name": "SPORTS （スポーツ）", "prefix": "S",
            "children": [
                {"name": "Match & Court", "children": [
                    {"name": "Tennis", "children": [{"name": "Doers"}, {"name": "Fans"}]},
                    {"name": "Table tennis", "children": [{"name": "Doers"}, {"name": "Fans"}]},
                    {"name": "Soccer", "alias": "Football", "children": [
                        {"name": "Doers"},
                        {"name": "Fans", "children": [
                            {"name": "La Liga", "children": [{"name": "Real Madrid CF"}, {"name": "FC Barcelona"}]},
                            {"name": "Premier League", "children": [{"name": "Manchester United F.C."}]},
                            {"name": "J1", "children": [{"name": "浦和レッズ"}]}
                        ]}
                    ]},
                    {"name": "Baseball", "children": [
                        {"name": "Doers", "children": [
                            {"name": "Youth Baseball", "alias": "少年野球"},
                            {"name": "High School Baseball", "alias": "高校野球"},
                            {"name": "University Baseball", "alias": "大学野球"},
                            {"name": "Womens Baseball", "alias": "女子野球"},
                            {"name": "Softball", "alias": "ソフトボール"},
                            {"name": "Independent League", "alias": "独立リーグ"},
                            {"name": "Amateur Baseball", "children": [
                                {"name": "草野球 (Kusa-Yakyu)", "children": [
                                    {"name": "一般・私設チーム"},
                                    {"name": "連盟・大会参加チーム"},
                                    {"name": "個人参加・1day"},
                                    {"name": "朝野球", "alias": "Morning baseball"}
                                ]}
                            ]},
                            {"name": "Senior Baseball", "alias": "シニア, 還暦野球"}
                        ]},
                        {"name": "Fans", "children": [
                            {"name": "MLB", "children": [{"name": "New York Yankees"}, {"name": "Los Angeles Dodgers"}]},
                            {"name": "NPB (日本プロ野球)", "children": [
                                {"name": "読売ジャイアンツ"}, {"name": "阪神タイガース"}, {"name": "中日ドラゴンズ"},
                                {"name": "福岡ソフトバンクホークス"}, {"name": "広島東洋カープ"}, {"name": "ヤクルトスワローズ"}
                            ]},
                            {"name": "大谷翔平 (Shohei Ohtani)", "is_master": True}
                        ]}
                    ]},
                    {"name": "Basketball", "children": [
                        {"name": "Doers"},
                        {"name": "Fans", "children": [
                            {"name": "NBA", "children": [
                                {"name": "Los Angeles Lakers"}, {"name": "Golden State Warriors"}, {"name": "Chicago Bulls"}
                            ]},
                            {"name": "河村優輝", "is_master": True}
                        ]}
                    ]}
                ]},
                {"name": "Solo & Nature", "children": [
                    {"name": "Golf", "children": [{"name": "Doers"}, {"name": "Fans"}]},
                    {"name": "Swimming", "children": [{"name": "Doers"}, {"name": "Fans"}]},
                    {"name": "Track & Field", "children": [
                        {"name": "Doers", "children": [{"name": "Running", "children": [{"name": "Marathon"}]}]},
                        {"name": "Fans"}
                    ]},
                    {"name": "Gym & Fitness", "children": [
                        {"name": "Doers", "children": [{"name": "Yoga"}, {"name": "Pilates"}]}
                    ]},
                    {"name": "Climbing", "children": [
                        {"name": "Doers", "children": [
                            {"name": "Wall Climbing"},
                            {"name": "Mountain Climbing", "children": [{"name": "Winter Climbing"}]}
                        ]}
                    ]},
                    {"name": "Ski & Snow boarding", "children": [
                        {"name": "Doers", "children": [{"name": "Ski"}, {"name": "Snow boarding"}]}
                    ]}
                ]},
                {"name": "Dance", "children": [
                    {"name": "Doers", "children": [
                        {"name": "Ballet", "children": [
                            {"name": "Classical Ballet"}, {"name": "Modern Ballet"}, {"name": "Contemporary Ballet"}
                        ]},
                        {"name": "Ballroom Dance", "children": [
                            {"name": "Waltz"}, {"name": "Tango"}, {"name": "Rumba"}, {"name": "Cha-Cha"}, {"name": "Salsa"}
                        ]},
                        {"name": "Street Dance", "children": [
                            {"name": "Hip Hop"}, {"name": "Breaking"}, {"name": "Locking"},
                            {"name": "Popping"}, {"name": "House Dance"}, {"name": "Crump"}
                        ]},
                        {"name": "Team Performance", "children": [
                            {"name": "Cheerleading"}, {"name": "Pom Dance"}, {"name": "Drill Dance"}, {"name": "K-Pop Cover Dance"}
                        ]},
                        {"name": "Folk Dance (Traditional)", "children": [
                            {"name": "Flamenco"},
                            {"name": "Irish Dance"},
                            {"name": "Hula Dance"},
                            {"name": "Indian Classical Dance"}
                        ]}
                    ]}
                ]},
                {"name": "Combat & Martial Arts", "children": [
                    {"name": "Boxing", "children": [{"name": "Doers"}, {"name": "Fans"}]},
                    {"name": "Kick Boxing", "children": [{"name": "Doers"}, {"name": "Fans"}]}
                ]},
                {"name": "Motor Sports", "children": [
                    {"name": "Doers", "children": [
                        {"name": "Karting", "alias": "カート"}
                    ]},
                    {"name": "Fans", "children": [
                        {"name": "F1 (Formula 1)", "is_master": True, "children": [
                            {"name": "角田裕毅", "alias": "Yuki Tsunoda", "is_master": True},
                            {"name": "Max Verstappen", "is_master": True},
                            {"name": "Lewis Hamilton", "is_master": True}
                        ]},
                        {"name": "MotoGP", "is_master": True},
                        {"name": "WRC", "alias": "ラリー", "is_master": True},
                        {"name": "Super GT", "is_master": True}
                    ]}
                ]}
            ]
        },

        # 5. THEATER
        {
            "name": "THEATER （演劇・舞台）", "prefix": "TH",
            "children": [
                {"name": "Fans", "children": [
                    {"name": "Traditional Drama", "children": [
                        {"name": "歌舞伎 (Kabuki)"},
                        {"name": "能 (Noh)"},
                        {"name": "文楽 (Bunraku)"}
                    ]},
                    {"name": "Musical / Revue", "children": [
                        {"name": "宝塚歌劇団", "alias": "Takarazuka,ヅカ"},
                        {"name": "劇団四季", "alias": "Shiki Theatre Company"},
                        {"name": "Paris Opéra", "is_master": True},
                        {"name": "The Metropolitan Opera", "alias": "The Met", "is_master": True}
                    ]},
                    {"name": "Ballet / Dance", "children": [
                        {"name": "Paris Opéra Ballet", "is_master": True},
                        {"name": "The Royal Ballet", "is_master": True},
                        {"name": "New York City Ballet", "alias": "NYCB", "is_master": True},
                        {"name": "American Ballet Theatre", "alias": "ABT", "is_master": True},
                        {"name": "K-BALLET TOKYO", "is_master": True}
                    ]},
                    {"name": "Play / Contemporary Theater", "children": [
                        {"name": "野田地図", "alias": "NODA・MAP"},
                        {"name": "大人計画"},
                        {"name": "劇団☆新感線"},
                        {"name": "The National Theatre (UK)"},
                        {"name": "Royal Court Theatre"},
                        {"name": "The Public Theater (NY)"},
                        {"name": "Royal Shakespeare Company", "alias": "RSC"},
                        {"name": "Comédie-Française"}
                    ]}
                ]}
            ]
        },

        # 6. POP CULTURE
        {
            "name": "POP CULTURE（ポップカルチャー）", "prefix": "P",
            "children": [
                {"name": "⚠️ COMMUNITY RULES; Anime Focus: After Animated, only ANIME base talk available"},
                {"name": "MANGA・ANIME", "children": [
                    {"name": "Doers (クリエイター・コスプレイヤー)", "role_type": "DOERS"},
                    {"name": "Fans (推し・読者)", "role_type": "FANS", "children": [
                        {"name": "葬送のフリーレン", "is_master": True},
                        {"name": "呪術廻戦", "is_master": True},
                        {"name": "鬼滅の刃", "is_master": True},
                        {"name": "鋼の錬金術師", "is_master": True}
                    ]}
                ]},
                {"name": "GAMES", "children": [
                    {"name": "Doers (制作・配信)", "role_type": "DOERS"},
                    {"name": "Fans (プレイヤー)", "role_type": "FANS", "children": [
                        {"name": "ポケットモンスター", "is_master": True, "alias": "ポケモン, Pokemon"}
                    ]}
                ]},
                {"name": "COSPLAY", "children": [
                    {"name": "Doers (コスプレイヤー)", "role_type": "DOERS"},
                    {"name": "Fans (カメラマン・ファン)", "role_type": "FANS"}
                ]},
                {"name": "VTUBER", "children": [
                    {"name": "Doers (配信者)", "role_type": "DOERS"},
                    {"name": "Fans (リスナー)", "role_type": "FANS"}
                ]},
                {"name": "CHARACTERS", "children": [
                    {"name": "Fans", "role_type": "FANS"}
                ]},
                {"name": "IDOL", "is_master": True, "prefix": "P", "children": [
                    {"name": "Doers", "is_master": True, "alias": "アイドル"},
                    {"name": "Fans", "children": [
                        {"name": "乃木坂46", "is_master": True, "alias": "坂道"},
                        {"name": "BABYMETAL", "is_master": True, "alias": "メタル"},
                        {"name": "地下アイドル総合", "is_master": True}
                    ]}
                ]}
            ]
        },

        # ANIMALS
        {
            "name": "ANIMALS（動物）", "prefix": "A", "alias": "ペット, 生き物",
            "children": [
                {"name": "Pets（愛玩動物）", "children": [
                    {"name": "Dogs（犬）", "children": [
                        {"name": "Chihuahua（チワワ）"},
                        {"name": "Toy Poodle（トイプードル）"},
                        {"name": "Shiba Inu（柴犬）", "alias": "しば, しばいぬ"},
                        {"name": "French Bulldog（フレンチブルドッグ）", "alias": "フレブル"},
                        {"name": "Dachshund（ダックスフンド）"},
                        {"name": "Golden Retriever（ゴールデンレトリバー）", "alias": "ゴールデン"},
                        {"name": "Mixed（ミックス犬）", "alias": "ミックス, 雑種"},
                    ]},
                    {"name": "Cats（猫）", "alias": "ねこ", "children": [
                        {"name": "Scottish Fold（スコティッシュフォールド）"},
                        {"name": "American Shorthair（アメリカンショートヘア）"},
                        {"name": "Munchkin（マンチカン）"},
                        {"name": "Persian（ペルシャ）"},
                        {"name": "Ragdoll（ラグドール）"},
                        {"name": "Mixed（雑種）", "alias": "ミックス"},
                                        ]},
                    {"name": "Birds（鳥）", "children": [
                        {"name": "Parakeet（インコ）"},
                        {"name": "Parrot（オウム）"},
                        {"name": "Canary（カナリア）"},
                    ]},
                    {"name": "Fish（魚）", "children": [
                        {"name": "Tropical Fish（熱帯魚）"},
                        {"name": "Goldfish（金魚）"},
                        {"name": "Koi（錦鯉）"},
                    ]},
                    {"name": "Small Animals（小動物）", "children": [
                        {"name": "Hamster（ハムスター）"},
                        {"name": "Rabbit（うさぎ）"},
                        {"name": "Guinea Pig（モルモット）"},
                        {"name": "Ferret（フェレット）"},
                    ]},
                ]},
                {"name": "Wildlife（野生動物）", "children": [
                    {"name": "Mammals（哺乳類）"},
                    {"name": "Reptiles（爬虫類）"},
                    {"name": "Insects（昆虫）"},
                ]},
                {"name": "Zoo & Safari（動物園・サファリパーク）", "children": [
                    {"name": "Zoo（動物園）"},
                    {"name": "Safari Park（サファリパーク）"},
                ]},
            ]
        },

        # 7. FOOD & DRINK
        {
            "name": "FOOD & DRINK（食・グルメ）", "prefix": "F", "alias": "食, グルメ, 料理",
            "children": [
                {"name": "Doers", "alias": "作る, 育てる", "children": [
                    {"name": "Chef / Cook", "alias": "料理人, シェフ"},
                    {"name": "Patissier / Baker", "alias": "菓子職人, パン職人"},
                    {"name": "Barista", "alias": "バリスタ"},
                    {"name": "Brewer / Sommelier", "alias": "醸造家, 蔵人, ソムリエ"},
                    {"name": "Agriculture (Farmer)", "alias": "農業, 農家", "children": [
                        {"name": "Crop Farming", "alias": "耕種農業", "children": [
                            {"name": "Rice Farming", "alias": "稲作"},
                            {"name": "Vegetable Farming", "alias": "野菜栽培"},
                            {"name": "Fruit Farming", "alias": "果樹栽培"}
                        ]},
                        {"name": "Livestock Farming", "alias": "畜産", "children": [
                            {"name": "Dairy Farming", "alias": "酪農"},
                            {"name": "Beef / Pork / Poultry", "alias": "肉牛, 養豚, 養鶏"}
                        ]}
                    ]}
                ]},
                {"name": "Fans", "alias": "食べる, 楽しむ", "children": [
                    {"name": "Japanese Cuisine", "alias": "和食, 日本料理", "children": [
                        {"name": "ラーメン", "alias": "Ramen", "is_master": True},
                        {"name": "寿司", "alias": "Sushi", "is_master": True},
                        {"name": "天ぷら", "alias": "Tempura"},
                        {"name": "粉もの", "alias": "Konamon", "children": [
                            {"name": "お好み焼き", "alias": "Okonomiyaki"},
                            {"name": "たこ焼き", "alias": "Takoyaki"},
                            {"name": "もんじゃ焼き", "alias": "Monjayaki"}
                        ]},
                        {"name": "懐石料理", "alias": "Kaiseki"},
                        {"name": "定食", "alias": "Teishoku"},
                        {"name": "Local Food", "children": [{"name": "郷土料理"}, {"name": "B級グルメ"}]}
                    ]},
                    {"name": "French", "alias": "フレンチ, フランス料理"},
                    {"name": "Italian", "alias": "イタリアン, イタリア料理"},
                    {"name": "Chinese", "alias": "中華料理"},
                    {"name": "Beverages", "alias": "飲み物", "children": [
                        {"name": "Sake", "alias": "日本酒", "is_master": True},
                        {"name": "Wine", "alias": "ワイン"},
                        {"name": "Coffee", "alias": "コーヒー, 珈琲"}
                    ]}
                ]}
            ]
        },

        # 8. LITERATURE
        {
            "name": "LITERATURE（文学）", "prefix": "LT", "alias": "文学, 本, 書籍",
            "children": [
                {"name": "Doers", "alias": "執筆, 創作", "children": [
                    {"name": "俳句", "alias": "Haiku"},
                    {"name": "短歌", "alias": "Tanka"},
                    {"name": "Poetry", "alias": "詩"},
                    {"name": "Fiction / Novel", "alias": "小説"},
                    {"name": "Essay", "alias": "エッセイ, 随筆"}
                ]},
                {"name": "Fans", "children": [
                    {"name": "Japanese Literature", "alias": "日本文学", "children": [
                        {"name": "芥川龍之介", "alias": "Ryunosuke Akutagawa", "is_master": True},
                        {"name": "太宰治", "alias": "Osamu Dazai", "is_master": True},
                        {"name": "村上春樹", "alias": "Haruki Murakami", "is_master": True},
                        {"name": "村上龍", "alias": "Ryu Murakami", "is_master": True},
                        {"name": "江國香織", "alias": "Kaori Ekuni", "is_master": True},
                        {"name": "紫式部", "alias": "Murasaki Shikibu, 源氏物語", "is_master": True},
                        {"name": "清少納言", "alias": "Sei Shonagon, 枕草子", "is_master": True},
                        {"name": "坂口安吾", "alias": "Ango Sakaguchi", "is_master": True},
                        {"name": "夏目漱石", "alias": "Natsume Soseki", "is_master": True},
                        {"name": "三島由紀夫", "alias": "Yukio Mishima", "is_master": True}
                    ]},
                    {"name": "World Literature", "alias": "海外文学", "children": [
                        {"name": "William Shakespeare", "alias": "シェイクスピア", "is_master": True},
                        {"name": "Fyodor Dostoevsky", "alias": "ドストエフスキー", "is_master": True},
                        {"name": "Franz Kafka", "alias": "カフカ", "is_master": True},
                        {"name": "Ernest Hemingway", "alias": "ヘミングウェイ", "is_master": True},
                        {"name": "Agatha Christie", "alias": "アガサ・クリスティ", "is_master": True},
                        # ★ 追加
                        {"name": "Jane Austen", "alias": "ジェイン・オースティン", "is_master": True},
                        {"name": "Brontë Sisters", "alias": "ブロンテ姉妹, Charlotte Brontë, Emily Brontë", "is_master": True}
                    ]},
                    {"name": "Genre-Specific", "alias": "ジャンル別", "children": [
                        {"name": "Mystery / Crime", "alias": "ミステリー, 推理小説"},
                        {"name": "Science Fiction", "alias": "SF"},
                        {"name": "Fantasy", "alias": "ファンタジー"}
                    ]}
                ]}
            ]
        },

        # 9. ART
        {
            "name": "ART（美術）", "prefix": "A", "alias": "芸術, 美術",
            "children": [
                {"name": "PAINTING", "alias": "絵画", "children": [
                    {"name": "Doers", "children": [
                        {"name": "Oil Painting", "alias": "油絵"},
                        {"name": "Illustration", "alias": "イラスト"},
                        {"name": "日本画", "alias": "Nihonga"}
                    ]},
                    {"name": "Fans", "children": [
                        {"name": "Nihonga", "alias": "日本画", "children": [
                            {"name": "伊藤若冲", "alias": "Jakuchu Ito", "is_master": True},
                            {"name": "歌川広重", "alias": "Hiroshige Utagawa", "is_master": True},
                            {"name": "葛飾北斎", "alias": "Hokusai Katsushika", "is_master": True}
                        ]},
                        {"name": "Western Art", "alias": "西洋画", "children": [
                            {"name": "Impressionism", "alias": "印象派", "children": [
                                {"name": "Claude Monet", "alias": "クロード・モネ"},
                                {"name": "Paul Cézanne", "alias": "ポール・セザンヌ"},
                                {"name": "Vincent van Gogh", "alias": "ゴッホ"}
                            ]},
                            {"name": "Surrealism", "alias": "シュルレアリスム", "children": [
                                {"name": "Pablo Picasso", "alias": "パブロ・ピカソ"}
                            ]},
                            {"name": "Contemporary Art", "alias": "現代美術", "children": [
                                {"name": "Gerhard Richter", "alias": "ゲルハルト・リヒター"},
                                {"name": "Banksy", "alias": "バンクシー"},
                                {"name": "草間彌生", "alias": "Yayoi Kusama", "is_master": True}
                            ]}
                        ]}
                    ]}
                ]},
                {"name": "Architecture（建築）", "alias": "建築", "children": [
                    {"name": "Doers"},
                    {"name": "Fans", "children": [
                        {"name": "Frank Lloyd Wright", "alias": "フランク・ロイド・ライト", "is_master": True},
                        {"name": "安藤忠雄", "alias": "Tadao Ando", "is_master": True},
                        {"name": "隈研吾", "alias": "Kengo Kuma", "is_master": True},
                        {"name": "Le Corbusier", "alias": "ル・コルビュジエ", "is_master": True},
                        {"name": "Antoni Gaudí", "alias": "アントニ・ガウディ", "is_master": True, "children": [
                            {"name": "La Sagrada Família", "alias": "サグラダ・ファミリア", "is_master": True}
                        ]},
                        {"name": "Zaha Hadid", "alias": "ザハ・ハディッド", "is_master": True}
                    ]}
                ]},
                {"name": "MUSEUM", "alias": "美術館", "children": [
                    {"name": "Fans", "children": [
                        {"name": "Solomon R. Guggenheim Museum", "alias": "グッゲンハイム美術館", "is_master": True},
                        {"name": "Chichu Art Museum", "alias": "地中美術館", "is_master": True},
                        {"name": "National Museum of Western Art", "alias": "国立西洋美術館", "is_master": True},
                        {"name": "Suntory Museum of Art", "alias": "サントリー美術館", "is_master": True},
                        {"name": "Musée du Louvre", "alias": "ルーヴル美術館", "is_master": True},
                        {"name": "The British Museum", "alias": "大英博物館", "is_master": True},
                        {"name": "国立競技場", "alias": "Japan National Stadium", "is_master": True}
                    ]}
                ]}
            ]
        },

        # STUDY
        {
            "name": "STUDY（学問）", "prefix": "S", "alias": "学問, 研究, 勉強",
            "children": [
                {"name": "Business（経営学）", "alias": "経営, ビジネス", "children": [
                    {"name": "Organization（組織論）"},
                    {"name": "Marketing（マーケティング）"},
                    {"name": "Entrepreneurship（起業）", "alias": "スタートアップ"},
                ]},
                {"name": "Economics（経済学）"},
                {"name": "Languages（語学）", "children": [
                    {"name": "English（英語）"},
                    {"name": "日本語（Japanese）"},
                    {"name": "中文（Chinese）"},
                    {"name": "한국어（Korean）"},
                    {"name": "Français（French）"},
                    {"name": "Español（Spanish）"},
                    {"name": "Deutsch（German）"}
                    ,
                ]},
                {"name": "Sociology（社会学）"},
                {"name": "Mathematics（数学）", "children": [
                    {"name": "Statistics（統計学）"},
                ]},
                {"name": "Physics（物理学）"},
                {"name": "Chemistry（化学）"},
                {"name": "Biology（生物学）"},
            ]
        },

        # 10. PEOPLE
        {
            "name": "PEOPLE（人物）", "prefix": "P",
            "children": [
                {"name": "Fans", "children": [
                    {"name": "Actors / Artists", "children": [
                        {"name": "佐藤健", "is_master": True},
                        {"name": "福山雅治", "is_master": True}
                    ]},
                    {"name": "Thinkers / Critics", "children": [
                        {"name": "岡田斗司夫", "is_master": True},
                        {"name": "ひろゆき (西村博之)", "is_master": True},
                        {"name": "Daigo", "is_master": True}
                    ]},
                    {"name": "Influencers / Creators"}
                ]}
            ]
        }

    ]  # end of return


# --- [4. 挿入ロジック (マスター連携)] ---
name_to_id_map = {}

def insert_category(db: Session, data: dict, parent_id: Optional[int] = None, depth: int = 0, default_prefix: str = ""):
    global name_to_id_map
    prefix = data.get("prefix", default_prefix)
    name = data["name"]
    alias = data.get("alias")
    is_master = data.get("is_master", False)

    existing_cat = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.name == name,
        models.HobbyCategory.parent_id == parent_id,
        models.HobbyCategory.depth == depth
    ).first()

    if existing_cat:
        current_cat_id = existing_cat.id
        if is_master and name not in name_to_id_map:
            name_to_id_map[name] = current_cat_id
    else:
        master_id = name_to_id_map.get(name) if not is_master else None
        new_cat = models.HobbyCategory(
            name=name,
            alias_name=alias,
            parent_id=parent_id,
            master_id=master_id,
            depth=depth,
            role_type=data.get("role_type"),
            is_public=data.get("is_public", False), 
            unique_code=generate_code(prefix=prefix)
        )
        db.add(new_cat)
        db.flush()
        current_cat_id = new_cat.id
        if is_master:
            name_to_id_map[name] = current_cat_id

    if "children" in data:
        for child in data["children"]:
            insert_category(db, child, current_cat_id, depth + 1, prefix)


def create_initial_data(db: Session):
    print("--- データベース更新開始 (安全モード) ---")
    Base.metadata.create_all(bind=engine)

    print("--- カテゴリ投入 (差分更新) ---")
    hierarchy = build_hierarchy()
    global name_to_id_map
    name_to_id_map = {}
    for item in hierarchy:
        insert_category(db, item)

    print("--- ユーザー登録チェック ---")
    common_password = get_password_hash("password123")
    test_users = [
        {
            "email": "system@osidou.com",
            "username": "osidou_system",
            "nickname": "推集炉",
            "bio": "おしどう公式アカウントです。"
        },
        {
            "email": "miho@example.com",
            "username": "miho_senkawa",
            "nickname": "みほ(千川)",
            "bio": "千川エリアを盛り上げたいです。日本酒、サザン、岡田斗司夫ゼミが好き。"
        },
        {
            "email": "kinki_fan@example.com",
            "username": "tsuyoshi_love",
            "nickname": "図書委員",
            "bio": "KinKi Kids一筋。福山雅治さんのドラマもよく見ます。"
        },
        {
            "email": "marine@example.com",
            "username": "ocean_diver",
            "nickname": "うみんちゅ",
            "bio": "沖縄の海でダイビングするのが生きがいです。石垣島によくいます。"
        }
    ]

    for u_data in test_users:
        exists = db.query(models.User).filter(
            or_(
                models.User.email == u_data["email"],
                models.User.username == u_data["username"],
                models.User.nickname == u_data["nickname"]
            )
        ).first()
        if not exists:
            db.add(models.User(
                email=u_data["email"],
                username=u_data["username"],
                nickname=u_data["nickname"],
                bio=u_data["bio"],
                public_code=generate_code(),
                hashed_password=common_password,
                is_active=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ))
            print(f" ✅ 作成完了: {u_data['nickname']}")
        else:
            print(f" ⏩ スキップ (登録済): {u_data['nickname']}")

# --- GUIDE 初期投稿 ---
        print("--- GUIDE 初期投稿チェック ---")

        admin_user = db.query(models.User).filter(
            models.User.email == "system@osidou.com"
        ).first()

        guide_cat = db.query(models.HobbyCategory).filter(
            models.HobbyCategory.name == "GUIDE （推し道の歩き方）"
        ).first()

    # --- GUIDE 親カテゴリへの投稿 ---
    if admin_user and guide_cat:
        existing_guide_top = db.query(models.HobbyPost).filter(
            models.HobbyPost.hobby_category_id == guide_cat.id,
            models.HobbyPost.is_system == True
        ).first()

        new_guide_content = """「推し道」では写真、画像の投稿はできません。テキストのみ投稿可能です。
English follows Japanese.
        
「推し道」のアプリケーションは以下の4つのページで構成されています。

【HOME】じぶんの気分を登録し、直近のともだちの気分を知る。
【コミュニティ】同担とつながる。
【ともだち】ともだちを登録、アプリ内管理する。
【MY PAGE】じぶんのデータ編集と、各ページのリンク、じぶんのFeeling/Activity LOGの保管場所。

しんらいできる相手とゆるくつながることを目標にこのアプリケーションをつくりました。

サービスを継続して運営するため、「広告なしプラン」「MEET UP」「AD（広告）」「ともだちログの企業利用」などの仕組みを設け、料金設定を行っています。

また、MY PAGEにご登録いただいた情報は、サービス改善や統計データとして利用させていただく場合があります。
ご登録いただく情報には、メールアドレス、年齢、住所（都道府県・市区町村）、ジェンダーなどが含まれます。
これらの個人情報は、適切な安全管理措置を講じて管理し、法令に基づく場合を除き、本人の同意なく第三者へ提供することはありません。

なお、決済には安全な決済サービスであるStripeを利用しており、クレジットカード情報を当サービス側で保存することはありません。

---

Important Notice:
Please note that "Oshidou" is a text-only platform. Photo and image uploads are not supported.

App Overview:
The Oshidou application consists of the following four main pages:

【HOME】 Update your own status and see the recent "Feelings" of your friends.

【COMMUNITY】 Connect with fellow fans who share your interests (Dou-tan).

【FRIENDS】 Register and manage your friends within the app.

【MY PAGE】 Edit your profile, access page links, and view your personal Feeling/Activity LOG history.

Our Concept & Operations:
We created this application with the goal of fostering gentle, trust-based connections with reliable people.
To ensure sustainable operations, we have established a fee structure that includes features such as an "Ad-free Plan," "MEET UP" events, "Advertisements," and "Corporate usage of friend logs."

Privacy & Security:
Information registered on your MY PAGE may be used for service improvements and as statistical data. This information includes your email address, age, location (prefecture/city), and gender. We manage all personal data with strict security measures and will not provide it to third parties without your consent, except as required by law.

Furthermore, we use Stripe, a secure payment service, for all transactions. Your credit card information is never stored on our servers."""
    if not existing_guide_top:
        db.add(models.HobbyPost(
            content=new_guide_content,
            hobby_category_id=guide_cat.id,
            user_id=admin_user.id,
            is_system=True,
            is_meetup=False,
            is_ad=False,
        ))
        print(" ✅ GUIDE 親カテゴリ 初期投稿完了")
    else:
        existing_guide_top.content = new_guide_content
        print(" ✅ GUIDE 親カテゴリ 説明文を更新しました")

    if admin_user and guide_cat:
        existing_guide_top = db.query(models.HobbyPost).filter(
            models.HobbyPost.hobby_category_id == guide_cat.id,
            models.HobbyPost.is_system == True
        ).first()

        if not existing_guide_top:
            db.add(...)
        else:
            existing_guide_top.content = new_guide_content

    # これで、下の guide_cat.id が正しく読み取れるようになります
    home_cat = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.name == "🏠 HOME",
        models.HobbyCategory.parent_id == guide_cat.id
    ).first()
    
    if admin_user and home_cat:
        existing = db.query(models.HobbyPost).filter(
            models.HobbyPost.hobby_category_id == home_cat.id,
            models.HobbyPost.is_system == True
        ).first()
        
        new_content = """🏠 HOME の使い方

【CURRENT FEELING】
200文字で今の気持ちを記録しよう。
Record your mood in 200 characters.

【FEELING LOGS】
Feeling LOGは最長3か月・最大1000件保存可能です。
保管場所はMY PAGEです。
公開/非公開の設定はMY PAGEのプロフィール編集から行えます。
Feeling/Activity LOG is saved for up to 3 months / 1,000 entries.
You can manage visibility in MY PAGE > Profile Settings.

【ともだちs' LOG】
繋がったともだち・身近な人の気持ちが表示されます。
（公開設定をしている人のみ）
See how your friends are feeling today.
(Only for friends who set mood to public)

ともだちの追加は「ともだち」ページからできます。
詳しくは「👥 ともだち FRIENDS」をご確認ください。

ともだち's LOGの基本表示はエモジとその感情です。
詳細表示にすると、言葉もともだちのページに表示されます。
設定はMY PAGEのプロフィール編集から行えます。
ともだちのフォロー/アンフォローも設定可能です。

You can follow/unfollow friends anytime."""
        if not existing:
            db.add(models.HobbyPost(
                content=new_content,
                hobby_category_id=home_cat.id,
                user_id=admin_user.id,
                is_system=True,
                is_meetup=False,
                is_ad=False,
            ))
            print(" ✅ HOME 初期投稿完了")
        else:
            existing.content = new_content
            print(" ✅ HOME 説明文を更新しました")

    friends_cat = db.query(models.HobbyCategory).filter(
            models.HobbyCategory.name == "👥 ともだち FRIENDS",
            models.HobbyCategory.parent_id == guide_cat.id
    ).first()
        
    if admin_user and friends_cat:
        existing = db.query(models.HobbyPost).filter(
            models.HobbyPost.hobby_category_id == friends_cat.id,
            models.HobbyPost.is_system == True
        ).first()
        
        new_content = """👥 ともだち FRIENDS の使い方

【ともだちと繋がることによりできること】
ともだちと投稿時の感情を共有できます。
何かが起きたとき、繋がりのあるともだちに、自分の無事をシンプルに伝えることができます。

By connecting with friends, you can share your feelings.
In case of emergency, you can simply let your friends know you're safe.

⚠️注意：ともだち登録には上限があります。
上限  10人
11人目以降  一人毎 100円/月

⚠️ Notice: Friend Limit
Up to 10 friends: FREE
From the 11th friend onwards: 100 JPY per additional friend / month

【検索 / Search】
実際に会った人のニックネームで検索して申請しましょう。
付き合いの長さよりも「こころ許せる」仲を大切に。
Search by nickname of someone you've actually met.

【承認 / Approve】
知っている人ですか？こころ許せる仲ですか？
付き合いの長さより「こころ許せる」仲が大事。
Is this someone you know and trust?

【一覧 / List】
ともだち承認した人々を管理できます。
Manage your approved friends here."""
        if not existing:
            db.add(models.HobbyPost(
                content=new_content,
                hobby_category_id=friends_cat.id,
                user_id=admin_user.id,
                is_system=True,
                is_meetup=False,
                is_ad=False,
            ))
            print(" ✅ HOME 初期投稿完了")
        else:
            existing.content = new_content
            print(" ✅ HOME 説明文を更新しました")
            
    community_cat = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.name == "💬 コミュニティ COMMUNITY",
        models.HobbyCategory.parent_id == guide_cat.id
    ).first()
    
    if admin_user and community_cat:
        existing = db.query(models.HobbyPost).filter(
            models.HobbyPost.hobby_category_id == community_cat.id,
            models.HobbyPost.is_system == True
        ).first()
        
        if not existing:
            db.add(models.HobbyPost(
                content="""💬 コミュニティ COMMUNITY の使い方

【Community Exploration】
推しがこの世に生まれたことに感謝し、推しの親のような気持ちになって投稿しましょう。
Be grateful your passion exists in this world.
Post with the heart of a proud parent.

推しが何かをしても、それが犯罪でない限り罪ではありません。
推しが生物でないならば、100年先も続くことをイメージしましょう。
Unless it's a crime, support your passion unconditionally.

差別的な発言・追いつめるような発言、その他Chatにおいてダメとされていること全て禁止します。
Discriminatory or harassing language is strictly prohibited.

Community ExplorationではChat、MEET UP、ADの投稿ができます。
You can post Chats, MEET UPs, and ADs in Community Exploration.

---

【MEET UP（交流会）】
投稿料金：¥500
※主催者はStripeへの登録が必要です。
Post fee: ¥500 / Host must register with Stripe.

有料の交流会にする場合、当日現金またはStripeでの費用回収が可能です。
Stripeでの費用回収を選択した場合、回収費の5%がプラットフォーム手数料として、
また銀行への振込時に別途振込手数料が必要になります。
If charging attendees via Stripe, a 5% fee applies.

# MEET UPのゆるやかな設定 / Gentle guidelines
・同担にジェンダーなし、年齢制限なしでお願いします。
  No gender or age restrictions among fans.
・まずは「推しのどこが好きなのか」「いつ神になったのか」から。
  Start with "What do you love about your passion?"
・開催のおすすめは推しイベントの後です。
  Best held right after a fan event.

---

【AD（広告）】
広告の発信は有料です。
Posting advertisements is a paid service.

参加者599人まで → ¥500
参加者600人以上 → 1人 × 1円（下2桁切り捨て）
Up to 599 members → ¥500
600+ members → ¥1 per member (rounded down to hundreds)

自分が参加しているGroupに投稿することができます。
You can post ads to any Group you have joined.""",
                hobby_category_id=community_cat.id,
                user_id=admin_user.id,
                is_system=True,
                is_meetup=False,
                is_ad=False,
            ))
            print(" ✅ COMMUNITY 初期投稿完了")
        else:
            print(" ⏩ スキップ (投稿済)")

    mypage_cat = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.name == "👤 MY PAGE",
        models.HobbyCategory.parent_id == guide_cat.id
    ).first()
    
    if admin_user and mypage_cat:
        existing = db.query(models.HobbyPost).filter(
            models.HobbyPost.hobby_category_id == mypage_cat.id,
            models.HobbyPost.is_system == True
        ).first()
        
        new_content = """👤 MY PAGE の使い方

【プロフィール編集 / Profile Settings】
ニックネームを設定してください。
設定がない場合、メールアドレスのドメインがニックネームとして表示されます。
Please set your nickname.
If not set, your email domain will be shown as your nickname.

住んでいる都道府県を入れておくと、自分がJOINしているCommunityでMEET UPが投稿されたときに通知が届き、
お近くの同担ともだちが作りやすくなります。
Adding your prefecture helps you get notified of nearby MEET UPs
in communities you've joined.

SNSを登録しておくと、あなたについてよりわかってもらえます。
Registering your SNS helps others know more about you.

MEET UPの参加前にはいろいろ登録しておきましょう。
Please fill in your profile before joining a MEET UP.

自分のActivity・Feelingの表示設定を変えることができます。
You can manage the visibility of your Activity and Feeling logs.

---

【自己紹介 / About Me】
プロフィール編集に入れた内容が表示されます。
Your profile information will be shown here.

---

【COMMUNITIES LIST】
自分がJOINしたCOMMUNITYへのリンクが表示されます。
Links to all communities you have joined.

---

【JOINING & MY MEETUPS LIST】
自分が参加表明、または自分が設定したMEET UPへのリンクが表示されます。
Links to MEET UPs you are joining or hosting.

---

【Activity Logs】
記録しているFeeling/Activity Logsが表示されます。
Logは最大3か月間、最長1000件保存されています。
Logは200円（1日一回まで）でその時の最大数をダウンロードすることができます。"""
        if not existing:
            db.add(models.HobbyPost(
                content=new_content,
                hobby_category_id=mypage_cat.id,
                user_id=admin_user.id,
                is_system=True,
                is_meetup=False,
                is_ad=False,
            ))
            print(" ✅ HOME 初期投稿完了")
        else:
            existing.content = new_content
            print(" ✅ HOME 説明文を更新しました")

    db.commit()
    print("✅ 全てのデータ投入が完了しました！")

# --- [5. ガイド用コミュニティの作成] ---
    guide_comm_name = "How to walk the osidou"
    exists_guide = db.query(models.Community).filter(models.Community.name == guide_comm_name).first()
    
    if not exists_guide:
        new_guide = models.Community(
            name=guide_comm_name,
            description="""基本的な使い方 Basic Usage
■ HOME
・TODAY's FEELING: 200文字で今の気持ちを記録する
・ともだち's LOG: ともだち、身近な人の気持ちを表示
■ COMMUNITY
・Chat: 気持ちは推しの親
・MEET UP: 同担にジェンダー・年齢制限なし。トピックは広めに！
■ FRIENDS
・検索・承認: 本当に「こころ許せる」仲を大事に。
■ MY PAGE
・プロフィール編集: 都道府県設定で近くの同担を見つけやすく。""",
            owner_id=1, # 最初に作成したmihoさんのIDなどを想定
            is_active=True
        )
        db.add(new_guide)
        print(f" ✅ ガイドコミュニティ作成完了: {guide_comm_name}")

if __name__ == "__main__":
    db = Session(bind=engine)
    try:
        create_initial_data(db)
    except Exception as e:
        db.rollback()
        print(f"❌ エラー発生: {e}")
    finally:
        db.close()
