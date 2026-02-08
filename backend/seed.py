import os
import sys
import string
import random
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

# パス設定
current_dir = os.path.dirname(os.path.abspath(__file__))
if 'app' not in current_dir:
    sys.path.append(os.path.join(current_dir, 'app'))

from app import models
from app.database import Base, engine
from app.utils.security import get_password_hash

# --- [1. 識別コード生成関数] ---
def generate_code(length=7, prefix=""):
    # 大文字 + 小文字 + 数字 (62種類)
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
    {"name": "青森県 (Aomori)", "cities": ["青森市 (Aomori City)"]},
    {"name": "岩手県 (Iwate)", "cities": ["盛岡市 (Morioka)"]},
    {"name": "宮城県 (Miyagi)", "cities": ["仙台市 (Sendai)"]},
    {"name": "秋田県 (Akita)", "cities": ["秋田市 (Akita City)"]},
    {"name": "山形県 (Yamagata)", "cities": ["山形市 (Yamagata City)"]},
    {"name": "福島県 (Fukushima)", "cities": ["福島市 (Fukushima City)"]},
    {"name": "茨城県 (Ibaraki)", "cities": ["水戸市 (Mito)"]},
    {"name": "栃木県 (Tochigi)", "cities": ["宇都宮市 (Utsunomiya)"]},
    {"name": "群馬県 (Gunma)", "cities": ["前橋市 (Maebashi)"]},
    {"name": "埼玉県 (Saitama)", "cities": ["さいたま市 (Saitama City)"]},
    {"name": "千葉県 (Chiba)", "cities": ["千葉市 (Chiba City)"]},
    {"name": "東京都 (Tokyo)", "cities": TOKYO_23_WARDS},
    {"name": "神奈川県 (Kanagawa)", "cities": ["横浜市 (Yokohama)"]},
    {"name": "新潟県 (Niigata)", "cities": ["新潟市 (Niigata City)"]},
    {"name": "富山県 (Toyama)", "cities": ["富山市 (Toyama City)"]},
    {"name": "石川県 (Ishikawa)", "cities": ["金沢市 (Kanazawa)"]},
    {"name": "福井県 (Fukui)", "cities": ["福井市 (Fukui City)"]},
    {"name": "山梨県 (Yamanashi)", "cities": ["甲府市 (Kofu)"]},
    {"name": "長野県 (Nagano)", "cities": ["長野市 (Nagano City)"]},
    {"name": "岐阜県 (Gifu)", "cities": ["岐阜市 (Gifu City)"]},
    {"name": "静岡県 (Shizuoka)", "cities": ["静岡市 (Shizuoka City)"]},
    {"name": "愛知県 (Aichi)", "cities": ["名古屋市 (Nagoya)"]},
    {"name": "三重県 (Mie)", "cities": ["津市 (Tsu)"]},
    {"name": "滋賀県 (Shiga)", "cities": ["大津市 (Otsu)"]},
    {"name": "京都府 (Kyoto)", "cities": ["京都市 (Kyoto City)"]},
    {"name": "大阪府 (Osaka)", "cities": ["大阪市 (Osaka City)"]},
    {"name": "兵庫県 (Hyogo)", "cities": ["神戸市 (Kobe)"]},
    {"name": "奈良県 (Nara)", "cities": ["奈良市 (Nara City)"]},
    {"name": "和歌山県 (Wakayama)", "cities": ["和歌山市 (Wakayama City)"]},
    {"name": "鳥取県 (Tottori)", "cities": ["鳥取市 (Tottori City)"]},
    {"name": "島根県 (Shimane)", "cities": ["松江市 (Matsue)"]},
    {"name": "岡山県 (Okayama)", "cities": ["岡山市 (Okayama City)"]},
    {"name": "広島県 (Hiroshima)", "cities": ["広島市 (Hiroshima City)"]},
    {"name": "山口県 (Yamaguchi)", "cities": ["山口市 (Yamaguchi City)"]},
    {"name": "徳島県 (Tokushima)", "cities": ["徳島市 (Tokushima City)"]},
    {"name": "香川県 (Kagawa)", "cities": ["高松市 (Takamatsu)"]},
    {"name": "愛媛県 (Ehime)", "cities": ["松山市 (Matsuyama)"]},
    {"name": "高知県 (Kochi)", "cities": ["高知市 (Kochi City)"]},
    {"name": "福岡県 (Fukuoka)", "cities": ["福岡市 (Fukuoka City)"]},
    {"name": "佐賀県 (Saga)", "cities": ["佐賀市 (Saga City)"]},
    {"name": "長崎県 (Nagasaki)", "cities": ["長崎市 (Nagasaki City)"]},
    {"name": "熊本県 (Kumamoto)", "cities": ["熊本市 (Kumamoto City)"]},
    {"name": "大分県 (Oita)", "cities": ["大分市 (Oita City)"]},
    {"name": "宮崎県 (Miyazaki)", "cities": ["宮崎市 (Miyazaki City)"]},
    {"name": "鹿児島県 (Kagoshima)", "cities": ["鹿児島市 (Kagoshima City)"]},
    {"name": "沖縄県 (Okinawa)", "cities": ["那覇市 (Naha)"]}
]

