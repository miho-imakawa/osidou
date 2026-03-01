import os
import sys
import string
import random
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

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
            if "豊島区" in city:
                city_item["children"].append({"name": "千川エリア (Senkawa Area)", "prefix": "R", "alias": "千川"})
            cities.append(city_item)
        japan_children.append({"name": pref["name"], "prefix": "R", "children": cities})

    return [
    # MUSIC
    {
        "name": "MUSIC (音楽)", "prefix": "M",
        "children": [
            # --- POP ---
            {"name": "POP", "children": [
                {"name": "Doers (演奏・歌唱)", "children": [
                    {"name": "Karaoke (カラオケ)"}, # 💡 独立配置
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
                        {"name": "Southern All Stars", "alias": "サザン", "is_master": True, "children": [
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
                            {"name": "岡村和義", "is_master": True} # 派生ユニット
                        ]},
                        {"name": "岡村靖幸", "is_master": True, "children": [
                            {"name": "岡村和義", "is_master": True} # 派生ユニット（ここからも辿れる）
                        ]}
                    ]},
                    {"name": "K-POP", "children": [{"name": "BTS", "is_master": True}]},
                    {"name": "Funk", "children": [{"name": "Bruno Mars", "is_master": True}]}
                ]}
            ]},

            # --- ROCK ---
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

            # --- CLASSIC ---
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

            # --- JAZZ ---
            {"name": "JAZZ", "children": [
                {"name": "Doers", "children": [
                    {"name": "Band", "children": [
                        {"name": "Sax"}, {"name": "Trumpet"}, {"name": "Piano"}, {"name": "Bass"}, {"name": "Drums"}, {"name": "Guitar"}
                    ]}
                ]},
                {"name": "FANs", "children": [
                    {"name": "Gershwin", "is_master": True}
                ]}
            ]}
        ]
    },
    # --- VIDEO & STREAMING ---
        {
            "name": "VIDEO & STREAMING (映像・配信)", "prefix": "V",
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
                            {"name": "OTAKING (岡田斗司夫ゼミ)", "alias": "オタキング", "is_master": True, "children": [{"name": "岡田斗司夫", "is_master": True}]},
                            {"name": "ひろゆき / hiroyuki", "alias": "ひろゆき", "is_master": True},
                            {"name": "メンタリスト Daigo", "alias": "Daigo", "is_master": True},
                            {"name": "HIKAKIN"}, {"name": "Fischer's"}, {"name": "Comdot"}, {"name": "Hajime Shacho"}
                        ]},
                        {"name": "Amazon Prime Video", "children": [{"name": "The Boys"}]},
                        {"name": "Disney+", "children": [{"name": "The Mandalorian"}, {"name": "Loki"}]}
                        ]}
                    ]
                }
            ]
        }, # 💡 ここに閉じカッコとカンマを追加！
        # 3. TRADITION (追加予定)
