# app/routers/moods.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
import time
from .. import models
from ..database import get_db
from .auth import get_current_user

_following_moods_cache: dict = {}
MOOD_CACHE_TTL = 30  # 30秒

router = APIRouter()

# ==========================================
# 💡 Mood Log用スキーマ（このファイル内で定義）
# ==========================================

class MoodLogCreate(BaseModel):
    """気分ログ作成"""
    mood_type: str
    comment: Optional[str] = None
    is_visible: bool = True
    created_at: Optional[datetime] = None  # ★フロントから過去時刻を受け取れるように追加

class MoodLogResponse(BaseModel):
    id: int
    user_id: int
    mood_type: str
    comment: Optional[str]
    is_visible: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserMoodResponse(BaseModel):
    """ユーザーの現在の気分"""
    user_id: int
    nickname: Optional[str]
    current_mood: str
    current_mood_comment: Optional[str]
    mood_updated_at: Optional[datetime]
    is_mood_visible: bool
    is_muted: bool = False             # ← 追加
    friend_note: Optional[str] = None 

# ==========================================
# 💡 気分ログの作成（アプリ起動時など）
# ==========================================

@router.post("/moods", response_model=MoodLogResponse, tags=["moods"])
def create_mood_log(
    mood: MoodLogCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # バリデーション
    valid_moods = ["happy", "excited", "calm", "tired", "sad", "anxious", "angry", "neutral", "grateful", "motivated"]
    if mood.mood_type not in valid_moods:
        raise HTTPException(status_code=400, detail="無効な気分タイプです")

    # ★ プランA：時刻のハンドリング
    # フロントから送られてきた created_at があればそれを使用、なければ現在のサーバー時刻。
    post_time = mood.created_at if mood.created_at else datetime.now(timezone.utc)

    # 1. 新しいログレコードを作成
    db_mood = models.MoodLog(
        user_id=current_user.id,
        mood_type=mood.mood_type,
        comment=mood.comment,
        is_visible=mood.is_visible,
        created_at=post_time  # ★ 確定した時刻（過去または現在）を注入
    )
    db.add(db_mood)

    # 2. ユーザーテーブルの「現在の状態」を更新
    current_user.current_mood = mood.mood_type
    current_user.current_mood_comment = mood.comment
    current_user.mood_updated_at = post_time  # ★ ユーザーの最新更新時刻も合わせる
    current_user.is_mood_visible = mood.is_visible

    try:
        db.commit()
        db.refresh(db_mood)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"保存に失敗しました: {str(e)}")

    # 古いログの削除（既存ロジック）
    try:
        cleanup_old_mood_logs(db, current_user.id)
    except:
        pass

    return db_mood

# ==========================================
# 💡 自分の気分ログ履歴を取得
# ==========================================

