# C:\E-Basho\backend\app\schemas\branches.py (最終整理案)

from pydantic import BaseModel, ConfigDict
# datetime は使用しないため、削除 (typing.Optional のみで十分)
from typing import Optional 
# from datetime import datetime # 不要

# 1. 店舗作成時の入力スキーマ
class BranchCreate(BaseModel):
    name: str 
    address: Optional[str] = None
    max_capacity: int = 50
    # 💡 追記: 場所の基本料金（イベント料金計算で使用）
    hourly_base_fee: float = 300.0 


# 2. 店舗情報の読み取り・レスポンス用スキーマ
class BranchRead(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    max_capacity: int
    # 💡 追記: 場所の基本料金
    hourly_base_fee: float 
    
    # SQLAlchemyモデルとの互換性設定
    model_config = ConfigDict(from_attributes=True)