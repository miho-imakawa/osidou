from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# models.pyで定義されているEnumをインポート（存在すると仮定）

# ==========================================
# 💡 HobbyCategory（全階層共通スキーマ）
# ==========================================

class HobbyCategoryBase(BaseModel):
    """全階層で共通のベーススキーマ"""
    id: int
    name: str
    parent_id: Optional[int]
    
    # 💡 街の戦略：マスターIDを追加
    # これにより、分身（エイリアス）から本尊（マスター）への道筋がフロントに伝わります
    master_id: Optional[int] = None 
    
    depth: int 
    role_type: Optional[str] = None 
    description: Optional[str] = None
    created_at: datetime
    member_count: Optional[int] = 0
    
    # 💡 unique_code もフロントで表示に使っているので追加しておきましょう
    unique_code: Optional[str] = None 

    is_public: Optional[bool] = False 

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

class CastMember(BaseModel):
    name: str
    role: Optional[str] = None
    master_id: Optional[int] = None

# 自由セクションの定義
class DetailSection(BaseModel):
    label: str
    content: str

# 今回エラーになっているメインのクラス
class CategoryDetailBase(BaseModel):
    description: Optional[str] = ""
    alias: Optional[str] = "" 
    cast: List[CastMember] = []
    sections: List[DetailSection] = []

    # Pydantic V2 用の設定
    model_config = {"from_attributes": True}