import enum
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Date, Text, 
    Enum as SQLEnum, PrimaryKeyConstraint, UniqueConstraint 
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base 
from datetime import datetime

# ==========================================
# 💡 1. Enum定義 (定数)
# ==========================================

class SubscriptionPlan(str, enum.Enum):
    BASE_MEMBERSHIP = "base_membership"
    MONTHLY_TABLE = "monthly_table"
    TEN_DAY_TABLE = "ten_day_table"

class HobbyRoleType(str, enum.Enum):
    DOERS = "doers"
    FANS = "fans"

class MoodType(str, enum.Enum):
    HAPPY = "happy"
    EXCITED = "excited"
    CALM = "calm"
    TIRED = "tired"
    SAD = "sad"
    ANXIOUS = "anxious"
    ANGRY = "angry"
    NEUTRAL = "neutral"
    GRATEFUL = "grateful"
    MOTIVATED = "motivated"

class FriendRequestStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

# ==========================================
# 💡 2. SNS・コミュニティ機能モデル
# ==========================================

class Community(Base):
    __tablename__ = "communities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    owner = relationship("User", back_populates="communities")

class HobbyCategory(Base):
    __tablename__ = "hobby_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), index=True, nullable=False)
    alias_name = Column(String, nullable=True)
    parent_id = Column(Integer, ForeignKey('hobby_categories.id'), nullable=True)
    depth = Column(Integer, nullable=False, default=0)
    master_id = Column(Integer, ForeignKey('hobby_categories.id'), nullable=True)
    unique_code = Column(String(7), unique=True, index=True, nullable=False) 
    role_type = Column(SQLEnum(HobbyRoleType), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_public = Column(Boolean, default=False)
    
    parent = relationship(
        "HobbyCategory", 
        remote_side=[id], 
        backref="children", 
        uselist=False,
        foreign_keys=[parent_id]
    )
    
    master = relationship(
        "HobbyCategory", 
        remote_side=[id], 
        foreign_keys=[master_id],
        backref="aliases"
    )
    
    members = relationship(
        "UserHobbyLink", 
        back_populates="hobby_category", 
        cascade="all, delete-orphan",
        foreign_keys="[UserHobbyLink.hobby_category_id]"
    )
    posts = relationship("HobbyPost", back_populates="hobby_category")

class UserHobbyLink(Base):
    __tablename__ = "user_hobby_links"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    hobby_category_id = Column(Integer, ForeignKey("hobby_categories.id", ondelete="CASCADE"), nullable=False)
    master_id = Column(Integer, ForeignKey("hobby_categories.id"), nullable=False, index=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="hobby_categories")
    hobby_category = relationship(
        "HobbyCategory", 
        back_populates="members",
        foreign_keys=[hobby_category_id]
    )
    
    __table_args__ = (
        UniqueConstraint('user_id', 'master_id', name='unique_user_master_entry'),
    )

class CategoryDetail(Base):
    __tablename__ = "category_details"
    
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("hobby_categories.id", ondelete="CASCADE"), unique=True)
    description = Column(Text, nullable=True)
    cast_json = Column(Text, nullable=True)
    sections_json = Column(Text, nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    category = relationship("HobbyCategory")
    editor = relationship("User", foreign_keys=[updated_by])

class Follow(Base):
    __tablename__ = "follows"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(Integer, nullable=False)
    target_type = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User")
    
    __table_args__ = (UniqueConstraint('user_id', 'target_id', 'target_type', name='unique_follow'),)

class Friendship(Base):
    __tablename__ = "friendships"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    friend_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    friend_note = Column(String(100), nullable=True)
    is_muted = Column(Boolean, default=False, nullable=False)
    is_hidden = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])
    friend = relationship("User", foreign_keys=[friend_id])

    __table_args__ = (UniqueConstraint("user_id", "friend_id", name="unique_friendship"),)

class FriendRequest(Base):
    __tablename__ = "friend_requests"
    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(SQLEnum(FriendRequestStatus), default=FriendRequestStatus.PENDING, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    requester = relationship("User", foreign_keys=[requester_id], back_populates="requests_sent")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="requests_received")

    __table_args__ = (UniqueConstraint('requester_id', 'receiver_id', name='_requester_receiver_uc'),)

# ==========================================
# 💡 3. 投稿機能 (HobbyPost)
# ==========================================

