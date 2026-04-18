import enum
from fastapi import APIRouter, Depends, HTTPException, status, Query 
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, BaseModel as PydanticBase, ConfigDict

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user 
from ..utils.security import get_password_hash
from ..schemas import MoodLogResponse, UserPublic

# ▼ 自動グループ作成ロジック
from .community import check_and_create_region_group 

router = APIRouter(tags=["users"])

# --- 型定義 (ここにある必要があります) ---

class MoodLogCreateWithCategory(PydanticBase):
    mood_type:  str
    comment:    Optional[str] = None
    category:   Optional[str] = None
    is_visible: bool = True

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
def update_my_mood(
    mood_data: MoodLogCreateWithCategory,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    new_log = models.MoodLog(
        user_id   = current_user.id,
        mood_type = mood_data.mood_type,
        comment   = mood_data.comment,
        category  = mood_data.category,   # ← NEW
    )
    db.add(new_log)
    current_user.current_mood         = mood_data.mood_type
    current_user.current_mood_comment = mood_data.comment
    current_user.mood_updated_at      = func.now()
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

@router.get("/me/notifications", response_model=List[schemas.NotificationResponse])
def read_my_notifications(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user), limit: int = 20, offset: int = 0):
    return db.query(models.Notification).filter(models.Notification.recipient_id == current_user.id).order_by(desc(models.Notification.created_at)).offset(offset).limit(limit).all()

@router.get("/search", response_model=List[schemas.UserPublic])
def search_users(query: str = Query(..., min_length=1), db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    search_pattern = f"%{query}%"
    return db.query(models.User).filter(models.User.id != current_user.id, or_(models.User.nickname.ilike(search_pattern), models.User.username.ilike(search_pattern))).limit(20).all()

class UserTagCreate(PydanticBase):
    label:      str
    color:      str = "gray"
    sort_order: int = 0

class UserTagResponse(PydanticBase):
    id:         int
    label:      str
    color:      str
    sort_order: int
    class Config:
        from_attributes = True

@router.get("/me/tags", response_model=List[UserTagResponse])
def get_my_tags(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return (
        db.query(models.UserTag)
        .filter(models.UserTag.user_id == current_user.id)
        .order_by(models.UserTag.sort_order, models.UserTag.id)
        .all()
    )


@router.post("/me/tags", response_model=UserTagResponse, status_code=201)
def create_my_tag(
    tag: UserTagCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    count = db.query(models.UserTag).filter(
        models.UserTag.user_id == current_user.id
    ).count()
    if count >= 10:
        raise HTTPException(status_code=400, detail="タグは最大10件まで登録できます。")
    new_tag = models.UserTag(
        user_id    = current_user.id,
        label      = tag.label.strip(),
        color      = tag.color,
        sort_order = tag.sort_order,
    )
    db.add(new_tag)
    try:
        db.commit()
        db.refresh(new_tag)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="同じ名前のタグが既に存在します。")
    return new_tag


@router.put("/me/tags/{tag_id}", response_model=UserTagResponse)
def update_my_tag(
    tag_id: int,
    tag: UserTagCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_tag = db.query(models.UserTag).filter(
        models.UserTag.id      == tag_id,
        models.UserTag.user_id == current_user.id
    ).first()
    if not db_tag:
        raise HTTPException(status_code=404, detail="タグが見つかりません。")
    db_tag.label      = tag.label.strip()
    db_tag.color      = tag.color
    db_tag.sort_order = tag.sort_order
    db.commit()
    db.refresh(db_tag)
    return db_tag


@router.delete("/me/tags/{tag_id}", status_code=204)
def delete_my_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_tag = db.query(models.UserTag).filter(
        models.UserTag.id      == tag_id,
        models.UserTag.user_id == current_user.id
    ).first()
    if not db_tag:
        raise HTTPException(status_code=404, detail="タグが見つかりません。")
    db.delete(db_tag)
    db.commit()

@router.get("/following/moods", response_model=List[UserMoodResponse])
def get_following_moods(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # 1. 自分が登録している友達関係を取得
    friendships = db.query(models.Friendship).filter(
        models.Friendship.user_id == current_user.id,
    ).all()

    # 友達がいない場合は、即座に空のリストを返す（Noneを返すとエラーになります）
    if not friendships:
        return []

    friend_ids = [f.friend_id for f in friendships]
    friendship_map = {f.friend_id: f for f in friendships}

    # 2. 全体公開設定がONのユーザーのみ取得
    users = db.query(models.User).filter(
        models.User.id.in_(friend_ids),
        models.User.is_mood_visible == True
    ).all()

    # 3. 返却用のリストを作成
    results = []
    for user in users:
        fs = friendship_map.get(user.id)

        # 【送り手優先】コメント非公開設定ならコメントをNoneにする
        is_comment_ok = getattr(user, "is_mood_comment_visible", True)
        final_comment = user.current_mood_comment if is_comment_ok else None

        results.append({
            "user_id": user.id,
            "nickname": user.nickname,
            "username": user.username,
            "email": user.email,
            "current_mood": user.current_mood,
            "current_mood_comment": final_comment,
            "mood_updated_at": user.mood_updated_at,
            "is_mood_comment_visible": bool(is_comment_ok),
            "friend_note": fs.friend_note if fs else None,
            "is_muted": bool(fs.is_muted) if fs else False,
        })
    
    # 4. 最後に必ずリスト（results）を返す
    return results

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