# --- TRADITION (伝統・文化) ---
        {
            "name": "TRADITION (伝統)", "prefix": "T",
            "children": [
                # 1. Festival (祭り) - 祭りとして参加・観覧するもの
                {
                    "name": "Festival (祭り)",
                    "children": [
                        {
                            "name": "Religious Festivals (宗教的祭礼)",
                            "children": [
                                {"name": "Japan", "children": [
                                    {"name": "祇園祭", "children": [{"name": "Doers"}]},
                                    {"name": "神田祭", "children": [{"name": "Doers"}]},
                                    {"name": "葵祭", "children": [{"name": "Doers"}]}
                                ]}
                            ]
                        },
                        {
                            "name": "Fire Festivals (火祭り)",
                            "children": [
                                {"name": "Japan", "children": [
                                    {"name": "那智の火祭り", "children": [{"name": "Doers"}]},
                                    {"name": "鬼夜", "children": [{"name": "Doers"}]},
                                    {"name": "左義長まつり", "children": [{"name": "Doers"}]}
                                ]},
                                {"name": "Spain", "children": [{"name": "Las Fallas (バレンシアの火祭り)", "children": [{"name": "Doers"}]}]}
                            ]
                        },
                        {
                            "name": "Procession & Carnival (行列・カーニバル)",
                            "children": [
                                {"name": "Japan", "children": [
                                    {"name": "盛岡さんさ踊り", "children": [
                                        {"name": "盛岡さんさ踊り（踊り）"},
                                        {"name": "Doers"}
                                    ]},
                                    {"name": "阿波踊り", "children": [
                                        {"name": "阿波踊り（踊り）"},
                                        {"name": "Doers"}
                                    ]},
                                    {"name": "青森ねぶた祭", "children": [{"name": "Doers"}]},
                                    {"name": "高山祭", "children": [{"name": "Doers"}]},
                                    {"name": "岸和田だんじり祭", "children": [{"name": "Doers"}]},
                                    {"name": "仙台七夕", "children": [{"name": "Doers"}]}
                                ]},
                                {"name": "Brazil", "children": [{"name": "Rio Carnival", "children": [{"name": "Doers"}]}]},
                                {"name": "UK", "children": [{"name": "Notting Hill Carnival", "children": [{"name": "Doers"}]}]}
                            ]
                        },
                        {
                            "name": "Harvest & Season (収穫・季節)",
                            "children": [
                                {"name": "Japan", "children": [
                                    {"name": "よさこい", "children": [
                                        {"name": "よさこい（踊り）"},
                                        {"name": "Doers"}
                                    ]},
                                    {"name": "盆踊り", "children": [
                                        {"name": "盆踊り（踊り）"},
                                        {"name": "Doers"}
                                    ]},
                                    {"name": "新嘗祭", "children": [{"name": "Doers"}]},
                                    {"name": "大原はだか祭り", "children": [{"name": "Doers"}]},
                                    {"name": "おわら風の盆", "children": [
                                        {"name": "おわら風の盆（踊り）"},
                                        {"name": "Doers"}
                                    ]},
                                    {"name": "西馬音内盆踊り", "children": [
                                        {"name": "西馬音内盆踊り（踊り）"},
                                        {"name": "Doers"}
                                    ]},
                                    {"name": "YOSAKOIソーラン祭り", "children": [
                                        {"name": "YOSAKOI（踊り）"},
                                        {"name": "Doers"}
                                    ]}
                                ]},
                                {"name": "Mexico", "children": [{"name": "Dia de los Muertos (死者の日)", "children": [{"name": "Doers"}]}]},
                                {"name": "USA / Canada", "children": [{"name": "Thanksgiving (感謝祭)"}]},
                                {"name": "Germany", "children": [{"name": "Oktoberfest (オクトーバーフェスト)"}]}
                            ]
                        },
                        {
                            "name": "Fireworks & Light (花火・光)",
                            "children": [
                                {"name": "Japan", "children": [
                                    {"name": "隅田川花火大会"},
                                    {"name": "長岡まつり"},
                                    {"name": "なにわ淀川花火大会"}
                                ]},
                                {"name": "France", "children": [{"name": "Bastille Day Fireworks (パリ祭)"}]},
                                {"name": "India", "children": [{"name": "Diwali (光の祭)"}]},
                                {"name": "Global / Islam", "children": [{"name": "Eid al-Fitr (断食明けの祭)"}]},
                                {"name": "USA", "children": [{"name": "Burning Man"}]}
                            ]
                        }
                    ]
                },

                # 2. Folk Music & Dance (民族音楽・舞踊) - 稽古・活動として
                {
                    "name": "Folk Music & Dance (民族音楽・舞踊)",
                    "children": [
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
                            {"name": "Spain", "children": [{"name": "Flamenco", "children": [{"name": "Doers"}]}]},
                            {"name": "Ireland", "children": [{"name": "Irish Dance and Music", "children": [{"name": "Doers"}]}]}
                        ]},
                        {"name": "Polynesia", "children": [
                            {"name": "Hawaii", "children": [
                                {"name": "Hula", "children": [
                                    {"name": "Chant", "children": [{"name": "Doers"}]},
                                    {"name": "Dance", "children": [{"name": "Doers"}]}
                                ]}
                            ]}
                        ]}
                    ]
                },

                # 3. Craft (工芸)
                {
                    "name": "Craft (工芸)",
                    "children": [
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
                    ]
                },

                # 4. Accomplishments (たしなみ)
                {
                    "name": "Accomplishments (たしなみ)",
                    "children": [
                        {"name": "Tea Ceremony (茶道)", "children": [{"name": "Doers"}]},
                        {"name": "Flower Arrangement (華道)", "children": [{"name": "Doers"}]},
                        {"name": "Calligraphy (書道)", "children": [{"name": "Doers"}]},
                        {"name": "Traditional Dance (日本舞踊)", "children": [{"name": "Doers"}]}
                    ]
                }
            ]
        },       

        # 4. SPORTS (追加予定)
        # {
        #     "name": "SPORTS (スポーツ)", "prefix": "S",
        #     "children": []
        # },
        # 5. THEATER (追加予定)
        # {
        #     "name": "THEATER (演劇・舞台)", "prefix": "TH",
        #     "children": []
        # },
        # 6. POP CULTURE (追加予定)
        # {
        #     "name": "POP CULTURE", "prefix": "P",
        #     "children": []
        # },
        # 7. FOOD (追加予定)
        # {
        #     "name": "FOOD (食・グルメ)", "prefix": "F",
        #     "children": []
        # },
        # 8. LITERATURE (追加予定)
        # {
        #     "name": "LITERATURE (文学・本)", "prefix": "LT",
        #     "children": []
        # },
        # 9. ART (追加予定)
        # {
        #     "name": "ART (芸術)", "prefix": "A",
        #     "children": []
        # },

