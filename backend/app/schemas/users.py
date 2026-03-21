from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

from .. import models # MoodType などの Enum を参照するため

# ==========================================
# 💡 1. ユーザー登録・更新用スキーマ
# ==========================================

class UserBase(BaseModel):
    """ユーザーの基本情報（登録・閲覧共通）"""
    username: str = Field(min_length=3, max_length=50, description="ユーザー名")
    email: EmailStr = Field(description="メールアドレス")
    nickname: Optional[str] = Field(None, max_length=100, description="表示名/ニックネーム")

class UserCreate(UserBase):
    """新規登録時に受け取るデータ"""
    password: str = Field(min_length=8, description="パスワード")

class UserProfileUpdate(BaseModel): 
    """PUT /users/me で使用される更新可能なフィールド"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    nickname: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8) # パスワード変更（ハッシュ化はルーターで処理）

    # 住所情報
    prefecture: Optional[str] = None
    city: Optional[str] = None
    town: Optional[str] = None

    #Birth, Gender
    birth_year_month: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}$", description="YYYY-MM形式")
    gender: Optional[str] = Field(None, description="male, female, other, prefer_not_to_say")

    # プロフィール情報
    bio: Optional[str] = None 
    oshi_page_url: Optional[str] = None
    
    # 💡 修正: 公開設定フラグ (入力用)
    is_mood_visible: Optional[bool] = None # 👈 これを追加！
    is_member_count_visible: Optional[bool] = None
    is_pref_visible: Optional[bool] = None
    is_city_visible: Optional[bool] = None
    is_town_visible: Optional[bool] = None
    is_notification_visible: Optional[bool] = None

    # SNSリンク
    facebook_url: Optional[str] = Field(None, max_length=255, description="Facebook URL")
    x_url: Optional[str] = Field(None, max_length=255, description="X (Twitter) URL")
    instagram_url: Optional[str] = Field(None, max_length=255, description="Instagram URL")
    note_url: Optional[str] = Field(None, max_length=255, description="note URL")
    threads_url: Optional[str] = Field(None, max_length=255, description="Threads URL")
# ==========================================
# 💡 2. 感情ログ（Mood Log）スキーマ
# ==========================================

class MoodLogCreate(BaseModel): 
    """今日の気分登録 (POST /me/mood) 用の入力スキーマ"""
    # 💡 型を Enum (models.MoodType) に指定
    mood_type: models.MoodType = Field(description="感情タイプ (Enum)") 
    comment: Optional[str] = Field(None, max_length=200, description="ひとことコメント")
    
class MoodLogResponse(BaseModel):
    """気分履歴データ (GET /{user_id}/mood-history) 用の出力スキーマ"""
    id: int
    # 💡 型を str に指定 (JSONシリアライズ用)
    mood_type: str 
    comment: Optional[str]
    is_visible: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 💡 3. DBから返すユーザー情報
# ==========================================

class UserPublic(BaseModel):
    """3-1. 他人閲覧用の公開プロフィール (GET /users/{id})"""
    id: int
    nickname: Optional[str] = None
    
    # SNS用プロフィール
    bio: Optional[str] = None
    
    # 感情ステータス
    current_mood: Optional[str] = None 
    current_mood_comment: Optional[str] = None
    mood_updated_at: Optional[datetime] = None
    is_mood_visible: bool = True # 感情ログの公開設定
    
    # 💡 新規追加: 公開設定フラグ (出力用)
    is_member_count_visible: bool
    is_pref_visible: bool
    is_city_visible: bool
    is_town_visible: bool

    # 💡 新規追加: 入推しとSNSリンク (出力用)
    oshi_page_url: Optional[str] = None
    facebook_url: Optional[str] = None
    x_url: Optional[str] = None
    instagram_url: Optional[str] = None
    note_url: Optional[str] = None
    threads_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class UserMe(UserPublic):
    """3-2. ログインユーザー本人用の全情報 (GET /users/me)"""
    email: EmailStr
    username: str
    is_active: bool

    # 💡 追加：自分のプロフィール確認・編集画面で表示するために必要
    birth_year_month: Optional[str] = None
    gender: Optional[str] = None

    # 住所情報（本人にのみ返す）
    prefecture: Optional[str] = None
    city: Optional[str] = None
    town: Optional[str] = None

# ==========================================
# 💡 4. 通知スキーマ
# ==========================================

class NotificationResponse(BaseModel):
    id: int
    recipient_id: int # 通知対象ユーザー
    sender_id: int   # 送信者
    hobby_category_id: int # 関連カテゴリ
    message: str     # 通知メッセージ
    event_post_id: Optional[int] = None # 関連投稿ID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)