# --- [3. 階層データの構築ロジック] ---
def build_hierarchy():
    japan_children = []
    for pref in JAPAN_REGIONS_DATA:
        cities = []
        for city in pref["cities"]:
            city_item = {"name": city, "prefix": "R", "children": []}
            if "豊島区" in city:
                city_item["children"].append({"name": "千川エリア (Senkawa Area)", "prefix": "R"})
            cities.append(city_item)
        japan_children.append({"name": pref["name"], "prefix": "R", "children": cities})

    return [
        # --- 1. MUSIC ---
        {
            "name": "MUSIC (音楽)", "prefix": "M",
            "children": [
                {"name": "DOer (演奏者)", "role_type": models.HobbyRoleType.DOERS, "children": [
                    {"name": "Instrumental (楽器)", "children": [{"name": "Piano"}, {"name": "Guitar"}, {"name": "Drums"}]},
                    {"name": "Composer (作曲・DTM)"}
                ]},
                {"name": "FANs (推し)", "role_type": models.HobbyRoleType.FANS, "children": [
                    {"name": "J-POP / Idol", "children": [
                        {"name": "DOMOTO (KinKi Kids)", "children": [{"name": "堂本光一"}, {"name": "堂本剛"}]},
                        {"name": "Southern All Stars", "children": [{"name": "桑田佳祐"}]},
                        {"name": "Mr.Children"}, {"name": "Snow Man"}
                    ]},
                    {"name": "J-ROCK", "children": [{"name": "B'z"}, {"name": "GLAY"}, {"name": "ONE OK ROCK"}]},
                    {"name": "Global Styles", "children": [{"name": "ROCK"}, {"name": "POP"}, {"name": "JAZZ"}, {"name": "K-POP"}]}
                ]}
            ]
        },
        # --- 2. VIDEO & ENT ---
        {
            "name": "VIDEO & ENT (映像・発信)", "prefix": "V",
            "children": [
                {"name": "DOer (制作・演劇)", "role_type": models.HobbyRoleType.DOERS, "children": [
                    {"name": "Acting (演技・舞台)"}, {"name": "Video Making (制作・配信)"}
                ]},
                {"name": "FANs (推し)", "role_type": models.HobbyRoleType.FANS, "children": [
                    {"name": "Performers (出演者)", "children": [
                        {"name": "岡田斗司夫 (Toshio Okada)"},
                        {"name": "Robert De Niro"}, 
                        {"name": "Tatsuya Fujiwara (藤原竜也)"},
                        {"name": "佐藤健 (Takeru Sato)"}
                    ]},
                    {"name": "Programs (作品)", "children": [
                        {"name": "Movies (映画)"}, 
                        {"name": "TV / Drama", "children": [
                            {"name": "るろうに剣心", "children": [{"name": "佐藤健 (Takeru Sato)"}]}
                        ]}, 
                        {"name": "YouTube / Online", "children": [
                            {"name": "OTAKING", "children": [{"name": "岡田斗司夫 (Toshio Okada)"}]}
                        ]}
                    ]}
                ]}
            ]
        },
        # --- 3. ANIME & MANGA ---
        {
            "name": "ANIME & MANGA", "prefix": "A",
            "children": [
                {"name": "DOer (制作・漫画家)", "role_type": models.HobbyRoleType.DOERS, "children": [
                    {"name": "Illustration (イラスト)"}, {"name": "Manga Writing"}, {"name": "Cosplay"}
                ]},
                {"name": "FANs (作品軸)", "role_type": models.HobbyRoleType.FANS, "children": [
                    {"name": "Studio Ghibli", "children": [{"name": "宮崎 駿"}, {"name": "高畑 勲"}]},
                    {"name": "WORKS", "children": [
                        {"name": "One Piece", "children": [{"name": "MANGA"}, {"name": "ANIME"}, {"name": "CAST (CV)"}]},
                        {"name": "Pokemon", "children": [{"name": "ANIME"}, {"name": "GAME"}, {"name": "CAST (CV)"}]},
                        {"name": "Demon Slayer (鬼滅の刃)", "children": [{"name": "MANGA"}, {"name": "ANIME"}, {"name": "CAST (CV)"}]},
                        {"name": "NARUTO", "children": [{"name": "MANGA"}, {"name": "ANIME"}]}
                    ]}
                ]}
            ]
        },
        # --- 4. LIFE (LIFESTYLE) ---
        {
            "name": "LIFE", "prefix": "L",
            "children": [
                {"name": "DOer (こだわり・実践)", "role_type": models.HobbyRoleType.DOERS, "children": [
                    {"name": "Fashion Design"}, {"name": "Cooking / Recipe"}, {"name": "Interior / DIY"}
                ]},
                {"name": "FANs (探求・愛好)", "role_type": models.HobbyRoleType.FANS, "children": [
                    {"name": "Luxury Brands"}, {"name": "Gourmet"}, {"name": "Travel"}
                ]}
            ]
        },
        # --- 5. GAMES ---
        {
            "name": "GAMES", "prefix": "G",
            "children": [
                {"name": "DOer (開発・制作)", "role_type": models.HobbyRoleType.DOERS, "children": [
                    {"name": "Game Dev"}, {"name": "3D Modeling"}, {"name": "Indie Game"}
                ]},
                {"name": "FANs (プレイヤー)", "role_type": models.HobbyRoleType.FANS, "children": [
                    {"name": "eSports"}, {"name": "RPG"}, {"name": "FPS"}
                ]}
            ]
        },
        # --- 6-8. SPORT / REGIONS / FESTIVALS ---
        # --- 6. SPORT (スポーツ) ---
        {
            "name": "SPORT", "prefix": "S",
            "children": [
                {
                    "name": "DOer (プレイヤー)", 
                    "role_type": models.HobbyRoleType.DOERS,
                    "children": [
                        {"name": "Baseball (野球)"}, 
                        {"name": "Soccer (サッカー)"}, 
                        {"name": "Tennis (テニス)"},
                        {"name": "Running / Gym"}
                    ]
                },
                {
                    "name": "FANs (観戦・推し)", 
                    "role_type": models.HobbyRoleType.FANS,
                    "children": [
                        {"name": "MLB"}, 
                        {"name": "Professional Baseball (NPB)"},
                        {"name": "European Soccer"},
                        {"name": "Sumo / Martial Arts"}
                    ]
                }
            ]
        },
        # --- 7. REGIONS / 8. FESTIVALS ---
        { "name": "REGIONS (地域)", "prefix": "R", "children": japan_children },
        { "name": "FESTIVALS (お祭り)", "prefix": "F", "children": [{"name": "Traditional (伝統祭り)"}, {"name": "Events (イベント)"}] }        
    ]

