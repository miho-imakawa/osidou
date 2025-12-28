import sqlite3
from fastapi import APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Tuple, Dict, Any
import re
import os

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user

router = APIRouter() 

# --------------------------------------------------
# 💡 地域マスタ DB 接続設定 (address.db)
# --------------------------------------------------

# BASE_DIR は、logics/notifications.py の親ディレクトリ (app/) からさらに親ディレクトリ (プロジェクトルート) へ
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "address.db")
ADDRESS_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "address.db")

def get_region_db_conn():
    """address.db への接続を返すヘルパー関数"""
    if not os.path.exists(DB_PATH):
        print(f"警告: 地域マスタDBが見つかりません: {DB_PATH}")
        return None
    try:
        return sqlite3.connect(DB_PATH)
    except sqlite3.Error as e:
        print(f"SQLite接続エラー: {e}")
        return None


# --------------------------------------------------
# 地域タグ解析 (JSONからDB検索へ変更)
# --------------------------------------------------

def parse_region_tag(content: str) -> Optional[Dict[str, str]]:
    """
    投稿内容から地域タグを解析し、DBを参照して正式な都道府県と市区町村を返す。
    返り値: {"prefecture": "東京都", "city": "渋谷区"} または None
    """
    conn = get_region_db_conn()
    if conn is None:
        return None

    # ブラケット [] または ダブルクォート "" の中の文字列を抽出
    matches = re.findall(r'\[([^\]]+)\]|\"([^\"]+)\"', content)
    if not matches:
        conn.close()
        return None

    # タプル (match1, match2) から値が入っている方を取得
    extracted_keywords = [m[0] if m[0] else m[1] for m in matches]
    
    cursor = conn.cursor()
    
    for keyword in extracted_keywords:
        # Synonymsテーブルからキーワードを検索し、対応する都道府県と市区町村を取得
        sql = """
            SELECT p.name AS prefecture, c.name AS city
            FROM synonyms s
            JOIN cities c ON s.city_id = c.id
            JOIN prefectures p ON c.prefecture_id = p.id
            WHERE s.synonym = ?
            LIMIT 1
        """
        try:
            cursor.execute(sql, (keyword,))
            row = cursor.fetchone()
        except sqlite3.Error as e:
            print(f"地域DBクエリ実行エラー: {e}")
            conn.close()
            return None
        
        if row:
            conn.close()
            return {"prefecture": row[0], "city": row[1]}

    conn.close()
    return None

# --------------------------------------------------
# 💡 【新規実装】多層ツリー通知ロジック (notify_ancestors)
# --------------------------------------------------

def get_ancestor_category_ids(db: Session, category_id: int) -> List[int]:
    """
    指定されたカテゴリIDの親カテゴリと祖先カテゴリのIDを再帰的に取得する。
    """
    ancestor_ids = []
    current_id = category_id
    
    while current_id is not None:
        # カテゴリを取得
        category = db.query(models.HobbyCategory).filter(
            models.HobbyCategory.id == current_id
        ).first()
        
        if category and category.parent_id is not None:
            ancestor_ids.append(category.parent_id)
            current_id = category.parent_id
        else:
            current_id = None # 親がいなければ終了
            
    return ancestor_ids

def notify_ancestors(
    post_id: int, 
    user_id: int, 
    db: Session, 
    nickname: str, 
    content: str
):
    """
    投稿が作成された際、そのカテゴリとすべての祖先カテゴリのフォロワーに通知を作成する。
    """
    post = db.query(models.HobbyPost).filter(models.HobbyPost.id == post_id).first()
    if not post:
        return
    
    category_id = post.hobby_category_id
    
    # 1. 自身と祖先カテゴリIDのリストを取得
    # 投稿先のカテゴリIDも通知対象とする
    target_category_ids = [category_id] + get_ancestor_category_ids(db, category_id)
    
    # 2. 対象カテゴリをフォローしているユーザーを全て取得
    # 💡 修正点: CategoryFollowerテーブルを利用してユーザーIDを取得
    follower_ids = db.query(
        models.CategoryFollower.user_id
    ).filter(
        models.CategoryFollower.hobby_category_id.in_(target_category_ids),
        models.CategoryFollower.user_id != user_id # 投稿者自身は除く
    ).distinct().all()
    
    new_notifications = []
    
    for follower_id_tuple in follower_ids:
        follower_id = follower_id_tuple[0]
        
        # 投稿カテゴリ名を取得 (post.hobby_category はリレーションとして存在すると想定)
        category_name = db.query(models.HobbyCategory.name).filter(
            models.HobbyCategory.id == category_id
        ).scalar() or "Unknown"

        title = f"【新着投稿】{category_name} に {nickname} さんが投稿しました！"
        # 内容は最初の50文字程度を抜粋
        message_content = content[:50] + ("..." if len(content) > 50 else "")
        content_msg = f"内容: {message_content}"

        new_notifications.append(models.Notification(
            user_id=follower_id,
            title=title,
            message=content_msg,
            post_id=post.id
        ))

    db.add_all(new_notifications)
    db.commit()


