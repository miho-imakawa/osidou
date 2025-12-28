# backend/app/routers/users.py
import enum
from fastapi import APIRouter, Depends, HTTPException, status, Query 
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_ # 💡 or_ を追加
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict # 👈 これを追記

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user 
from ..utils.security import get_password_hash
# 💡 追加: 気分ログの型定義（schemas.pyからMoodLogResponseをインポート）
from ..schemas import MoodLogResponse, UserPublic # 💡 UserPublic を追加

# ▼ 自動グループ作成ロジックを読み込み（community.pyが存在することを前提）
from .community import check_and_create_region_group 

router = APIRouter(tags=["users"])

# ==========================================
# 💡 0. ユーザー登録 (認証不要)
# ==========================================

@router.post("/register", response_model=schemas.UserMe, summary="新しいユーザーを登録")
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """新しいユーザーを登録します。"""
    try:
        # 既存ユーザー確認
        existing = db.query(models.User).filter(models.User.email == user.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="そのメールアドレスは既に登録されています。")

        # パスワードをハッシュ化
        hashed_password = get_password_hash(user.password) 
        
        # DBモデルを作成 (UserCreate スキーマのフィールドを使用)
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
        
    except HTTPException as http_e:
        raise http_e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登録時に予期せぬ問題が発生しました: {e}"
        )

# ==========================================
# 💡 1. ユーザー情報取得 (自分) - GET /users/me
# ==========================================

@router.get("/me", response_model=schemas.UserMe, summary="現在のユーザー情報を取得")
def read_users_me(current_user: models.User = Depends(get_current_user)):
    """認証済みのユーザー自身のプロフィール情報を取得します。"""
    return current_user

# ==========================================
# 💡 2. ユーザープロフィール更新 - PUT /users/me
# ==========================================