class HobbyPost(Base):
    __tablename__ = "hobby_posts"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    hobby_category_id = Column(Integer, ForeignKey("hobby_categories.id", ondelete="CASCADE"), nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    parent_id = Column(Integer, ForeignKey("hobby_posts.id", ondelete="CASCADE"), nullable=True)

    region_tag_pref = Column(String(50), index=True, nullable=True)
    region_tag_city = Column(String(100), index=True, nullable=True)
    
    # --- MeetUp関連 ---
    is_meetup = Column(Boolean, default=False, nullable=False)
    meetup_date = Column(DateTime, nullable=True)
    meetup_location = Column(String(200), nullable=True)
    meetup_capacity = Column(Integer, nullable=True)
    meetup_fee_info = Column(Text, nullable=True)
    meetup_status = Column(String(20), default="open", nullable=False)
    
    # --- 広告・リポスト関連 ---
    is_ad = Column(Boolean, default=False, nullable=False)
    is_hidden = Column(Boolean, default=False, nullable=False)  
    ad_color = Column(String(20), nullable=True, default="green")
    ad_start_date = Column(DateTime, nullable=True)
    ad_end_date = Column(DateTime, nullable=True)
    original_post_id = Column(Integer, ForeignKey("hobby_posts.id", ondelete="SET NULL"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # --- リレーションシップ ---
    user = relationship("User", back_populates="hobby_posts")
    hobby_category = relationship("HobbyCategory", back_populates="posts")
    responses = relationship("PostResponse", back_populates="post", cascade="all, delete-orphan")
    meetup_messages = relationship("MeetupMessage", back_populates="post", cascade="all, delete-orphan")

    parent = relationship("HobbyPost", remote_side=[id], foreign_keys=[parent_id], backref="children_posts")
    original_post = relationship("HobbyPost", remote_side=[id], foreign_keys=[original_post_id], backref="reposts")

class UserAdInteraction(Base):
    __tablename__ = "user_ad_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("hobby_posts.id", ondelete="CASCADE"), nullable=False)
    is_liked = Column(Boolean, default=False)
    is_pinned = Column(Boolean, default=False)
    is_closed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    
    __table_args__ = (UniqueConstraint('user_id', 'post_id', name='uq_user_ad'),)

class PostResponse(Base):
    __tablename__ = "post_responses"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("hobby_posts.id", ondelete="CASCADE"), nullable=False)
    
    content = Column(Text, nullable=True)
    is_participation = Column(Boolean, default=False, nullable=False)
    is_attended = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="post_responses")
    post = relationship("HobbyPost", back_populates="responses")
    
    __table_args__ = (UniqueConstraint('user_id', 'post_id', name='unique_user_post_response'),)

class MeetupMessage(Base):
    __tablename__ = "meetup_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("hobby_posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    author_nickname = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    post = relationship("HobbyPost", back_populates="meetup_messages")
    user = relationship("User")
    # ✅ 追加：リアクションとのリレーション
    reactions = relationship(
        "MeetupMessageReaction",
        back_populates="message",
        cascade="all, delete-orphan"
    )

# ==========================================
# 💡 3-b. MeetupMessageReaction（新規追加）
# ==========================================

class MeetupMessageReaction(Base):
    __tablename__ = "meetup_message_reactions"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(
        Integer,
        ForeignKey("meetup_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    reaction = Column(String(10), nullable=False)   # 絵文字文字列（例: "✅"）
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    message = relationship("MeetupMessage", back_populates="reactions")
    user = relationship("User")

    __table_args__ = (
        # 同じユーザーが同じメッセージに同じ絵文字を重複登録しない
        UniqueConstraint("message_id", "user_id", "reaction", name="uq_meetup_reaction"),
    )

# ==========================================
# 💡 4. 通知・感情・その他
# ==========================================

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False) 
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    hobby_category_id = Column(Integer, ForeignKey("hobby_categories.id", ondelete="CASCADE"), nullable=False)
    message = Column(Text, nullable=False)
    event_post_id = Column(Integer, ForeignKey("hobby_posts.id", ondelete="SET NULL"), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="notifications_received") 
    sender = relationship("User", foreign_keys=[sender_id])
    hobby_category = relationship("HobbyCategory") 
    event_post = relationship("HobbyPost")

class MoodLog(Base):
    __tablename__ = "mood_logs"
    
    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    mood_type  = Column(SQLEnum(MoodType), nullable=False)
    comment    = Column(String(200), nullable=True)
    category   = Column(String(50), nullable=True)   # ← NEW: タグ名を文字列で保存
    is_visible = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="mood_logs")


# ──────────────────────────────────────────
# 【追加1】UserTag テーブル（新規追加）
# MoodLog クラスの直後に配置
# ──────────────────────────────────────────

class UserTag(Base):
    """ユーザーが MY PAGE 編集モードで登録する「よく使うタグ」"""
    __tablename__ = "user_tags"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    label      = Column(String(30), nullable=False)
    color      = Column(String(20), default="gray", nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="user_tags")

    __table_args__ = (
        UniqueConstraint("user_id", "label", name="uq_user_tag_label"),
    )

# ==========================================
# 💡 5. 管理機能モデル (店舗・予約・決済)
# ==========================================

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_type = Column(SQLEnum(SubscriptionPlan), nullable=False)
    stripe_subscription_id = Column(String(255), unique=True, nullable=True)
    status = Column(String(50), default="active", nullable=False)
    next_billing_date = Column(Date, nullable=True) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="subscriptions")

class Branch(Base):
    __tablename__ = "branches"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    address = Column(String(200), nullable=True)
    max_capacity = Column(Integer, nullable=False, default=50) 
    hourly_base_fee = Column(Float, nullable=False, default=300.0)
    
    events = relationship("Event", back_populates="branch")

