import enum
from fastapi import APIRouter, Depends, HTTPException, status, Query 
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user 
from ..utils.security import get_password_hash
from ..schemas import MoodLogResponse, UserPublic

# ▼ 自動グループ作成ロジック
from .community import check_and_create_region_group 

router = APIRouter(tags=["users"])

# --- 型定義 (ここにある必要があります) ---

class UserMoodResponse(BaseModel):
    user_id: int
    nickname: Optional[str] = None
    email: Optional[str] = None
    current_mood: Optional[str] = None
    current_mood_comment: Optional[str] = None
    mood_updated_at: Optional[datetime] = None
    friend_note: Optional[str] = None
    is_mood_comment_visible: Optional[bool] = None
    is_muted: Optional[bool] = None 
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 💡 ユーザー登録 / 自分自身の操作 (認証あり/なし)
# ==========================================

@router.post("/register", response_model=schemas.UserMe)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    try:
        existing = db.query(models.User).filter(models.User.email == user.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="そのメールアドレスは既に登録されています。")

        hashed_password = get_password_hash(user.password) 
        db_user = models.User(
            username=user.username,
            email=user.email,
            nickname=user.nickname,
            hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me", response_model=schemas.UserMe)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=schemas.UserMe)
def update_user_me(user_update: schemas.UserProfileUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "password":
            setattr(current_user, "hashed_password", get_password_hash(value))
        elif hasattr(current_user, key):
            setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/me/mood", response_model=schemas.UserMe)
def update_my_mood(mood_data: schemas.MoodLogCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    new_log = models.MoodLog(user_id=current_user.id, mood_type=mood_data.mood_type, comment=mood_data.comment)
    db.add(new_log)
    current_user.current_mood = mood_data.mood_type
    current_user.current_mood_comment = mood_data.comment
    current_user.mood_updated_at = func.now()
    db.commit()
    db.refresh(current_user)
    return current_user

@router.get("/me/mood-history", response_model=List[schemas.MoodLogResponse])
def get_my_mood_history(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    three_months_ago = datetime.now() - timedelta(days=90)
    return db.query(models.MoodLog).filter(models.MoodLog.user_id == current_user.id, models.MoodLog.created_at >= three_months_ago).order_by(models.MoodLog.created_at.desc()).limit(1000).all()

@router.patch("/me/mood-visibility")
def toggle_mood_visibility(is_visible: bool, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    current_user.is_mood_visible = is_visible
    db.commit()
    return {"message": "設定を更新しました"}

@router.patch("/me/mood-comment-visibility")
def toggle_mood_comment_visibility(is_visible: bool, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    current_user.is_mood_comment_visible = is_visible
    db.commit()
    return {"message": "設定を更新しました"}

@router.get("/me/notifications", response_model=List[schemas.NotificationResponse])
def read_my_notifications(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user), limit: int = 20, offset: int = 0):
    return db.query(models.Notification).filter(models.Notification.recipient_id == current_user.id).order_by(desc(models.Notification.created_at)).offset(offset).limit(limit).all()

@router.get("/search", response_model=List[schemas.UserPublic])
def search_users(query: str = Query(..., min_length=1), db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    search_pattern = f"%{query}%"
    return db.query(models.User).filter(models.User.id != current_user.id, or_(models.User.nickname.ilike(search_pattern), models.User.username.ilike(search_pattern))).limit(20).all()

@router.get("/following/moods", response_model=List[UserMoodResponse])
def get_following_moods(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # --- (前段の friendships 取得ロジックはそのまま) ---
    friendships = db.query(models.Friendship).filter(
        or_(
            models.Friendship.user_id == current_user.id,
            models.Friendship.friend_id == current_user.id
        )
    ).all()

    if not friendships:
        return []

    friend_ids = [f.friend_id if f.user_id == current_user.id else f.user_id for f in friendships]

    users = db.query(models.User).filter(
        models.User.id.in_(friend_ids),
        models.User.is_mood_visible == True
    ).all()

# friendshipをuser_idで引けるようにマップ化
    friendship_map = {}
    for f in friendships:
        if f.user_id == current_user.id:
            # 自分がuser_id側 → is_mutedは自分の設定
            friendship_map[f.friend_id] = f
        # friend_id側のレコードはis_mutedを使わない

    moods = []
    for user in users:
        fs = friendship_map.get(user.id)
        moods.append({
            "user_id": user.id,
            "nickname": user.nickname,
            "username": user.username,
            "email": user.email,
            "current_mood": user.current_mood,
            "current_mood_comment": user.current_mood_comment,
            "mood_updated_at": user.mood_updated_at,
            "is_mood_comment_visible": user.is_mood_comment_visible,
            "friend_note": fs.friend_note if fs else None,
            "is_muted": fs.is_muted if (fs and fs.user_id == current_user.id) else False,
        })
    return moods

# ==========================================
# 💡 ID指定の操作 (末尾に置く)
# ==========================================

@router.get("/", response_model=List[schemas.UserPublic])
def read_users(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.User).all()

@router.get("/{user_id}", response_model=schemas.UserPublic)
def read_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    return user

@router.get("/{user_id}/mood-history", response_model=List[schemas.MoodLogResponse])
def get_user_mood_history(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user: raise HTTPException(status_code=404, detail="見つかりません")
    if current_user.id != target_user.id and not target_user.is_mood_visible:
        raise HTTPException(status_code=403, detail="権限がありません")
    three_months_ago = datetime.now() - timedelta(days=90)
    return db.query(models.MoodLog).filter(models.MoodLog.user_id == user_id, models.MoodLog.created_at >= three_months_ago).order_by(models.MoodLog.created_at.desc()).limit(1000).all()

@router.post("/{user_id}/follow")
def follow_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.id == user_id: raise HTTPException(status_code=400)
    existing = db.query(models.Follow).filter(models.Follow.follower_id == current_user.id, models.Follow.following_id == user_id).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"status": "unfollowed"}
    new_follow = models.Follow(follower_id=current_user.id, following_id=user_id)
    db.add(new_follow)
    db.commit()
    return {"status": "followed"}

@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)
    if user.id != current_user.id: raise HTTPException(status_code=403)
    db.delete(user)
    db.commit()
    return