# --- PEOPLE ---
        {
            "name": "PEOPLE (人物)", "prefix": "P",
            "children": [
                {"name": "Fans", "children": [
                    {"name": "Actors / Artists", "children": [
                        {"name": "佐藤健", "is_master": True,},
                        {"name": "福山雅治", "is_master": True,}
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
    ]

# --- [4. 挿入ロジック (マスター連携)] ---
name_to_id_map = {}

def insert_category(db: Session, data: dict, parent_id: Optional[int] = None, depth: int = 0, default_prefix: str = ""):
    global name_to_id_map
    prefix = data.get("prefix", default_prefix)
    name = data["name"]
    alias = data.get("alias")
    is_master = data.get("is_master", False)

    # 💡 1. すでに同じ階層に同じ名前のカテゴリがあるかチェック
    existing_cat = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.name == name,
        models.HobbyCategory.parent_id == parent_id,
        models.HobbyCategory.depth == depth
    ).first()

    if existing_cat:
        # すでにある場合は、それを使って「次に進む」
        current_cat_id = existing_cat.id
        # 本尊（Master）として登録が必要な場合はマップを更新
        if is_master and name not in name_to_id_map:
            name_to_id_map[name] = current_cat_id
    else:
        # 💡 2. ない場合だけ新しく作る
        master_id = name_to_id_map.get(name) if not is_master else None
        
        new_cat = models.HobbyCategory(
            name=name,
            alias_name=alias,
            parent_id=parent_id,
            master_id=master_id,
            depth=depth,
            role_type=data.get("role_type"),
            unique_code=generate_code(prefix=prefix)
        )
        db.add(new_cat)
        db.flush()
        current_cat_id = new_cat.id
        
        # 本尊（Master）として登録
        if is_master:
            name_to_id_map[name] = current_cat_id

    # 💡 3. 子供たちの処理（既存または新規のIDを親として渡す）
    if "children" in data:
        for child in data["children"]:
            insert_category(db, child, current_cat_id, depth + 1, prefix)
            
def create_initial_data(db: Session):
    print("--- データベース更新開始 (安全モード) ---")
    
    # 💡 闇を払うポイント1：全削除を停止し、既存データを守る
    # Base.metadata.drop_all(bind=engine)  
    
    # 💡 闇を払うポイント2：存在しないテーブル（将来のカラム追加分など）だけ作成
    Base.metadata.create_all(bind=engine)  

    print("--- カテゴリ投入 (差分更新) ---")
    hierarchy = build_hierarchy()
    
    # name_to_id_map を初期化（既存DBから読み込むように拡張も可能ですが、
    # 今は一旦この実行サイクル内での重複を防ぐ形を維持します）
    global name_to_id_map
    name_to_id_map = {}
    
    for item in hierarchy:
        insert_category(db, item)
    
    # 💡 テストユーザー作成も、すでに存在する場合はスキップするようにするとより安全です
    # （現状は重複エラーが出る可能性がありますが、テーブルを消さないので
    #  一度作成済みならこの後の処理はエラーで止まってもデータは守られます）
    
    # print("--- テストユーザー3名の作成 ---")
    common_password = get_password_hash("password123")
    
    test_users = [
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
    
    db.commit()
    print("✅ 全てのデータ投入が完了しました！")
    for u in test_users:
        print(f" - {u['email']}")

if __name__ == "__main__":
    db = Session(bind=engine)
    try:
        create_initial_data(db)
    except Exception as e:
        db.rollback()
        print(f"❌ エラー発生: {e}")
    finally:
        db.close()