import enum
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Date, Text, 
    Enum as SQLEnum, PrimaryKeyConstraint, 
    UniqueConstraint 
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base 
from datetime import datetime

# ==========================================
# 💡 1. Enum定義 (定数)
# ==========================================

# サブスクリプションプラン
class SubscriptionPlan(str, enum.Enum):
    BASE_MEMBERSHIP = "base_membership"  # 月額200円
    MONTHLY_TABLE = "monthly_table"      # 月極25,000円
    TEN_DAY_TABLE = "ten_day_table"      # 10日席10,000円

# 趣味の役割タイプ (Doers vs Fans)
class HobbyRoleType(str, enum.Enum):
    DOERS = "doers"  # する人（演奏する人、描く人、競技する人、料理する人、旅行する人など）
    FANS = "fans"    # 見る人、聞く人、応援する人

# 感情タイプ (Mood Types) - プリセット10種類
class MoodType(str, enum.Enum):
    HAPPY = "happy"          # 😊 幸せ
    EXCITED = "excited"      # 🤩 ワクワク
    CALM = "calm"            # 😌 穏やか
    TIRED = "tired"          # 😴 疲れた
    SAD = "sad"              # 😢 悲しい
    ANXIOUS = "anxious"      # 😰 不安
    ANGRY = "angry"          # 😠 怒り
    NEUTRAL = "neutral"      # 😐 普通
    GRATEFUL = "grateful"    # 🙏 感謝
    MOTIVATED = "motivated"  # 💪 やる気

# フレンド申請の状態
class FriendRequestStatus(str, enum.Enum):
    PENDING = "pending"       # 申請中
    ACCEPTED = "accepted"     # 承認済み
    REJECTED = "rejected"     # 拒否済み

# ==========================================
# 💡 2. SNS・コミュニティ機能モデル（多層ツリー構造）
# ==========================================

# 【多層ツリー構造】Category, Role, Genre, HobbyGroup を統合
class HobbyCategory(Base):
    __tablename__ = "hobby_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), index=True) 
    parent_id = Column(Integer, ForeignKey('hobby_categories.id'), nullable=True) # 👈 親ノードへの参照
    depth = Column(Integer, nullable=False) # 👈 階層番号 (0: Root/Category, 4: Mrs.GREEN APPLE)
    
    # 💡 新規追加: role_type カラムを追加
    unique_code = Column(String(7), unique=True, index=True)
    role_type = Column(SQLEnum(HobbyRoleType), nullable=True)
    
    # 既存の fields を保持
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # リレーション
    parent = relationship("HobbyCategory", remote_side=[id], backref="children", uselist=False)
    
    # 以前の HobbyGroup に相当するリレーション
    members = relationship("UserHobbyLink", back_populates="hobby_category", cascade="all, delete-orphan")
    posts = relationship("HobbyPost", back_populates="hobby_category")
    
    # 【通知モデルとのリレーション】
    # backref="notifications_sent_to" は User モデル側で定義済みのため不要

# 【中間テーブル】ユーザー ⇔ 趣味カテゴリ（旧 UserHobbyLink）
class UserHobbyLink(Base):
    __tablename__ = "user_hobby_links"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    
    # 【修正】hobby_group_id を hobby_category_id に変更
    hobby_category_id = Column(Integer, ForeignKey("hobby_categories.id", ondelete="CASCADE"))
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Userとのリレーション: Userモデル側で 'hobby_categories' を期待
    user = relationship("User", back_populates="hobby_categories")
    hobby_category = relationship("HobbyCategory", back_populates="members")

# C:\osidou\backend\app\models.py の Follow クラス部分

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

# models.py の正しい構造

# ✅ Follow クラス (Chat/場所用)
# 人と人の関係ではなく、人とコミュニティ/場所の関係
class Follow(Base):
    __tablename__ = "follows"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    target_id = Column(Integer, nullable=False)
    target_type = Column(String, nullable=False)  # "chat", "place", "community"

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class Friendship(Base):
    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    friend_id = Column(Integer, ForeignKey("users.id"), nullable=False)

# 💡 これを追加：自分だけが見える相手のメモ（「父」など）
    friend_note = Column(String(100), nullable=True)

    is_muted = Column(Boolean, default=False)
    is_hidden = Column(Boolean, default=False)

    user = relationship("User", foreign_keys=[user_id])
    friend = relationship("User", foreign_keys=[friend_id])

    __table_args__ = (
        UniqueConstraint("user_id", "friend_id", name="unique_friendship"),
    )



