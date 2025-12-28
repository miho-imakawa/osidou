from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# models.pyで定義されているEnumをインポート（存在すると仮定）

# ==========================================
# 💡 HobbyCategory（全階層共通スキーマ）
# ==========================================

class HobbyCategoryBase(BaseModel):
    """全階層（Category, Role, Genre, Group）で共通のベーススキーマ"""
    id: int
    name: str
    parent_id: Optional[int]
    # depth はシードで 0, 1, 2, 3 の値が設定されています
    depth: int 
    
    # Level 1 (Role)でのみ使用される role_type を追加
    role_type: Optional[str] = None 
    
    description: Optional[str] = None
    created_at: datetime
    
    # 参加人数（計算で取得するフィールドとして定義）
    member_count: Optional[int] = 0
    
    class Config:
        from_attributes = True

# 趣味カテゴリーの階層構造用スキーマ（自己参照）
class HobbyCategoryResponse(HobbyCategoryBase):
    """階層構造（ツリー）を表現するための自己参照スキーマ"""
    # children フィールドに自身（HobbyCategoryResponse）のリストを持つ
    children: List['HobbyCategoryResponse'] = []

# Pydantic V2の自己参照のために必要
# これにより、List['HobbyCategoryResponse'] が正しく解釈されます。
HobbyCategoryResponse.model_rebuild()

# ==========================================
# 💡 その他検索用スキーマ
# ==========================================

class HobbySearchParams(BaseModel):
    """趣味検索パラメータ"""
    category_id: Optional[int] = None
    role_type: Optional[str] = None  # "doers" or "fans"
    genre_id: Optional[int] = None
    keyword: Optional[str] = None  # グループ名で検索