# ルーターが使用する主要なスキーマを明示的にインポートし、
# app.schemas.〇〇 として参照できるようにする。

# User/Auth
from .users import UserCreate, UserPublic, UserMe, UserProfileUpdate, MoodLogCreate, MoodLogResponse, NotificationResponse
from .auth import Token, TokenData

# Access Logs
from .access_logs import AccessLogCreate, AccessLogUpdate, AccessLogRead, UsageAnalytics

# Branch/Event/Reservation/Invoice
from .events import (
    BranchCreate, BranchResponse, EventCreate, EventResponse, 
    SeatCreate, SeatResponse, ReservationCreate, ReservationResponse
)
from .invoices import InvoiceCreate, InvoiceRead, SubscriptionCreate, SubscriptionResponse # 💡 修正: InvoiceResponse -> InvoiceRead

# SNS/Posts
from .posts import HobbyPostCreate, HobbyPostResponse, PostResponseCreate, PostResponseResponse, AllPostCreate
from .hobbies import HobbyCategoryResponse, HobbySearchParams

# 💡 Friend Requests (新規追加)
from .friend_requests import FriendRequestBase, FriendRequestUpdate, FriendRequestResponse, FriendStatusUpdate, FriendshipResponse, FriendshipUpdate