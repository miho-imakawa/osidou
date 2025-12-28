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
        {
            "name": "MUSIC", "prefix": "M",
            "children": [
                {"name": "DOer (演奏)", "role_type": models.HobbyRoleType.DOERS, "children": [
                    {"name": "J-POP", "children": [{"name": "Band (バンド)", "children": [{"name": "Bass"}, {"name": "Drums"}, {"name": "Guitar"}]}]},
                    {"name": "J-ROCK", "children": [{"name": "Band (バンド)", "children": [{"name": "Bass"}, {"name": "Drums"}, {"name": "Guitar"}]}]},
                    {"name": "JAZZ"}, {"name": "POP"}, {"name": "ROCK"}
                ]},
                {"name": "FANs (推し)", "role_type": models.HobbyRoleType.FANS, "children": [
                    {"name": "J-POP", "children": [{"name": "Mr.Children"}, {"name": "スピッツ (SPITZ)"}, {"name": "平井 堅 (Ken Hirai)"}]},
                    {"name": "J-ROCK", "children": [{"name": "B'z"}]},
                    {"name": "JAZZ"}, {"name": "POP"}, {"name": "ROCK"}
                ]}
            ]
        },
        {
            "name": "SPORT (スポーツ)", "prefix": "S",
            "children": [
                {"name": "DOer (する人)", "role_type": models.HobbyRoleType.DOERS, "children": [{"name": "Baseball (野球)"}, {"name": "Basketball (バスケ)"}, {"name": "Soccer (サッカー)"}]},
                {"name": "FANs (観る人)", "role_type": models.HobbyRoleType.FANS, "children": [{"name": "Baseball", "children": [{"name": "大谷 翔平 (Shohei Otani)"}]}, {"name": "Basketball"}, {"name": "Soccer"}]}
            ]
        },
        {
            "name": "REGIONS (地域)", "prefix": "R",
            "children": [
                {"name": "日本 (Japan)", "children": japan_children},
                {"name": "France (フランス)"}, {"name": "USA (アメリカ)"}
            ]
        }
    ]

# --- [4. 再帰挿入関数] ---
def insert_category(db: Session, data: dict, parent_id: Optional[int] = None, depth: int = 0, default_prefix: str = ""):
    prefix = data.get("prefix", default_prefix)
    new_cat = models.HobbyCategory(
        name=data["name"],
        parent_id=parent_id,
        depth=depth,
        role_type=data.get("role_type"),
        unique_code=generate_code(prefix=prefix)
    )
    db.add(new_cat); db.flush()
    if "children" in data:
        for child in data["children"]:
            insert_category(db, child, new_cat.id, depth + 1, prefix)

# --- [5. 実行メインロジック] ---
def create_initial_data(db: Session):
    print("--- DBリセット中 ---")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    print("--- カテゴリ投入中 (日本全国・併記・コード付与) ---")
    hierarchy = build_hierarchy()
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