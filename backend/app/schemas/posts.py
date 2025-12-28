# backend/app/schemas/posts.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class HobbyPostBase(BaseModel):
    content: str = Field(description="投稿内容")
    hobby_category_id: int = Field(description="所属する趣味カテゴリのID")  # ✅ 統一
    is_meetup: bool = Field(False, description="Meet up（オフ会）告知であるか")
    meetup_date: Optional[datetime] = Field(None, description="開催日時")
    meetup_location: Optional[str] = Field(None, description="開催場所")
    meetup_capacity: Optional[int] = Field(None, description="定員数")

class HobbyPostCreate(HobbyPostBase):
    pass

class HobbyPostResponse(HobbyPostBase):
    id: int
    user_id: int
    created_at: datetime
    author_nickname: Optional[str] = None
    public_code: Optional[str] = None  # ✅ 7桁コード用
    response_count: Optional[int] = 0
    participation_count: Optional[int] = 0
    
    class Config:
        from_attributes = True

class PostResponseBase(BaseModel):
    """投稿への返信/参加表明の基本情報"""
    content: Optional[str] = Field(None, description="コメント内容")
    is_participation: bool = Field(False, description="Meetupへの参加表明であるか")

class PostResponseCreate(PostResponseBase):
    """返信作成リクエスト"""
    pass

class PostResponseResponse(PostResponseBase):
    """返信の詳細応答"""
    id: int
    user_id: int
    post_id: int
    created_at: datetime
    author_nickname: Optional[str] = None

    class Config:
        from_attributes = True

class AllPostCreate(BaseModel):
    """自分が参加している全グループへの投稿リクエスト"""
    content: str = Field(description="投稿内容")
    confirmed: bool = Field(False, description="確認済みフラグ")