from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Dict
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

class ReactionSummary(BaseModel):
    reaction: str
    count: int
    reacted_by_me: bool

class MeetupMessageResponse(BaseModel):
    id: int
    content: str
    created_at: datetime
    user_id: int
    post_id: int
    author_nickname: Optional[str] = None
    reactions: List[ReactionSummary] = []

    class Config:
        from_attributes = True

class ReactionCreate(BaseModel):
    reaction: str = Field(..., min_length=1, max_length=10)

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


def build_reactions(message_id: int, current_user_id: int, db: Session) -> List[ReactionSummary]:
    """メッセージのリアクション集計（絵文字ごとのcount + 自分が押したか）"""
    rows = db.query(models.MeetupMessageReaction).filter(
        models.MeetupMessageReaction.message_id == message_id
    ).all()

    counts: Dict[str, int] = {}
    mine: set = set()
    for r in rows:
        counts[r.reaction] = counts.get(r.reaction, 0) + 1
        if r.user_id == current_user_id:
            mine.add(r.reaction)

    return [
        ReactionSummary(reaction=emoji, count=cnt, reacted_by_me=(emoji in mine))
        for emoji, cnt in counts.items()
    ]


# ==========================================
# 💡 APIエンドポイント
# ==========================================

@router.get("/{post_id}", response_model=List[MeetupMessageResponse])
def get_meetup_messages(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """過去ログ取得（HOSTまたは参加者のみ）"""
    check_chat_permission(post_id, current_user.id, db)

    messages = db.query(models.MeetupMessage)\
        .filter(models.MeetupMessage.post_id == post_id)\
        .order_by(desc(models.MeetupMessage.created_at))\
        .all()

    # リアクションを各メッセージに付与
    result = []
    for m in messages:
        reactions = build_reactions(m.id, current_user.id, db)
        result.append(MeetupMessageResponse(
            id=m.id,
            content=m.content,
            created_at=m.created_at,
            user_id=m.user_id,
            post_id=m.post_id,
            author_nickname=m.author_nickname,
            reactions=reactions,
        ))
    return result


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

    return MeetupMessageResponse(
        id=db_message.id,
        content=db_message.content,
        created_at=db_message.created_at,
        user_id=db_message.user_id,
        post_id=db_message.post_id,
        author_nickname=db_message.author_nickname,
        reactions=[],
    )


@router.post("/{post_id}/messages/{message_id}/reaction", status_code=status.HTTP_200_OK)
def toggle_reaction(
    post_id: int,
    message_id: int,
    reaction_in: ReactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    リアクションのトグル（押す／外す）
    - 同じ絵文字を再度押すと削除（トグル）
    - 返り値: { "action": "added" | "removed", "reactions": [...] }
    """
    check_chat_permission(post_id, current_user.id, db)

    # メッセージ存在確認
    message = db.query(models.MeetupMessage).filter(
        models.MeetupMessage.id == message_id,
        models.MeetupMessage.post_id == post_id
    ).first()
    if not message:
        raise HTTPException(status_code=404, detail="メッセージが見つかりません")

    # 既存リアクション確認
    existing = db.query(models.MeetupMessageReaction).filter(
        models.MeetupMessageReaction.message_id == message_id,
        models.MeetupMessageReaction.user_id == current_user.id,
        models.MeetupMessageReaction.reaction == reaction_in.reaction
    ).first()

    if existing:
        # 既に押している → 削除（トグルOFF）
        db.delete(existing)
        db.commit()
        action = "removed"
    else:
        # 未押し → 追加（トグルON）
        new_reaction = models.MeetupMessageReaction(
            message_id=message_id,
            user_id=current_user.id,
            reaction=reaction_in.reaction
        )
        db.add(new_reaction)
        db.commit()
        action = "added"

    reactions = build_reactions(message_id, current_user.id, db)
    return {"action": action, "reactions": reactions}