@router.put("/me", response_model=schemas.UserMe, summary="プロフィール情報を更新") # 💡 GETからPUTに変更
def update_user_me( # 💡 関数名が重複していたので変更
    user_update: schemas.UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    old_prefecture = current_user.prefecture
    old_city = current_user.city

    # 送信されたデータのみを取得
    update_data = user_update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        if key == "password":
            setattr(current_user, "hashed_password", get_password_hash(value))
        else:
            # Userモデルにフィールドが存在する場合のみ更新
            if hasattr(current_user, key):
                setattr(current_user, key, value)

    db.commit()
    db.refresh(current_user)

    # 地域変更のチェック
    address_changed = (current_user.prefecture != old_prefecture) or (current_user.city != old_city)
    if address_changed and current_user.prefecture and current_user.city:
        # ここに必要な地域グループ作成ロジックがあれば入れる
        pass 

    return current_user

# ==========================================
# 💡 3. 今日の気分登録 (Mood Log) - POST /users/me/mood
# ==========================================

@router.post("/me/mood", response_model=schemas.UserMe, summary="今日の気分を登録")
def update_my_mood(
    mood_data: schemas.MoodLogCreate, # MoodLogCreate スキーマを使用
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    ユーザーの現在の気分を MoodLog に記録し、ユーザー本体の current_mood も更新します。
    """
    # A. 履歴(ログ)に残す
    new_log = models.MoodLog(
        user_id=current_user.id,
        mood_type=mood_data.mood_type,
        comment=mood_data.comment
    )
    db.add(new_log)
    
    # B. ユーザー本体の「現在のステータス」も更新
    current_user.current_mood = mood_data.mood_type
    current_user.current_mood_comment = mood_data.comment
    current_user.mood_updated_at = func.now()
    
    db.commit()
    db.refresh(current_user)
    return current_user


# ==========================================
# 💡 4. 自分の気分履歴を取得 (Me版) - GET /users/me/mood-history (新規追加)
# ==========================================
@router.get("/me/mood-history", response_model=List[schemas.MoodLogResponse], summary="自分の気分履歴を取得")
def get_my_mood_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """認証ユーザー自身の気分履歴を取得します。"""
    
    # 3ヶ月以内 かつ 最大1000件
    three_months_ago = datetime.now() - timedelta(days=90)

    logs = db.query(models.MoodLog)\
             .filter(models.MoodLog.user_id == current_user.id)\
             .filter(models.MoodLog.created_at >= three_months_ago)\
             .order_by(models.MoodLog.created_at.desc())\
             .limit(1000)\
             .all()
             
    return logs

# ==========================================
# 💡 8. 新規追加: ユーザー検索機能 - GET /users/search
# ==========================================

@router.get("/search", response_model=List[schemas.UserPublic], summary="ユーザー検索（ニックネームまたはユーザー名で部分一致）")
def search_users(
    query: str = Query(..., min_length=1, description="検索クエリ（ニックネームまたはユーザー名）"),
    limit: int = Query(20, gt=0, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    ニックネームまたはユーザー名で、現在のユーザー以外のユーザーを検索します。
    """
    search_pattern = f"%{query}%"

    # ニックネームまたはユーザー名で部分一致検索し、自分自身を除外する
    users = db.query(models.User).filter(
        models.User.id != current_user.id, # 自分自身を除外
        or_(
            models.User.nickname.ilike(search_pattern), # ニックネームで検索
            models.User.username.ilike(search_pattern)  # ユーザー名で検索
        )
    ).limit(limit).all()

    return users

# ==========================================
# 💡 4. (元) 気分履歴の取得 (安全キャップ付き) - GET /users/{user_id}/mood-history
# ==========================================

@router.get("/{user_id}/mood-history", response_model=List[schemas.MoodLogResponse], summary="ユーザーの気分履歴を取得")
def get_user_mood_history(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    指定されたユーザーIDの気分履歴を取得します（公開設定に従う）。
    最大3ヶ月以内、1000件に制限されます。
    """
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    
    # 公開設定チェック（閲覧者が本人ではない かつ 非公開設定の場合）
    if current_user.id != target_user.id and not target_user.is_mood_visible:
          raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="このユーザーの気分履歴を閲覧する権限がありません")
    
    # 3ヶ月以内 かつ 最大1000件
    three_months_ago = datetime.now() - timedelta(days=90)

    logs = db.query(models.MoodLog)\
             .filter(models.MoodLog.user_id == user_id)\
             .filter(models.MoodLog.created_at >= three_months_ago)\
             .order_by(models.MoodLog.created_at.desc())\
             .limit(1000)\
             .all()
             
    return logs

# ==========================================
# 💡 5. 気分公開設定の切り替え - PATCH /users/me/mood-visibility
# ==========================================

@router.patch("/me/mood-visibility", summary="気分履歴の公開/非公開を切り替え")
def toggle_mood_visibility(
    is_visible: bool,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    自分の気分履歴の公開設定を切り替えます。
    """
    current_user.is_mood_visible = is_visible
    db.commit()
    return {"message": f"気分の公開設定を {'ON' if is_visible else 'OFF'} にしました"}

# ==========================================
# 💡 6. ユーザーの通知一覧取得
# ==========================================

@router.get(
    "/me/notifications", 
    response_model=List[schemas.NotificationResponse], 
    summary="自分宛ての通知一覧を取得"
)
def read_my_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    limit: int = Query(20, gt=0, le=100),
    offset: int = Query(0, ge=0)
):
    """
    認証済みユーザー宛ての通知（メンション、アナウンス、Meetup通知など）を新しい順に取得します。
    """
    notifications = db.query(models.Notification).filter(
        models.Notification.recipient_id == current_user.id
    ).order_by(
        desc(models.Notification.created_at)
    ).offset(offset).limit(limit).all()
    
    if not notifications:
        return []
        
    return notifications


# ==========================================
# 💡 9. 新規追加: FRIENDS/フォロー/アンフォロー機能
# ==========================================

@router.post("/{user_id}/follow", status_code=status.HTTP_200_OK, summary="ユーザーをFRIENDS/フォローする")
def follow_user(
    user_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """
    指定されたIDのユーザーをフォロー（FRIENDS申請）します。
    """
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="自分自身をフォローすることはできません")

    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="フォロー対象のユーザーが見つかりません")

    # 既にフォロー済みかチェック
    existing_follow = db.query(models.Follow).filter(
        models.Follow.follower_id == current_user.id,
        models.Follow.following_id == user_id
    ).first()

    if existing_follow:
        # すでにフォローしている場合は、ここでアンフォロー（FRIENDS解除）を行う
        db.delete(existing_follow)
        db.commit()
        return {"message": "アンフォローしました", "status": "unfollowed"}
    else:
        # まだフォローしていない場合は、新しくフォロー関係を作成
        new_follow = models.Follow(
            follower_id=current_user.id,
            following_id=user_id
        )
        db.add(new_follow)
        db.commit()
        return {"message": "フォローしました", "status": "followed"}



# ==========================================
# 💡 7. 基本CRUD (Admin/Advanced Use)
# ==========================================

@router.get("/", response_model=List[schemas.UserPublic], summary="全ユーザー情報を取得 (Admin/Auth)")
def read_users(db: Session = Depends(get_db), 
               current_user: models.User = Depends(get_current_user)):
    """全てのユーザー情報を取得します。"""
    return db.query(models.User).all()

@router.get("/{user_id}", response_model=schemas.UserPublic, summary="特定のユーザー情報を取得")
def read_user(user_id: int, 
              db: Session = Depends(get_db), 
              current_user: models.User = Depends(get_current_user)):
    """特定のIDのユーザー情報を取得します。"""
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ユーザーが見つかりません")
        
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="特定のユーザーを削除")
def delete_user(user_id: int, 
                db: Session = Depends(get_db), 
                current_user: models.User = Depends(get_current_user)):
    """特定のIDのユーザーを削除します（本人または管理者のみ許可）。"""
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ユーザーが見つかりません")
        
    # 💡 権限チェック: 自分のアカウントか、管理者であること
    if user.id != current_user.id: 
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="このユーザー情報を削除する権限がありません")

    db.delete(user)
    db.commit()
    
    return

# 💡 UserMoodResponse をこのファイル内で定義してエラーを消します
class UserMoodResponse(BaseModel):
    user_id: int
    nickname: Optional[str] = None
    email: Optional[str] = None
    current_mood: Optional[str] = None
    current_mood_comment: Optional[str] = None
    mood_updated_at: Optional[datetime] = None
    friend_note: Optional[str] = None 

    model_config = ConfigDict(from_attributes=True)

# 💡 response_model から "schemas." を消して直接指定します
@router.get("/following/moods", response_model=List[UserMoodResponse])
def get_following_moods(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    results = db.query(
        models.User,
        models.Friendship.friend_note 
    ).join(
        models.Friendship, models.Friendship.friend_id == models.User.id
    ).filter(
        models.Friendship.user_id == current_user.id
    ).all()

    moods = []
    for user, note in results:
        moods.append({
            "user_id": user.id,
            "nickname": user.nickname,
            "email": user.email,
            "current_mood": user.current_mood,
            "current_mood_comment": user.current_mood_comment,
            "mood_updated_at": user.mood_updated_at,
            "friend_note": note 
        })
    return moods