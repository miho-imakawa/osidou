# backend/app/schemas/posts.py

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# ============================================================
# 1. 最初にレスポンス（参加者）側を定義する
# ============================================================

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
    is_attended: bool = Field(False, description="出席済みフラグ")

    class Config:
        from_attributes = True

# ============================================================
# 2. 次に投稿（Post）のベースを定義する
# ============================================================

class HobbyPostBase(BaseModel):
    content: str = Field(description="投稿内容")
    hobby_category_id: int = Field(description="所属する趣味カテゴリのID")
    is_meetup: bool = Field(False, description="Meet up告知")
    meetup_date: Optional[datetime] = Field(None, description="開催日時")
    meetup_location: Optional[str] = Field(None, description="開催場所")
    meetup_capacity: Optional[int] = Field(None, description="定員数")
    meetup_fee_info: Optional[str] = Field(None, description="費用詳細")
    meetup_status: Optional[str] = Field("open", description="募集状況 (open/closed)")
    parent_id: Optional[int] = Field(None, description="親投稿のID（返信の場合）")
    is_ad: bool = Field(False, description="有料広告投稿であるか")
    ad_end_date: Optional[datetime] = Field(None, description="広告掲載終了日")
    original_post_id: Optional[int] = Field(None, description="リポスト元の投稿ID")
    ad_color: Optional[str] = Field("green", description="広告カラー")

class HobbyPostCreate(HobbyPostBase):
    """投稿作成リクエスト"""
    pass

class HobbyPostResponse(HobbyPostBase):
    """投稿の詳細応答（参加者リスト含む）"""
    id: int
    user_id: int
    created_at: datetime
    author_nickname: Optional[str] = None
    public_code: Optional[str] = None
    response_count: Optional[int] = 0
    participation_count: Optional[int] = 0
    
    # 💡 参加者リストをフロントエンドに送る
    responses: List[PostResponseResponse] = []
    
    # 親投稿（返信の場合）
    parent_post: Optional["HobbyPostResponse"] = None 

    class Config:
        from_attributes = True

# ============================================================
# 3. 全グループ投稿用
# ============================================================

class AllPostCreate(BaseModel):
    """自分が参加している全グループへの投稿リクエスト"""
    content: str = Field(description="投稿内容")
    confirmed: bool = Field(False, description="確認済みフラグ")

# ============================================================
# 循環参照の解決
# ============================================================
HobbyPostResponse.model_rebuild()

