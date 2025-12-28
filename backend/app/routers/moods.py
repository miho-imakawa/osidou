# app/routers/moods.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from .. import models
from ..database import get_db
from .auth import get_current_user

router = APIRouter()

# ==========================================
# 💡 Mood Log用スキーマ（このファイル内で定義）
# ==========================================

class MoodLogCreate(BaseModel):
    """気分ログ作成"""
    mood_type: str  # "happy", "excited", "calm", "tired", "sad", "anxious", "angry", "neutral", "grateful", "motivated"
    comment: Optional[str] = None  # ひとことコメント（200文字以内）
    is_visible: bool = True  # 公開設定

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

    # 1. 新しいログレコードを作成
    db_mood = models.MoodLog(
        user_id=current_user.id,
        mood_type=mood.mood_type,
        comment=mood.comment,
        is_visible=mood.is_visible,
        created_at=datetime.now() # ここを明示
    )
    db.add(db_mood)

    # 2. ユーザーテーブルの「現在の状態」を更新
    current_user.current_mood = mood.mood_type
    current_user.current_mood_comment = mood.comment
    current_user.mood_updated_at = datetime.now()
    current_user.is_mood_visible = mood.is_visible

    try:
        db.commit()
        db.refresh(db_mood)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"保存に失敗しました: {str(e)}")

    # 古いログの削除（バックグラウンドで動くので失敗しても無視してOK）
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

# ==========================================
# 💡 他のユーザーの現在の気分を取得
# ==========================================

@router.get("/moods/user/{user_id}", response_model=UserMoodResponse, tags=["moods"])
def get_user_current_mood(
    user_id: int,
    db: Session = Depends(get_db)
):
    """他のユーザーの現在の気分を取得（プロフィール表示用）"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    
    # 非公開設定の場合は表示しない
    if not user.is_mood_visible:
        return UserMoodResponse(
            user_id=user.id,
            nickname=user.nickname,
            current_mood="neutral",
            current_mood_comment=None,
            mood_updated_at=None,
            is_mood_visible=False
        )
    
    return UserMoodResponse(
        user_id=user.id,
        nickname=user.nickname,
        current_mood=user.current_mood,
        current_mood_comment=user.current_mood_comment,
        mood_updated_at=user.mood_updated_at,
        is_mood_visible=user.is_mood_visible
    )

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
    # 3ヶ月前の日時
    three_months_ago = datetime.now() - timedelta(days=90)
    
    # 3ヶ月以上前のログを削除
    db.query(models.MoodLog).filter(
        models.MoodLog.user_id == user_id,
        models.MoodLog.created_at < three_months_ago
    ).delete()
    
    # 1000件を超える古いログを削除
    total_logs = db.query(func.count(models.MoodLog.id)).filter(
        models.MoodLog.user_id == user_id
    ).scalar()
    
    if total_logs > 1000:
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
    # 🔍 デバッグ: 必ず最初に実行される
    print("=" * 50)
    print("[DEBUG] get_following_moods が呼ばれました")
    print(f"[DEBUG] current_user.id: {current_user.id}")
    print(f"[DEBUG] current_user.nickname: {current_user.nickname}")
    print("=" * 50)
    
    # 1. Friendshipテーブルから「友達のID」を取得
    friend_relations = db.query(models.Friendship).filter(
        models.Friendship.user_id == current_user.id,
        models.Friendship.is_hidden == False,
        models.Friendship.is_muted == False
    ).all()

    print(f"[DEBUG] Friendship の数: {len(friend_relations)}")
    
    friend_ids = [rel.friend_id for rel in friend_relations]
    print(f"[DEBUG] 友達のID: {friend_ids}")

    if not friend_ids:
        print("[DEBUG] 友達が見つかりません - 空のリストを返します")
        return []

    # 2. 友達の最新情報を取得
    friends_with_mood = db.query(models.User).filter(
        models.User.id.in_(friend_ids),
        models.User.is_mood_visible == True
    ).order_by(models.User.mood_updated_at.desc()).all()
    
    print(f"[DEBUG] 気分公開中の友達の数: {len(friends_with_mood)}")
    
    for user in friends_with_mood:
        print(f"[DEBUG] - ユーザーID: {user.id}, ニックネーム: {user.nickname}, 気分: {user.current_mood}, 更新: {user.mood_updated_at}")

    # 3. レスポンス形式に変換
    result = [
        UserMoodResponse(
            user_id=user.id,
            nickname=user.nickname,
            current_mood=user.current_mood,
            current_mood_comment=user.current_mood_comment,
            mood_updated_at=user.mood_updated_at,
            is_mood_visible=user.is_mood_visible
        )
        for user in friends_with_mood
    ]
    
    print(f"[DEBUG] 返すデータの数: {len(result)}")
    print("=" * 50)
    
    return result
