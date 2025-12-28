from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import date, datetime
from .. import models # Enum参照のため

# ==========================================
# 💡 1. Subscription (サブスクリプション) スキーマ
# ==========================================

class SubscriptionBase(BaseModel):
    plan_type: models.SubscriptionPlan
    status: Optional[str] = "active"
    next_billing_date: Optional[date] = None

class SubscriptionCreate(SubscriptionBase):
    """新規サブスクリプション作成時の入力スキーマ"""
    user_id: int # 管理者用APIを想定

class SubscriptionResponse(SubscriptionBase):
    id: int
    user_id: int
    stripe_subscription_id: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 💡 2. Invoice (請求書) スキーマ
# ==========================================

class InvoiceBase(BaseModel):
    user_id: int
    billing_start_date: date
    billing_end_date: date
    total_amount: float
    status: str = "pending"
    payment_date: Optional[datetime] = None

class InvoiceCreate(InvoiceBase):
    """請求書作成時の入力スキーマ（管理者専用）"""
    pass

class InvoiceRead(InvoiceBase): # 💡 InvoiceResponse から InvoiceRead にリネーム済み
    """請求書レスポンススキーマ"""
    id: int
    model_config = ConfigDict(from_attributes=True)