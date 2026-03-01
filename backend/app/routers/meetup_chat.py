from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

from .. import models
from ..database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/meetup-chat", tags=["meetup-chat"])

# ==========================================
# 💡 スキーマ定義
# ==========================================
class MeetupMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class MeetupMessageResponse(BaseModel):
    id: int
    content: str
    created_at: datetime
    user_id: int
    post_id: int
    author_nickname: Optional[str] = None

    class Config:
        from_attributes = True

# ==========================================
# 💡 共通バリデーション関数
# ==========================================
def check_chat_permission(post_id: int, user_id: int, db: Session):
    """主催者または参加者であるかを確認する"""
    post = db.query(models.HobbyPost).filter(models.HobbyPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="MeetUpが見つかりません")
    if not post.is_meetup:
        raise HTTPException(status_code=400, detail="これはMeetUp投稿ではありません")

    # 1. 主催者(HOST)であるか確認
    is_host = (post.user_id == user_id)
    if is_host:
        return post

    # 2. 参加者リストに含まれているか確認
    is_participant = db.query(models.PostResponse).filter(
        models.PostResponse.post_id == post_id,
        models.PostResponse.user_id == user_id,
        models.PostResponse.is_participation == True
    ).first()

    if not is_participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="このMeetUpの参加者または主催者のみアクセス可能です"
        )
    return post

# ==========================================
# 💡 APIエンドポイント
# ==========================================

@router.get("/{post_id}", response_model=List[MeetupMessageResponse])
def get_meetup_messages(
    post_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user) # 💡 閲覧時も認証を追加
):
    """過去ログ取得（HOSTまたは参加者のみ）"""
    check_chat_permission(post_id, current_user.id, db)
    
    messages = db.query(models.MeetupMessage)\
        .filter(models.MeetupMessage.post_id == post_id)\
        .order_by(models.MeetupMessage.created_at.asc())\
        .all()
    return messages

@router.post("/{post_id}", response_model=MeetupMessageResponse, status_code=status.HTTP_201_CREATED)
def send_meetup_message(
    post_id: int, 
    message_in: MeetupMessageCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """メッセージ送信（HOSTまたは参加者のみ）"""
    check_chat_permission(post_id, current_user.id, db)
    
    db_message = models.MeetupMessage(
        post_id=post_id,
        user_id=current_user.id,
        author_nickname=current_user.nickname or f"User{current_user.id}",
        content=message_in.content
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message