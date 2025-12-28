from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

# ==========================================
# 💡 AccessLog (入退室ログ) スキーマ
# ==========================================

class AccessLogCreate(BaseModel):
    """1. 入室時のログ作成用スキーマ (ユーザーIDと時刻はサーバー側で設定)"""
    pass

class AccessLogUpdate(BaseModel):
    """2. 退室時のログ更新用スキーマ (サーバー側で時刻を設定するトリガーとして使用)"""
    # 退室処理のトリガーとして使用するため、空のモデルで十分です。
    pass 

class AccessLogRead(BaseModel):
    """3. ログの読み取り（レスポンス）用スキーマ"""
    id: int
    user_id: int
    entry_time: datetime
    exit_time: Optional[datetime] = None
    
    # 💡 ルーター側で計算される滞在時間
    duration_minutes: Optional[int] = None 

    model_config = ConfigDict(from_attributes=True)

# 4. 利用時間分析のレスポンス用スキーマ
class UsageAnalytics(BaseModel):
    """分析結果とログリストを返すスキーマ"""
    total_duration_hours: float
    average_duration_minutes: float
    # logs_with_duration は AccessLogRead のリスト
    logs_with_duration: List[AccessLogRead]