# C:\E-Basho\backend\app\schemas\seats.py

from pydantic import BaseModel, ConfigDict
from typing import Optional

# 座席作成時の入力スキーマ (管理者用)
class SeatCreate(BaseModel):
    name: str 
    location: str
    type: str
    price_per_hour: float

# 座席情報の読み取り・レスポンス用スキーマ
class SeatRead(BaseModel):
    id: int
    name: str
    location: str
    type: str
    price_per_hour: float
    
    # 💡 SQLAlchemyモデルとの互換性設定
    model_config = ConfigDict(from_attributes=True)