# ✅ FriendRequest クラス (人と人の関係)
class FriendRequest(Base):
    __tablename__ = "friend_requests"

    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    status = Column(
        SQLEnum(FriendRequestStatus),
        default=FriendRequestStatus.PENDING,
        nullable=False
    )
    
    # # 友達管理フラグ（status='accepted'の場合に使用）
    # is_muted = Column(Boolean, default=False)   # 更新停止
    # is_hidden = Column(Boolean, default=False)  # 非表示

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('requester_id', 'receiver_id', name='_requester_receiver_uc'),
    )

    requester = relationship(
        "User",
        foreign_keys=[requester_id],
        back_populates="requests_sent"
    )

    receiver = relationship(
        "User",
        foreign_keys=[receiver_id],
        back_populates="requests_received"
    )
    
# ==========================================
# 💡 3. 投稿機能
# ==========================================

# 趣味グループへの投稿
class HobbyPost(Base):
    __tablename__ = "hobby_posts"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    
    # 【修正】hobby_group_id を hobby_category_id に変更
    hobby_category_id = Column(Integer, ForeignKey("hobby_categories.id", ondelete="CASCADE"))
    
    # 地域タグ（投稿者の居住地を自動付与）
    region_tag_pref = Column(String(50), index=True, nullable=True)
    region_tag_city = Column(String(100), index=True, nullable=True)
    
    # Meet upイベント用フラグ
    is_meetup = Column(Boolean, default=False)
    meetup_date = Column(DateTime, nullable=True)
    meetup_location = Column(String(200), nullable=True)
    meetup_capacity = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="hobby_posts")
    # 【修正】hobby_group を hobby_category に変更
    hobby_category = relationship("HobbyCategory", back_populates="posts")
    responses = relationship("PostResponse", back_populates="post", cascade="all, delete-orphan")

# 投稿への返信（PostResponse）
class PostResponse(Base):
    __tablename__ = "post_responses"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    post_id = Column(Integer, ForeignKey("hobby_posts.id", ondelete="CASCADE"), nullable=True)
    
    content = Column(Text, nullable=True)
    is_participation = Column(Boolean, default=False) # Meet up参加表明
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="post_responses")
    post = relationship("HobbyPost", back_populates="responses")

# ==========================================
# 💡 4. 通知モデル (HobbyCategoryへの告知機能に対応)
# ==========================================

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 💡 修正: 通知対象のユーザーID（宛先）を追加
    recipient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False) 
    
    # 通知の送信元（投稿者やシステム）
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # この通知がどのカテゴリ階層への告知かを示す (Meetupの地域フィルタリングなど用)
    hobby_category_id = Column(Integer, ForeignKey("hobby_categories.id", ondelete="CASCADE"), nullable=False)
    
    message = Column(Text, nullable=False)
    
    # 関連する MeetUp イベントの ID 
    event_post_id = Column(Integer, ForeignKey("hobby_posts.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # リレーション
    # 🚨 修正点: 'foreign_keys' を指定し、recipient_id のみが User モデルを参照することを明確化
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="notifications_received") 
    sender = relationship("User", foreign_keys=[sender_id])
    hobby_category = relationship("HobbyCategory", backref="notifications_sent_to") 
    event_post = relationship("HobbyPost")

# ==========================================
# 💡 6. 感情ログ (Mood Log) - 軽量化設計
# ==========================================

class MoodLog(Base):
    __tablename__ = "mood_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    
    # 感情タイプ（プリセットから選択）
    mood_type = Column(SQLEnum(MoodType), nullable=False)
    
    # ひとことコメント（任意）
    comment = Column(String(200), nullable=True)
    
    # 公開設定
    is_visible = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="mood_logs")

# ==========================================
# 💡 7. 既存の管理機能モデル (店舗・予約・決済)
# ==========================================

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE")) 
    plan_type = Column(SQLEnum(SubscriptionPlan), nullable=False)
    stripe_subscription_id = Column(String, unique=True, nullable=True) 
    status = Column(String(50), default="active") 
    next_billing_date = Column(Date, nullable=True) 
    user = relationship("User", back_populates="subscriptions")

class Branch(Base):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    address = Column(String, nullable=True)
    max_capacity = Column(Integer, nullable=False, default=50) 
    hourly_base_fee = Column(Float, nullable=False, default=300.0)
    events = relationship("Event", back_populates="branch")

class EventRegistration(Base):
    __tablename__ = "event_registrations"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True) 
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    registered_at = Column(DateTime, default=datetime.now) 
    user = relationship("User", back_populates="event_registrations")
    event = relationship("Event", back_populates="registrations")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    capacity = Column(Integer, nullable=False, default=12) 
    creator_price = Column(Integer, nullable=False, default=0)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    owner = relationship("User", back_populates="owned_events")
    branch = relationship("Branch", back_populates="events") 
    registrations = relationship("EventRegistration", back_populates="event", cascade="all, delete-orphan") 

