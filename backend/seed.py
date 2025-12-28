import os
import sys
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

# 🚨 【重要】ルートディレクトリから実行することを前提としたパス設定
# app/ フォルダをPythonのパスに追加
current_dir = os.path.dirname(os.path.abspath(__file__))
if 'app' not in current_dir: # seed.py が app/ の外にあることを想定
    sys.path.append(os.path.join(current_dir, 'app'))

from app import models
from app.database import Base, engine # engine, Base を直接インポート
from app.models import HobbyRoleType # 👈 HobbyRoleType をインポート
from app.utils.security import get_password_hash # 👈 パスワードハッシュ化関数をインポート

# --- [都道府県・県庁所在地データ] ---
PREFECTURE_CAPITALS = {
    "北海道": "札幌市", "青森県": "青森市", "岩手県": "盛岡市", "宮城県": "仙台市",
    "秋田県": "秋田市", "山形県": "山形市", "福島県": "福島市", "茨城県": "水戸市",
    "栃木県": "宇都宮市", "群馬県": "前橋市", "埼玉県": "さいたま市", "千葉県": "千葉市",
    "東京都": "新宿区", "神奈川県": "横浜市", "新潟県": "新潟市", "富山県": "富山市",
    "石川県": "金沢市", "福井県": "福井市", "山梨県": "甲府市", "長野県": "長野市",
    "岐阜県": "岐阜市", "静岡県": "静岡市", "愛知県": "名古屋市", "三重県": "津市",
    "滋賀県": "大津市", "大津市": "大津市", "京都府": "京都市", "大阪府": "大阪市",
    "兵庫県": "神戸市", "奈良県": "奈良市", "和歌山県": "和歌山市", "鳥取県": "鳥取市",
    "島根県": "松江市", "岡山県": "岡山市", "広島県": "広島市", "山口県": "山口市",
    "徳島県": "徳島市", "香川県": "高松市", "愛媛県": "松山市", "高知県": "高知市",
    "福岡県": "福岡市", "佐賀県": "佐賀市", "長崎県": "長崎市", "熊本県": "熊本市",
    "大分県": "大分市", "宮崎県": "宮崎市", "鹿児島県": "鹿児島市", "沖縄県": "那覇市",
}

# --- [街づくりカテゴリの動的生成] ---
def generate_machizukuri_hierarchy():
    children = []
    for pref, city in PREFECTURE_CAPITALS.items():
        children.append({
            "name": pref, # Depth 1 (都道府県)
            "children": [
                {
                    "name": city, # Depth 2 (県庁所在地の市区町村)
                    "children": [], 
                },
            ],
        })
    return {
        "name": "街づくり・地方創生",
        "children": children
    }

# --- [データ定義の修正] ---
INITIAL_HOBBY_HIERARCHY_DATA = [
    # 💡 音楽カテゴリ (Fans と Doers の両方を定義)
    {
        "name": "音楽",
        "children": [
            # --- 1. Fans (見る人/聞く人) ---
            {
                "name": "Fans",
                "role_type": models.HobbyRoleType.FANS, 
                "children": [
                    {
                        "name": "J-POP",
                        "children": [
                            {"name": "Mr.Children"},
                            {"name": "米津玄師"},
                            {"name": "Mrs. GREEN APPLE"},
                            {"name": "藤井風"},
                        ],
                    },
                ],
            },
            # --- 2. Doers (する人/演奏する人) ---
            {
                "name": "する人",
                "role_type": models.HobbyRoleType.DOERS, 
                "children": [
                    {
                        "name": "楽器",
                        "children": [
                            {"name": "ギター"}, # 👈 ここに Guitar を追加
                            {"name": "ドラム"},
                            {"name": "ピアノ"},
                        ],
                    },
                    {"name": "歌唱 (カラオケ/バンド)"},
                ],
            },
        ],
    },
    # 💡 趣味カテゴリ (スポーツ, 文化・芸術) (既存)
    {
        "name": "スポーツ",
        "children": [
            {
                "name": "する人",
                "role_type": models.HobbyRoleType.DOERS, 
                "children": [
                    {
                        "name": "サッカー",
                        "children": [
                            {"name": "フットサル"},
                        ],
                    },
                ],
            },
        ],
    },
    {
        "name": "文化・芸術",
        "children": [
            {
                "name": "する人",
                "role_type": models.HobbyRoleType.DOERS, 
                "children": [
                    {
                        "name": "絵画",
                        "children": [
                            {"name": "水彩画"},
                        ],
                    },
                ],
            },
        ],
    },
    # 💡 街づくりカテゴリ (既存)
    generate_machizukuri_hierarchy()
]

INITIAL_USER_DATA = [
    {
        "email": "test1@example.com",
        "password": "password123", # プレーンテキストで用意
        "username": "tanaka_fs",
        "nickname": "田中_フットサル好き",
        "prefecture": "東京都",
        "city": "渋谷区",
        "town": "宇田川町",
        "is_active": True,
        "bio": "フットサルと地元の街おこしに情熱を燃やしています！",
        "oshi_page_url": None, # 入推しリンクなし
        "facebook_url": "https://facebook.com/tanaka_fs", 
        "x_url": None, 
        "instagram_url": None,
        "note_url": None,
    },
    {
        "email": "test2@example.com",
        "password": "password123",
        "username": "sato_painter",
        "nickname": "佐藤_水彩画",
        "prefecture": "大阪府",
        "city": "大阪市",
        "town": "堂島",
        "is_active": True,
        "bio": "水彩画を描いています。気分ログはいつもONです。",
        "oshi_page_url": None,
        "facebook_url": None,
        "x_url": None,
        "instagram_url": "https://instagram.com/sato_art",
        "note_url": None,
    },
    # 💡 新規追加ユーザー (鈴木ミスチルファン)
    {
        "email": "suzuki@mr-children.com",
        "password": "password123",
        "username": "suzuki_mrchildren",
        "nickname": "鈴木_桜井さん推し",
        "prefecture": "神奈川県",
        "city": "横浜市",
        "town": "西区",
        "is_active": True,
        "bio": "Mr.Childrenを20年推しています。人生のサウンドトラックはミスチル一択！",
        # 💡 入推しリンクを設定
        "oshi_page_url": "https://www.mrchildren.jp/", 
        "facebook_url": None,
        "x_url": "https://x.com/suzuki_oshi",
        "instagram_url": "https://instagram.com/suzuki_mrchildren",
        "note_url": None,
    },
]