@router.get("/moods/my-logs", response_model=List[MoodLogResponse], tags=["moods"])
def get_my_mood_logs(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """自分の気分ログ履歴を取得（最新順）"""
    logs = db.query(models.MoodLog).filter(
        models.MoodLog.user_id == current_user.id
    ).order_by(models.MoodLog.created_at.desc()).offset(offset).limit(limit).all()
    
    return logs

# # ==========================================
# # 💡 他のユーザーの現在の気分を取得
# # ==========================================

# @router.get("/moods/user/{user_id}", response_model=UserMoodResponse, tags=["moods"])
# def get_user_current_mood(
#     user_id: int,
#     db: Session = Depends(get_db)
# ):
#     """他のユーザーの現在の気分を取得（プロフィール表示用）"""
#     user = db.query(models.User).filter(models.User.id == user_id).first()
#     if not user:
#         raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    
#     # 非公開設定の場合は表示しない
#     if not user.is_mood_visible:
#         return UserMoodResponse(
#             user_id=user.id,
#             nickname=user.nickname,
#             current_mood="neutral",
#             current_mood_comment=None,
#             mood_updated_at=None,
#             is_mood_visible=False
#         )
    
#     return UserMoodResponse(
#         user_id=user.id,
#         nickname=user.nickname,
#         current_mood=user.current_mood,
#         current_mood_comment=user.current_mood_comment,
#         mood_updated_at=user.mood_updated_at,
#         is_mood_visible=user.is_mood_visible
#     )

# ==========================================
# 💡 他のユーザーの気分ログ履歴（公開のみ）
# ==========================================

@router.get("/moods/user/{user_id}/logs", response_model=List[MoodLogResponse], tags=["moods"])
def get_user_mood_logs(
    user_id: int,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """他のユーザーの気分ログ履歴を取得（公開設定のもののみ）"""
    logs = db.query(models.MoodLog).filter(
        models.MoodLog.user_id == user_id,
        models.MoodLog.is_visible == True  # 公開のみ
    ).order_by(models.MoodLog.created_at.desc()).limit(limit).all()
    
    return logs

# ==========================================
# 💡 気分ログの公開/非公開設定変更
# ==========================================

@router.patch("/moods/visibility", tags=["moods"])
def update_mood_visibility(
    is_visible: bool,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """気分表示の公開/非公開を切り替える"""
    current_user.is_mood_visible = is_visible
    db.commit()
    
    return {
        "message": f"気分表示を{'公開'if is_visible else '非公開'}に設定しました",
        "is_visible": is_visible
    }

# ==========================================
# 💡 過去ログの自動削除（軽量化）
# ==========================================

def cleanup_old_mood_logs(db: Session, user_id: int):
    """
    3ヶ月以上前のログ、または1000件を超えるログを自動削除
    ※ DB負荷を抑えるための軽量化施策
    """
    # 3ヶ月弱前の日時
    three_months_ago = datetime.now(timezone.utc) - timedelta(days=95)
    
    # 3ヶ月弱以上前のログを削除
    db.query(models.MoodLog).filter(
        models.MoodLog.user_id == user_id,
        models.MoodLog.created_at < three_months_ago
    ).delete()
    
    # 1200件を超える古いログを削除
    total_logs = db.query(func.count(models.MoodLog.id)).filter(
        models.MoodLog.user_id == user_id
    ).scalar()
    
    if total_logs > 1200:
        # 最新1000件を残して削除
        logs_to_keep = db.query(models.MoodLog.id).filter(
            models.MoodLog.user_id == user_id
        ).order_by(models.MoodLog.created_at.desc()).limit(1000).subquery()
        
        db.query(models.MoodLog).filter(
            models.MoodLog.user_id == user_id,
            ~models.MoodLog.id.in_(logs_to_keep)
        ).delete(synchronize_session=False)
    
    db.commit()

# ==========================================
# 💡 気分統計（おまけ機能）
# ==========================================

@router.get("/moods/my-stats", tags=["moods"])
def get_my_mood_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """自分の気分ログの統計情報（過去30日間）"""
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    # 各気分タイプの出現回数をカウント
    stats = db.query(
        models.MoodLog.mood_type,
        func.count(models.MoodLog.id).label('count')
    ).filter(
        models.MoodLog.user_id == current_user.id,
        models.MoodLog.created_at >= thirty_days_ago
    ).group_by(models.MoodLog.mood_type).all()
    
    # 辞書形式に変換
    mood_stats = {stat.mood_type: stat.count for stat in stats}
    
    # 最も多い気分
    most_common_mood = max(mood_stats, key=mood_stats.get) if mood_stats else "neutral"
    
    return {
        "period": "過去30日間",
        "mood_counts": mood_stats,
        "most_common_mood": most_common_mood,
        "total_logs": sum(mood_stats.values())
    }

# C:\osidou\backend\app\routers\moods.py の末尾に追加

# ==========================================
# 💡 フォロー中ユーザーの最新気分ログを取得
# ==========================================

# フロントエンドの呼び出しが /users/following/moods であるため、
# ルーターの登録方法によってはパスがずれる可能性があります。
# ここでは、moodsルーター内で最も自然なパスとして /following/moods を使用します。
# ==========================================
# 💡 友達（Friendship）の最新気分ログを取得
# ==========================================

# app/routers/moods.py

@router.get(
    "/following/moods",
    response_model=List[UserMoodResponse],
    tags=["moods"]
)
def get_following_moods(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    承認済みの友達（Friendship）の中で、非表示・更新停止されていないユーザーの最新気分を取得。
    """
    # キャッシュチェック
    cache_key = str(current_user.id)
    now = time.time()
    if cache_key in _following_moods_cache:
        cached_data, cached_time = _following_moods_cache[cache_key]
        if now - cached_time < MOOD_CACHE_TTL and cached_data is not None:
            return cached_data

        # 1. Friendshipテーブルから「友達のID」を取得
    friend_relations = db.query(models.Friendship).filter(
        models.Friendship.user_id == current_user.id,
        models.Friendship.is_hidden == False,
    ).all()

    friend_ids = [rel.friend_id for rel in friend_relations]
    relation_map = {rel.friend_id: rel for rel in friend_relations}

    if not friend_ids:
        return []

    # 2. 友達の最新情報を取得
    friends_with_mood = db.query(models.User).filter(
        models.User.id.in_(friend_ids),
        models.User.is_mood_visible == True
    ).order_by(models.User.mood_updated_at.desc()).all()

    # 3. レスポンス形式に変換
    result = [
        UserMoodResponse(
            user_id=user.id,
            nickname=user.nickname,
            current_mood=user.current_mood,
            current_mood_comment=user.current_mood_comment,
            mood_updated_at=user.mood_updated_at,
            is_mood_visible=user.is_mood_visible,
            is_muted=relation_map[user.id].is_muted,        # ← 追加
            friend_note=relation_map[user.id].friend_note,
        )
        for user in friends_with_mood
    ]

    # キャッシュに保存
    _following_moods_cache[cache_key] = (result, now)

    return result
