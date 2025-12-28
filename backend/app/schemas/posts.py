from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date

# ==========================================
# 💡 共通スキーマ
# ==========================================

class MessageResponse(BaseModel):
    """汎用的なメッセージ応答"""
    message: str = Field(description="応答メッセージ")
    posted_count: Optional[int] = None # ALL投稿用のフィールド

# ==========================================
# 💡 投稿 (HobbyPost)
# ==========================================

class HobbyPostBase(BaseModel):
    """趣味グループへの投稿の基本情報"""
    content: str = Field(description="投稿内容 (地域タグ [東京] などを含む可能性あり)")
    hobby_group_id: int = Field(description="所属する趣味グループのID")
    
    # Meet up イベント用フィールド
    is_meetup: bool = Field(False, description="Meet up（オフ会）告知であるか")
    meetup_date: Optional[datetime] = Field(None, description="開催日時")
    meetup_location: Optional[str] = Field(None, description="開催場所")
    meetup_capacity: Optional[int] = Field(None, description="定員数")

class HobbyPostCreate(HobbyPostBase):
    """投稿作成リクエスト"""
    pass

class HobbyPostResponse(HobbyPostBase):
    """投稿の詳細応答 (Read/Detail用)"""
    id: int
    user_id: int
    created_at: datetime
    
    # 動的に追加されるフィールド
    author_nickname: str = Field(None, description="投稿者のニックネーム")
    response_count: Optional[int] = Field(0, description="この投稿への返信数 (コメント/参加表明)")
    participation_count: Optional[int] = Field(0, description="Meetupへの参加表明数")
    
    class Config:
        from_attributes = True

# ==========================================
# 💡 投稿への返信 (PostResponse)
# ==========================================

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
    post_id: int = Field(description="対象のHobbyPost ID")
    created_at: datetime
    
    # 動的に追加されるフィールド
    author_nickname: str = Field(None, description="返信者のニックネーム")

    class Config:
        from_attributes = True

# ==========================================
# 💡 ALL投稿
# ==========================================

class AllPostCreate(BaseModel):
    """自分が参加している全グループへの投稿リクエスト"""
    content: str = Field(description="投稿内容")
    confirmed: bool = Field(False, description="フロントエンド側で確認ダイアログを表示し、Trueが渡されること")

# ==========================================
# 💡 通知 (Notification)
# ==========================================

class NotificationBase(BaseModel):
    """通知の基本情報"""
    user_id: int
    title: str = Field(description="通知のタイトル")
    message: str = Field(description="通知メッセージ本文")
    post_id: Optional[int] = Field(None, description="関連する投稿ID")
    is_read: bool = Field(False, description="既読フラグ")

class NotificationResponse(NotificationBase):
    """通知の詳細応答"""
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class UnreadCountResponse(BaseModel):
    """未読通知件数応答"""
    unread_count: int