# --------------------------------------------------
# 💡 【新規実装】Town 人数チェックロジック (check_town_member_limit)
# --------------------------------------------------

def check_town_member_limit(category_ids: List[int], db: Session):
    """
    指定されたカテゴリIDに対応するTownのメンバー数をチェックし、
    上限を超えている、または超えそうな場合に管理者へ通知する。
    """
    for category_id in category_ids:
        # 1. Town 情報を取得
        town = db.query(models.Town).filter(
            models.Town.hobby_category_id == category_id
        ).first()

        if not town or not town.member_limit:
            continue

        # 2. 現在のメンバー数をカウント
        current_members = db.query(func.count(models.UserTown.user_id)).filter(
            models.UserTown.town_id == town.id
        ).scalar() or 0

        limit = town.member_limit
        
        # 3. チェックロジック
        
        # 閾値: 例として、上限の90%
        threshold = limit * 0.9

        if current_members >= limit:
            # 上限超過
            title = f"⚠️ Town上限超過警告: {town.name}"
            message = f"Town [{town.name}] のメンバー数が上限 ({limit}名) に達しました ({current_members}名)。"
        elif current_members >= threshold:
            # 警告 (90%以上)
            title = f"📈 Town人数警告: {town.name}"
            message = f"Town [{town.name}] のメンバー数が上限の90% ({int(threshold)}名) を超えました ({current_members}名)。"
        else:
            continue # 問題なければ通知しない
            
        # 4. 管理者/特定のユーザーに通知 (ここでは仮に Admin ID=1 に通知)
        admin_id = 1 
        
        # 既に同じ警告が最近発行されていないか確認するロジックを入れても良いが、ここでは単純に通知を作成
        notification = models.Notification(
            user_id=admin_id,
            title=title,
            message=message,
            town_id=town.id # Town IDを通知に関連付ける
        )
        db.add(notification)
        
    db.commit()

# --------------------------------------------------
# 通知ロジック（地域通知の作成）- DB連携に対応
# --------------------------------------------------

def create_region_notifications_for_post(db: Session, post: models.HobbyPost):
    """
    投稿内容を解析し、地域タグが含まれるMeetup投稿の場合、
    同じカテゴリかつ同じ地域のユーザーに通知を作成する。
    """
    if not post.is_meetup:
        return

    # DB参照による地域情報（都道府県/市区町村）の取得
    region_info = parse_region_tag(post.content) 
    if not region_info:
        return

    target_pref = region_info['prefecture']
    target_city = region_info['city']

    # 1. カテゴリを取得 (通知メッセージ用)
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == post.hobby_category_id
    ).first()
    if not category:
        return

    # 2. 解析された地域名に一致し、かつ同じカテゴリをフォローしているユーザーを抽出
    # 💡 修正点: HobbyGroup -> HobbyCategory に変更し、UserHobbyLink -> CategoryFollower を利用すると想定
    query = db.query(models.User).join(models.CategoryFollower).filter(
        models.CategoryFollower.hobby_category_id == post.hobby_category_id
    )

    # 3. ユーザーの登録地域が、タグの指す地域と一致する場合に絞り込む
    region_filter = (
        (models.User.prefecture == target_pref) | 
        (models.User.city == target_city)
    )
    query = query.filter(region_filter)

    target_users = query.all()

    new_notifications = []

    for user in target_users:
        if user.id == post.user_id:
            continue

        # 通知メッセージは、市区町村名を優先して使用
        region_display = target_city if target_city else target_pref
        title = f"【Meetup開催】{region_display} 付近でイベントが投稿されました！"
        # 💡 修正点: post.hobby_group.name -> category.name に変更
        content = f"{category.name} で地域Meetupが作成されました。"

        new_notifications.append(models.Notification(
            user_id=user.id,
            title=title,
            message=content,
            post_id=post.id
        ))

    db.add_all(new_notifications)
    db.commit()