# --- [ヘルパー関数] ---

def insert_category_recursively(db: Session, data: dict, parent_id: Optional[int] = None, current_depth: int = 0):
    """HobbyCategoryを再帰的に挿入する。"""
    category_name = data.get("name")
    
    # HobbyCategory の新しいインスタンスを作成
    new_category = models.HobbyCategory(
        name=category_name,
        parent_id=parent_id,
        depth=current_depth, 
        role_type=data.get("role_type") if "role_type" in data else None,
        # description がデータに存在しない場合は None を設定
        description=data.get("description", None) 
    )
    db.add(new_category); db.flush()
    print(f"  -> Category: {category_name} (ID: {new_category.id}, Parent ID: {parent_id}, Depth: {current_depth})")
    
    # 子要素を再帰的に処理
    if "children" in data:
        for child_data in data["children"]:
            insert_category_recursively(db, child_data, new_category.id, current_depth + 1)

    return new_category.id

# --- [データ投入ロジック] ---

def create_initial_data(db: Session):
    print("--- データベースの初期化 ---")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("テーブルを再作成しました。")
    
    print("\n--- 趣味階層データ (HobbyCategory) の投入 ---")
    
    # 階層データを再帰的に投入
    for cat_data in INITIAL_HOBBY_HIERARCHY_DATA:
        insert_category_recursively(db, cat_data, current_depth=0)

    db.commit()


    # 初期ユーザーデータの投入
    print("\n--- 初期ユーザーデータの投入 ---")
    user_map = {}
    for user_data in INITIAL_USER_DATA:
        # プレーンパスワードを取得し、ハッシュ化
        password = user_data["password"]
        
        # パスワード長を72バイトに制限 (bcryptの制限回避)
        if len(password.encode('utf-8')) > 72:
            password = password[:72] 
        
        # 修正済みのsecurity.py (sha256_crypt優先) を使用
        hashed_password = get_password_hash(password)
        
        # Userモデルのインスタンスを作成 (辞書展開で全フィールドを投入)
        user = models.User(
             # username, email, nickname, 住所, SNSリンクなどが一度に渡される
             **{k: v for k, v in user_data.items() if k not in ["password"]}
        )
        user.hashed_password = hashed_password # ハッシュ化されたパスワードをセット
        
        db.add(user)
        db.flush() 
        user_map[user.nickname] = user
        print(f"  -> User: {user.nickname} ({user.email}) - Oshi Link: {user.oshi_page_url}")

    db.commit()

    # ユーザーとカテゴリの関連付け (テスト用)
    print("\n--- ユーザーとカテゴリの関連付け (UserHobbyLink) ---")
    
    # 1. 田中さん -> フットサル
    user1 = user_map.get("田中_フットサル好き")
    category_futsal = db.query(models.HobbyCategory).filter(models.HobbyCategory.name == "フットサル").first()
    if user1 and category_futsal:
        link = models.UserHobbyLink(user_id=user1.id, hobby_category_id=category_futsal.id)
        db.add(link)
        print(f"  -> {user1.nickname} を Category: {category_futsal.name} にリンク。")
        
    # 2. 佐藤さん -> 大阪市 (街づくり)
    user2 = user_map.get("佐藤_水彩画")
    category_osaka_city = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.name == "大阪市",
        models.HobbyCategory.depth == 2,
    ).first()
    if user2 and category_osaka_city:
        link = models.UserHobbyLink(user_id=user2.id, hobby_category_id=category_osaka_city.id)
        db.add(link)
        print(f"  -> {user2.nickname} を Category: {category_osaka_city.name} にリンク。")

    # 3. 鈴木さん -> Mr.Children (新しい推し)
    user3 = user_map.get("鈴木_桜井さん推し")
    category_mrchildren = db.query(models.HobbyCategory).filter(models.HobbyCategory.name == "Mr.Children").first()
    if user3 and category_mrchildren:
        link = models.UserHobbyLink(user_id=user3.id, hobby_category_id=category_mrchildren.id)
        db.add(link)
        print(f"  -> {user3.nickname} を Category: {category_mrchildren.name} (入推し) にリンク。")


    db.commit() 
    print("\n✅ 初期データ投入が完了しました。")


if __name__ == "__main__":
    db = Session(bind=engine)
    
    # 💡 最初にパスワードハッシュ化関数が app.utils.security に存在することを確認してください
    if 'get_password_hash' not in locals():
        print("\n🚨 エラー: パスワードハッシュ化関数 (get_password_hash) が見つかりません。")
        print("   utils/security.py が存在し、この関数が定義されていることを確認してください。")
        sys.exit(1)
        
    try:
            create_initial_data(db)
    except Exception as e:
        db.rollback()
        print(f"\n❌ エラーが発生しました: {e}")
    finally:
        db.close()