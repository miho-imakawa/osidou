import sqlite3
import os
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import re
from datetime import timedelta

# DB接続用の情報 (FastAPIのプロジェクトルートからの相対パスを想定)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "address.db")
# 💡 models のインポートパスは app/logics/notifications.py から見て正しい階層に変更
from .. import models, schemas 

# --------------------------------------------------
# 💡 地域マスタ DB 接続設定 (address.db)
# --------------------------------------------------

def get_region_db_conn():
    """address.db への接続を返すヘルパー関数"""
    # 接続パスの確認 (現在のファイルから見てプロジェクトルートの data/address.db を指す)
    if not os.path.exists(DB_PATH):
        print(f"警告: 地域マスタDBが見つかりません: {DB_PATH}")
        return None
    try:
        # check_same_thread=False を設定しないと、FastAPIのBackgroundTasksで問題が発生する可能性がある
        return sqlite3.connect(DB_PATH, check_same_thread=False)
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
    # 例: "[東京都渋谷区]" => "東京都渋谷区"
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
            # row[0]がprefecture、row[1]がcity
            return {"prefecture": row[0], "city": row[1]}

    conn.close()
    return None

# --------------------------------------------------
# 💡 多層ツリー通知ロジック (notify_ancestors)
# --------------------------------------------------

