# app/schemas/community.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

# 循環参照を防ぐため、文字列で受け取るか、ここで再定義するか、
# modelsからEnumだけインポートします。
from app.models import HobbyRoleType

# --------------------------------------
# カテゴリ (例: 音楽, スポーツ)
# --------------------------------------
class CategoryBase(BaseModel):
    genre: str

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    class Config:
        from_attributes = True

# --------------------------------------
# コミュニティグループ
# --------------------------------------
class CommunityGroupBase(BaseModel):
    genre: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    role_type: Optional[HobbyRoleType] = None # "players" or "fans"
    
    # 地域情報は自動生成時などに使うが、手動作成時は任意
    is_region_group: bool = False
    region_key: Optional[str] = None

class CommunityGroupCreate(CommunityGroupBase):
    pass

class CommunityGroupResponse(CommunityGroupBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# --------------------------------------
# 投稿 (Posts)
# --------------------------------------
class CommunityPostBase(BaseModel):
    content: str
    image_url: Optional[str] = None
    is_event_announcement: bool = False
    
    # 投稿時にエリア情報をタグ付けする場合
    region_tag_pref: Optional[str] = None
    region_tag_city: Optional[str] = None

class CommunityPostCreate(CommunityPostBase):
    group_id: int  # どのグループへの投稿か指定

class CommunityPostResponse(CommunityPostBase):
    id: int
    user_id: int
    group_id: int
    created_at: datetime
    
    # 投稿者の情報を少しだけ返すとフロントエンドで表示しやすい
    # （必要に応じてUserSchemaをネストするが、ここではIDのみにしておく）
    
    class Config:
        from_attributes = True