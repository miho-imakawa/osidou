from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime
from .. import models # Enum参照のため
# 💡 修正: 以下の自己参照インポートは循環参照の原因となるため削除されました。

# ==========================================
# 💡 1. Branch (店舗) スキーマ
# ==========================================

class BranchBase(BaseModel):
    name: str = Field(..., max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    max_capacity: int = Field(50, ge=1, description="最大収容人数")
    hourly_base_fee: float = Field(300.0, ge=0, description="時間あたりの基本料金")

class BranchCreate(BranchBase):
    pass

class BranchResponse(BranchBase):
    id: int
    # events: List["EventResponse"] = [] # リレーションは詳細取得時に使用
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 💡 2. Event (イベント) スキーマ
# ==========================================

class EventBase(BaseModel):
    title: str = Field(..., max_length=150)
    description: Optional[str] = None
    branch_id: int = Field(description="開催店舗ID")
    capacity: int = Field(12, ge=1, description="イベントの定員")
    creator_price: int = Field(0, ge=0, description="主催者料金（参加者が支払う料金とは限らない）")
    start_time: datetime
    end_time: datetime
    owner_id: int = Field(description="イベント主催者ユーザーID")

class EventCreate(EventBase):
    pass

class EventResponse(EventBase):
    id: int
    owner_nickname: Optional[str] = None # 主催者のニックネーム（動的に追加）
    current_participants: Optional[int] = 0 # 現在の参加人数（動的に追加）
    
    model_config = ConfigDict(from_attributes=True)

# 💡 2-A. Event Registration (イベント参加登録) スキーマ
class EventRegistrationResponse(BaseModel):
    user_id: int
    event_id: int
    registered_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
    
# ==========================================
# 💡 3. Seat (座席) スキーマ
# ==========================================

class SeatBase(BaseModel):
    name: str = Field(..., max_length=50, description="座席名/座席番号")
    location: Optional[str] = Field(None, max_length=100, description="座席の場所詳細")
    seat_type: str = Field("flexible", max_length=50, description="座席タイプ (flexible, fixedなど)")
    price_per_hour: float = Field(500.0, ge=0, description="時間あたりの料金")

class SeatCreate(SeatBase):
    branch_id: int = Field(description="所属店舗ID")

class SeatResponse(SeatBase):
    id: int
    branch_id: int
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 💡 4. Reservation (予約) スキーマ
# ==========================================

class ReservationBase(BaseModel):
    seat_id: int
    start_time: datetime
    end_time: datetime

class ReservationCreate(ReservationBase):
    pass

class ReservationResponse(ReservationBase):
    id: int
    user_id: int
    status: str = "active" # active, cancelled, completed など
    
    model_config = ConfigDict(from_attributes=True)