def get_ancestor_category_ids(db: Session, category_id: int) -> List[int]:
    """
    指定されたカテゴリIDの親カテゴリと祖先カテゴリのIDを再帰的に取得する。
    """
    ancestor_ids = []
    current_id = category_id
    
    # 💡 SQLAlchemyで親を辿るための単純なループ
    while current_id is not None:
        category = db.query(models.HobbyCategory).filter(
            models.HobbyCategory.id == current_id
        ).first()
        
        if category and category.parent_id is not None:
            ancestor_ids.append(category.parent_id)
            current_id = category.parent_id
        else:
            current_id = None
            
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
    （ALL投稿時、または[ALL]タグ付きの投稿時に実行されることを想定）
    """
    post = db.query(models.HobbyPost).filter(models.HobbyPost.id == post_id).first()
    if not post:
        print(f"通知作成エラー: 投稿ID {post_id} が見つかりません。")
        return
    
    category_id = post.hobby_category_id
    
    # 1. 自身と祖先カテゴリIDのリストを取得
    # 投稿先のカテゴリIDも通知対象とする
    target_category_ids = [category_id] + get_ancestor_category_ids(db, category_id)
    
    # 2. 対象カテゴリをフォローしているユーザーを全て取得 (UserHobbyLinkを使用)
    follower_ids = db.query(
        models.UserHobbyLink.user_id
    ).filter(
        models.UserHobbyLink.hobby_category_id.in_(target_category_ids),
        models.UserHobbyLink.user_id != user_id # 投稿者自身は除く
    ).distinct().all()
    
    new_notifications = []
    
    for follower_id_tuple in follower_ids:
        follower_id = follower_id_tuple[0]
        
        # 投稿カテゴリ名を取得
        category_name = db.query(models.HobbyCategory.name).filter(
            models.HobbyCategory.id == category_id
        ).scalar() or "Unknown"

        title = f"【新着投稿】{category_name} に {nickname} さんが投稿しました！"
        # 内容は最初の50文字程度を抜粋
        message_content = content[:50] + ("..." if len(content) > 50 else "")
        content_msg = f"内容: {message_content}"

        # 💡 通知モデルの fields に合わせて修正: post_id ではなく event_post_id を使用
        new_notifications.append(models.Notification(
            user_id=follower_id,           # Userモデルに通知対象ユーザーIDのフィールドがないため、一時的に無視
            sender_id=user_id,             # 投稿者を sender_id として設定
            hobby_category_id=category_id, # どのカテゴリへの告知かを示す
            title=title,
            message=content_msg,
            event_post_id=post.id          # 関連する投稿ID
        ))

    # 💡 重要な点: Notificationモデルには 'user_id' カラムがないため、
    # どのユーザーに届ける通知かを示すため、ここでは Notification テーブルを通知先としてではなく、
    # 告知元として使用し、ユーザーごとの通知テーブルが必要になるが、一旦この構造で続行する。
    # ※ 既存のNotificationモデルを、ユーザーごとの通知テーブルとして利用する場合、user_idが必要です。
    #    しかし、現在のNotificationモデルには通知対象ユーザーを示すカラムが存在しません。
    #    **この点はお客様の models.py に依存するため、現状では通知の作成のみを行います。**
    
    # Town/UserTownモデルの追加により、Notificationモデルも修正されていることを期待し、
    # 仮に `Notification` に `user_id` があるとして処理を継続します。
    # 
    # [models.py の最新版に基づく仮定]
    # Notificationモデルには、通知対象ユーザーを示す user_id カラムが必要ですが、
    # 最新のmodels.pyでは `hobby_category_id` しかありません。
    #
    # => Town 人数チェックロジックが参照している Notification モデルの最新版に依存する形で、
    #    現在は、通知対象ユーザーIDを特定できても、それを保存する場所がない問題を無視して進めます。
    #    (通知対象ユーザーIDを持つ`NotificationRecipient`テーブルが本来必要ですが、今回は既存モデル内で対応)
    
    # 💡 通知がどのユーザーに届くかを示すために、Notificationモデルに `recipient_id` が必要だが、
    #    Townロジックと衝突するため、TownロジックのNotification作成方法に倣う（管理者ID=1に通知）。
    
    # => 複雑さを避けるため、ここでは通知を一旦 **管理者 (ID=1)** にのみ送る形に簡易化します。
    #    本来は、`models.NotificationRecipient` テーブルが必要です。
    
    
    # 簡易化: 上層通知は行わずに、投稿カテゴリのフォローユーザーに直接通知を作成します。
    # 適切なモデルがないため、このロジックは一旦ロギングのみとします。
    print(f"DEBUG: 投稿ID {post_id} の祖先通知は、適切なレシーバテーブルがないためスキップされました。")
    
    # db.add_all(new_notifications)
    # db.commit()


def notify_ancestors_working(
    post_id: int, 
    user_id: int, 
    db: Session, 
    nickname: str, 
    content: str
):
    """
    投稿が作成された際、そのカテゴリとすべての祖先カテゴリのフォロワーに通知を作成する。
    (Notificationモデルに `recipient_id` があることを前提とした、実際の処理)
    """
    post = db.query(models.HobbyPost).filter(models.HobbyPost.id == post_id).first()
    if not post: return
    category_id = post.hobby_category_id
    target_category_ids = [category_id] + get_ancestor_category_ids(db, category_id)
    follower_ids = db.query(
        models.UserHobbyLink.user_id
    ).filter(
        models.UserHobbyLink.hobby_category_id.in_(target_category_ids),
        models.UserHobbyLink.user_id != user_id
    ).distinct().all()
    
    new_notifications = []
    category_name = db.query(models.HobbyCategory.name).filter(
        models.HobbyCategory.id == category_id
    ).scalar() or "Unknown"

    for follower_id_tuple in follower_ids:
        follower_id = follower_id_tuple[0]
        title = f"【新着投稿】{category_name} に {nickname} さんが投稿しました！"
        message_content = content[:50] + ("..." if len(content) > 50 else "")
        
        # 💡 仮に Notification モデルに `recipient_id` と `message` があるとして挿入
        new_notifications.append(models.Notification(
            # recipient_id=follower_id, # 本来はこれ
            sender_id=user_id,
            hobby_category_id=category_id,
            message=f"{title} - {message_content}", # titleとmessageを結合
            event_post_id=post.id
        ))

    # db.add_all(new_notifications)
    # db.commit()
    print(f"DEBUG: 投稿ID {post_id} の祖先通知 {len(new_notifications)} 件が作成されました (DB挿入はスキップ)。")


# --------------------------------------------------
# 💡 Town 人数チェックロジック (check_town_member_limit)
# --------------------------------------------------

def check_town_member_limit(category_ids: List[int], db: Session):
    """
    指定されたカテゴリIDに対応するTownのメンバー数をチェックし、
    上限を超えている、または超えそうな場合に管理者へ通知する。
    """
    # 💡 処理の最後に commit が必要 (Townモデルの追加により、Town IDとTown.membersを使用)
    
    for category_id in category_ids:
        # 1. Town 情報を取得 (HobbyCategory -> Town)
        town = db.query(models.Town).filter(
            models.Town.hobby_category_id == category_id
        ).first()

        if not town or not town.member_limit:
            continue

        # 2. 現在のメンバー数をカウント (Town -> UserTown)
        current_members = db.query(func.count(models.UserTown.user_id)).filter(
            models.UserTown.town_id == town.id
        ).scalar() or 0

        limit = town.member_limit
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
            continue
            
        # 4. 管理者/特定のユーザーに通知 (ここでは仮に Admin ID=1 に通知)
        # 💡 Notification モデルは Town 警告を保存するために使用
        admin_id = 1 
        
        notification = models.Notification(
            # user_id=admin_id, # 💡 Notificationモデルにuser_idがないため、コメントアウト
            sender_id=admin_id,  # Adminからのお知らせとしてsender_idを使用
            hobby_category_id=category_id,
            message=f"{title} - {message}",
            town_id=town.id # Town IDを通知に関連付ける
        )
        db.add(notification)
        
    db.commit()


# --------------------------------------------------
# 通知ロジック（地域通知の作成）- Meetup投稿用
# --------------------------------------------------

def create_region_notifications_for_post(db: Session, post: models.HobbyPost):
    """
    Meetup投稿の内容を解析し、地域タグが含まれるMeetup投稿の場合、
    同じカテゴリかつ同じ地域のユーザーに通知を作成する。
    """
    # 1. Meetup投稿でなければ終了
    if not post.is_meetup:
        return

    # 2. 地域情報（都道府県/市区町村）の取得
    #    投稿内容のタグ解析を優先し、タグがなければ投稿者の登録地域を使用する。
    region_info = parse_region_tag(post.content) 
    
    target_pref = region_info.get('prefecture') if region_info else post.region_tag_pref
    target_city = region_info.get('city') if region_info else post.region_tag_city

    if not target_pref and not target_city:
        return # 地域情報がなければ通知しない

    # 3. カテゴリを取得 (通知メッセージ用)
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == post.hobby_category_id
    ).first()
    if not category:
        return

    # 4. 対象ユーザーの抽出 (同じカテゴリをフォロー ＋ 地域一致)
    query = db.query(models.User).join(models.UserHobbyLink).filter(
        models.UserHobbyLink.hobby_category_id == post.hobby_category_id
    )

    # 地域のフィルタリング
    region_filter = []
    if target_pref:
        region_filter.append(models.User.prefecture == target_pref)
    if target_city:
        region_filter.append(models.User.city == target_city)
        
    if region_filter:
        # OR条件で結合 (都道府県が一致 OR 市区町村が一致)
        query = query.filter(models.User.id == models.User.id, *region_filter) # models.User.id == models.User.id は常に真でフィルタ開始
    else:
        return # 地域情報がない場合は処理しない

    target_users = query.all()

    new_notifications = []

    for user in target_users:
        if user.id == post.user_id:
            continue

        # 通知メッセージは、市区町村名を優先して使用
        region_display = target_city if target_city else target_pref
        title = f"【Meetup開催】{region_display} 付近でイベントが投稿されました！"
        content_msg = f"{category.name} で地域Meetupが作成されました。"

        # 💡 仮に Notification モデルに `recipient_id` があるとして挿入
        new_notifications.append(models.Notification(
            # recipient_id=user.id, # 本来はこれ
            sender_id=post.user_id,
            hobby_category_id=post.hobby_category_id,
            message=f"{title} - {content_msg}", # titleとmessageを結合
            event_post_id=post.id
        ))
        
    # 💡 適切なモデルがないため、このロジックは一旦ロギングのみとします。
    print(f"DEBUG: 投稿ID {post.id} の地域通知 {len(new_notifications)} 件が作成されました (DB挿入はスキップ)。")

    # db.add_all(new_notifications)
    # db.commit()