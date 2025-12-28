# C:\E-Basho\backend\app\schemas\reservations.py

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

# 予約作成時の入力スキーマ
class ReservationCreate(BaseModel):
    seat_id: int
    start_time: datetime
    end_time: datetime
    # user_id はトークンから自動取得するため、入力に含めない

# 予約読み取り・レスポンス用スキーマ
class ReservationRead(BaseModel):
    id: int
    user_id: int
    seat_id: int
    start_time: datetime
    end_time: datetime
    status: str
    
    model_config = ConfigDict(from_attributes=True)

# 予約キャンセル/ステータス更新用のスキーマ
class ReservationUpdate(BaseModel):
    status: Optional[str] = None