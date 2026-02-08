# backend/app/schemas/posts.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class HobbyPostBase(BaseModel):
    content: str = Field(description="投稿内容")
    hobby_category_id: int = Field(description="所属する趣味カテゴリのID")
    is_meetup: bool = Field(False, description="Meet up告知")
    meetup_date: Optional[datetime] = Field(None, description="開催日時")
    meetup_location: Optional[str] = Field(None, description="開催場所")
    meetup_capacity: Optional[int] = Field(None, description="定員数")
    
    # --- 💡 新規追加: MeetUpの運用詳細 ---
    meetup_fee_info: Optional[str] = Field(None, description="費用詳細")
    meetup_status: Optional[str] = Field("open", description="募集状況 (open/closed)")
    parent_id: Optional[int] = Field(None, description="親投稿のID（返信の場合）")
    is_meetup: bool = Field(False, description="Meet up告知")

    # --- 広告とリポスト用 ---
    is_ad: bool = Field(False, description="有料広告投稿であるか")
    ad_end_date: Optional[datetime] = Field(None, description="広告掲載終了日")
    original_post_id: Optional[int] = Field(None, description="リポスト元の投稿ID")

class HobbyPostCreate(HobbyPostBase):
    pass

class HobbyPostResponse(HobbyPostBase):
    id: int
    user_id: int
    created_at: datetime
    author_nickname: Optional[str] = None
    public_code: Optional[str] = None
    response_count: Optional[int] = 0
    participation_count: Optional[int] = 0
    
    # 💡 念のためレスポンスにも含める（Baseを継承しているので自動で含まれますが、明示的に管理する場合）
    meetup_fee_info: Optional[str] = None   
    meetup_status: Optional[str] = "open"
    
    # --- 💡 新規追加: フロントでの表示用 ---
    # リポストの場合、元の投稿内容を含めることができる
    parent_post: Optional["HobbyPostResponse"] = None 

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

# backend/app/schemas/posts.py の一番最後に追加
HobbyPostResponse.model_rebuild()