# --- [4. リンク対応・再帰挿入関数] ---
# 💡 名前とIDの対応を一時的に保持するメモ
name_to_id_map = {}

def insert_category(db: Session, data: dict, parent_id: Optional[int] = None, depth: int = 0, default_prefix: str = ""):
    global name_to_id_map
    prefix = data.get("prefix", default_prefix)
    name = data["name"]

    # 💡 街の戦略：同じ名前が既に登録されていれば、それをマスターとする
    master_id = name_to_id_map.get(name)

    new_cat = models.HobbyCategory(
        name=name,
        parent_id=parent_id,
        master_id=master_id,  # 👈 ここでマスターを紐付け
        depth=depth,
        role_type=data.get("role_type"),
        unique_code=generate_code(prefix=prefix)
    )
    db.add(new_cat)
    db.flush()

    # 💡 初めて登録した名前なら、自分のIDをメモに残す
    if name not in name_to_id_map:
        name_to_id_map[name] = new_cat.id

    if "children" in data:
        for child in data["children"]:
            insert_category(db, child, new_cat.id, depth + 1, prefix)

# --- [5. 実行メインロジック] ---
def create_initial_data(db: Session):
    print("--- DBリセット中 ---")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    print("--- カテゴリ投入中 (日本全国・リンク対応) ---")
    hierarchy = build_hierarchy()
    
    # グローバルなメモをリセット
    global name_to_id_map
    name_to_id_map = {}
    
    for item in hierarchy:
        insert_category(db, item)
    
    print("--- 初期ユーザー作成中 ---")
    test_user = models.User(
        email="test@example.com",
        username="senkawa_user",
        nickname="千川っ子",
        public_code=generate_code(),
        hashed_password=get_password_hash("password123")
    )
    db.add(test_user)
    db.commit()
    print("✅ 全ての初期設定が完了しました！")

if __name__ == "__main__":
    db = Session(bind=engine)
    try:
        create_initial_data(db)
    except Exception as e:
        db.rollback()
        print(f"❌ エラー発生: {e}")
    finally:
        db.close()