class EventRegistration(Base):
    __tablename__ = "event_registrations"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True) 
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="event_registrations")
    event = relationship("Event", back_populates="registrations")

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True, nullable=False)
    description = Column(Text, nullable=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    capacity = Column(Integer, nullable=False, default=12) 
    creator_price = Column(Integer, nullable=False, default=0)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owner = relationship("User", back_populates="owned_events")
    branch = relationship("Branch", back_populates="events") 
    registrations = relationship("EventRegistration", back_populates="event", cascade="all, delete-orphan") 

class Seat(Base):
    __tablename__ = "seats"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    location = Column(String(100), nullable=True) 
    seat_type = Column(String(50), default="flexible", nullable=False)
    price_per_hour = Column(Float, default=500.0, nullable=False)
    
    reservations = relationship("Reservation", back_populates="seat")

class AccessLog(Base):
    __tablename__ = "access_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="access_logs")

class Reservation(Base):
    __tablename__ = "reservations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    seat_id = Column(Integer, ForeignKey("seats.id", ondelete="CASCADE"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(20), default="active", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="reservations")
    seat = relationship("Seat", back_populates="reservations")

class Invoice(Base):
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    billing_start_date = Column(Date, nullable=False)
    billing_end_date = Column(Date, nullable=False)
    total_amount = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), default="pending", nullable=False)
    payment_date = Column(DateTime, nullable=True) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="invoices")

# ==========================================
# 💡 6. ユーザーモデル (User)
# ==========================================

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    public_code = Column(String(8), unique=True, index=True, nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_company = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    birth_year_month = Column(String(7), nullable=True)
    gender = Column(String(20), nullable=True)
    is_stats_visible = Column(Boolean, default=True, nullable=False)
    nickname = Column(String(100), unique=True, index=True, nullable=True) 
    prefecture = Column(String(50), index=True, nullable=True)
    city = Column(String(100), index=True, nullable=True)
    town = Column(String(100), index=True, nullable=True)

    bio = Column(Text, nullable=True)
    oshi_page_url = Column(String(255), nullable=True)
    facebook_url = Column(String(255), nullable=True)
    x_url = Column(String(255), nullable=True)
    instagram_url = Column(String(255), nullable=True)
    note_url = Column(String(255), nullable=True)

    is_member_count_visible = Column(Boolean, default=True, nullable=False)
    is_pref_visible = Column(Boolean, default=True, nullable=False)
    is_city_visible = Column(Boolean, default=True, nullable=False)
    is_town_visible = Column(Boolean, default=True, nullable=False)
    is_notification_visible = Column(Boolean, default=True, nullable=False)
    
    is_restricted = Column(Boolean, default=False, nullable=False)
    report_count = Column(Integer, default=0, nullable=False)

    current_mood = Column(SQLEnum(MoodType), default=MoodType.NEUTRAL, nullable=False)
    current_mood_comment = Column(String(200), nullable=True)
    mood_updated_at = Column(DateTime, nullable=True)
    is_mood_comment_visible = Column(Boolean, default=False, nullable=False)
    is_mood_visible = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    subscriptions = relationship("UserSubscription", back_populates="user")
    access_logs = relationship("AccessLog", back_populates="user")
    reservations = relationship("Reservation", back_populates="user")
    invoices = relationship("Invoice", back_populates="user")
    owned_events = relationship("Event", back_populates="owner")
    event_registrations = relationship("EventRegistration", back_populates="user", cascade="all, delete-orphan")
    mood_logs = relationship("MoodLog", back_populates="user", order_by="desc(MoodLog.created_at)")
    
    hobby_categories = relationship("UserHobbyLink", back_populates="user")
    hobby_posts = relationship("HobbyPost", back_populates="user")
    post_responses = relationship("PostResponse", back_populates="user")
    
    requests_sent = relationship("FriendRequest", foreign_keys="FriendRequest.requester_id", back_populates="requester", cascade="all, delete-orphan")
    requests_received = relationship("FriendRequest", foreign_keys="FriendRequest.receiver_id", back_populates="receiver", cascade="all, delete-orphan")
    follows = relationship("Follow", overlaps="user")

    user_tags = relationship(
        "UserTag", back_populates="user",
        order_by="UserTag.sort_order",
        cascade="all, delete-orphan"
    )

    paid_friend_slots = Column(Integer, default=0)
    is_premium = Column(Boolean, default=False)

    communities = relationship("Community", back_populates="owner")
    friendships = relationship("Friendship", back_populates="user", foreign_keys="[Friendship.user_id]", overlaps="user")
    notifications_received = relationship(
        "Notification", 
        back_populates="recipient", 
        foreign_keys="[Notification.recipient_id]", 
        cascade="all, delete-orphan"
    )

# ==========================================
# 💡 7. 安全機能 (Report / Block)
# ==========================================

class PostReport(Base):
    __tablename__ = "post_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("hobby_posts.id", ondelete="CASCADE"), nullable=False)
    reason = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    reporter = relationship("User", foreign_keys=[reporter_id])
    post = relationship("HobbyPost")
    
    __table_args__ = (UniqueConstraint('reporter_id', 'post_id', name='unique_report_per_user'),)

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")