class Seat(Base):
    __tablename__ = "seats"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True)
    location = Column(String(100)) 
    seat_type = Column(String(50), default="flexible") 
    price_per_hour = Column(Float, default=500.0) 
    reservations = relationship("Reservation", back_populates="seat")

class AccessLog(Base):
    __tablename__ = "access_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    user = relationship("User", back_populates="access_logs")

class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE")) 
    seat_id = Column(Integer, ForeignKey("seats.id", ondelete="CASCADE")) 
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(20), default="active") 
    user = relationship("User", back_populates="reservations")
    seat = relationship("Seat", back_populates="reservations")

class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE")) 
    billing_start_date = Column(Date, nullable=False)
    billing_end_date = Column(Date, nullable=False)
    total_amount = Column(Float, default=0.0)
    status = Column(String(50), default="pending") 
    payment_date = Column(DateTime, nullable=True) 
    user = relationship("User", back_populates="invoices")

# ==========================================
# 💡 8. ユーザーモデル (User) - 全統合版
# ==========================================

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 基本情報
    public_code = Column(String(7), unique=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(120), unique=True, index=True)
    hashed_password = Column(String(255))
    is_company = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # SNS用プロフィール
    nickname = Column(String(100), unique=True, index=True, nullable=True) 
    prefecture = Column(String(50), index=True, nullable=True)
    city = Column(String(100), index=True, nullable=True)
    town = Column(String(100), index=True, nullable=True)

    hobby_categories = relationship("UserHobbyLink", back_populates="user")
    hobby_posts = relationship("HobbyPost", back_populates="user")
    post_responses = relationship("PostResponse", back_populates="user")

    requests_sent = relationship(
        "FriendRequest",
        foreign_keys="FriendRequest.requester_id",
        back_populates="requester",
        cascade="all, delete-orphan"
    )

    requests_received = relationship(
        "FriendRequest",
        foreign_keys="FriendRequest.receiver_id",
        back_populates="receiver",
        cascade="all, delete-orphan"
    )
    
    friendships = relationship("Friendship", foreign_keys="Friendship.user_id")
    follows = relationship("Follow")    
    # --- 1. 入推しとSNSリンク ---

    # 💡 新規追加: 入推しとSNSリンク (出力用)
    oshi_page_url = Column(String(255), nullable=True) # 💡 Columnを使用し、型をStringに
    facebook_url = Column(String(255), nullable=True)
    x_url = Column(String(255), nullable=True)
    instagram_url = Column(String(255), nullable=True)
    note_url = Column(String(255), nullable=True)    
    # 💡 新規追加: 自己紹介とプライバシー設定フラグ
    bio = Column(Text, nullable=True)
    is_member_count_visible = Column(Boolean, default=True) # 人数情報の公開
    is_pref_visible = Column(Boolean, default=True)         # 都道府県の公開
    is_city_visible = Column(Boolean, default=True)          # 区市の公開
    is_town_visible = Column(Boolean, default=True)          # Townの公開
    is_notification_visible = Column(Boolean, default=True)  # 通知情報の公開 (関わっている通知)
    
    # 現在の感情状態（最新のMood Logから自動更新）
    current_mood = Column(SQLEnum(MoodType), default=MoodType.NEUTRAL) 
    current_mood_comment = Column(String(200), nullable=True)
    mood_updated_at = Column(DateTime, nullable=True)
    is_mood_visible = Column(Boolean, default=True)
    
    # リレーションシップ
    # 管理機能系
    subscriptions = relationship("UserSubscription", back_populates="user")
    access_logs = relationship("AccessLog", back_populates="user")
    reservations = relationship("Reservation", back_populates="user")
    invoices = relationship("Invoice", back_populates="user")
    owned_events = relationship("Event", back_populates="owner")
    event_registrations = relationship("EventRegistration", back_populates="user", cascade="all, delete-orphan")
    
    # SNS系
    hobby_categories = relationship("UserHobbyLink", back_populates="user")
    hobby_posts = relationship("HobbyPost", back_populates="user")
    post_responses = relationship("PostResponse", back_populates="user")
    
    # 🚨 修正点: Notification リレーションの外部キーを明確に指定
    notifications_received = relationship(
        "Notification", 
        back_populates="recipient", 
        foreign_keys="[Notification.recipient_id]", 
        cascade="all, delete-orphan"
    )
    
    # 感情ログ（最新3ヶ月/1000件まで保持）
    mood_logs = relationship("MoodLog", back_populates="user", order_by="desc(MoodLog.created_at)")
    