# C:\osidou\backend\app\schemas\friend_requests.py

from pydantic import BaseModel, ConfigDict
from typing import Literal, Optional, List
from datetime import datetime

# modelsを正しくインポートするため、相対インポートを使用
from .. import models 
from .users import UserPublic

class UserSimple(BaseModel):
    id: int
    username: str
    nickname: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class FriendRequestBase(BaseModel):
    id: int
    requester_id: int
    receiver_id: int
    status: str 
    created_at: datetime
    updated_at: datetime
    # 💡 修正：警告が出ない Pydantic v2 の書き方に統一
    model_config = ConfigDict(from_attributes=True)

# 申請ステータス更新用（リクエストボディ用）
# C:\osidou\backend\app\schemas\friend_requests.py

# --- 1. 申請そのものの処理（一度きりの操作） ---
class FriendRequestUpdate(BaseModel):
    """
    フレンド申請に対して『承認』か『拒否』を決定する際のスキーマ。
    PUT /friend_requests/{id}/status で使用。
    """
    status: Literal[
        models.FriendRequestStatus.ACCEPTED, 
        models.FriendRequestStatus.REJECTED
    ]
    model_config = ConfigDict(from_attributes=True)


# --- 2. 承認後の関係性管理（継続的な設定変更） ---
class FriendStatusUpdate(BaseModel):
    """
    友達になった後、その相手を『ミュート』や『非表示』にする際のスキーマ。
    PATCH /friends/{user_id}/settings などのエンドポイントを想定。
    """
    # 特定のアクションを指定させる場合
    action: Optional[Literal['hide', 'show', 'mute', 'unmute']] = None
    
    # または、より柔軟に boolean で直接指定させる形もスマートです
    is_muted: Optional[bool] = None
    is_hidden: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)

class FriendRequestResponse(BaseModel):
    id: int
    requester_id: int
    receiver_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    requester: UserSimple  # 👈 ここで申請者の情報を含める

    model_config = ConfigDict(from_attributes=True)

# --- 友達一覧を取得するためのレスポンス形式 ---
class FriendshipResponse(BaseModel):
    id: int
    user_id: int
    friend_id: int
    friend_note: Optional[str] = None  # 追加した「メモ」カラム
    is_muted: bool
    is_hidden: bool
    
    friend: UserSimple
    # 循環参照を避けるため、UserSimpleなど既存のスキーマを利用
    # friend: Optional[UserSimple] = None 

    model_config = ConfigDict(from_attributes=True)

class FriendshipUpdate(BaseModel):
    friend_note: Optional[str] = None
    is_muted: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)