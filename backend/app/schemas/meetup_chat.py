from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/meetup-chat", tags=["meetup-chat"])

class MeetupMessageCreate(BaseModel):
    content: str

class MeetupMessageResponse(BaseModel):
    id: int
    content: str
    created_at: datetime
    user_id: int
    post_id: int
    author_nickname: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("/{post_id}", response_model=List[MeetupMessageResponse])
def get_meetup_messages(post_id: int, db: Session = Depends(get_db)):
    messages = db.query(models.MeetupMessage).filter(models.MeetupMessage.post_id == post_id).order_by(models.MeetupMessage.created_at.asc()).all()
    return messages

@router.post("/{post_id}", response_model=MeetupMessageResponse)
def send_meetup_message(
    post_id: int,
    message_in: MeetupMessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
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