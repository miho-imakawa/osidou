from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

# Local imports (必要に応じて調整)
from ..database import get_db
from ..models import User
from ..schemas.auth import TokenData # スキーマファイルにTokenDataが存在すると仮定

# 認証設定

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # アクセストークンの有効期限

# パスワードハッシュ化の設定
# 💡 修正: デフォルトのスキームを sha256_crypt に変更し、bcryptを予備として残す
pwd_context = CryptContext(schemes=["sha256_crypt", "bcrypt"], deprecated="auto")

# OAuth2 スキームの定義
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/token",
    auto_error=False
)
# --- パスワード関連関数 ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """平文のパスワードとハッシュ化されたパスワードを比較します。"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """パスワードをハッシュ化します。"""
    return pwd_context.hash(password)

# --- JWTトークン関連関数 ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWTアクセストークンを生成します。"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15) # デフォルト値
    
    to_encode.update({"exp": expire, "sub": to_encode["sub"]})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# app/utils/security.py

def decode_access_token(token: str):
    try:
        # 💡 追加: トークンが空の場合は即座にエラーを出すようにしてクラッシュを防ぐ
        if token is None:
            return None
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception: # JWTErrorなど
        return None

# --- ユーザー認証と依存関数 ---

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """ユーザーのメールアドレスとパスワードを検証し、ユーザーオブジェクトを返します。"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password): # Userモデルにhashed_password列があると仮定
        return None
    return user

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """リクエストから認証済みユーザーオブジェクトを取得します。（FastAPIのDependsで使用）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="認証情報が無効です",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = decode_access_token(token)
    if token_data is None:
        raise credentials_exception
    
    # ユーザーをDBから取得
    user = db.query(User).filter(User.email == token_data["sub"]).first()
    if user is None:
        raise credentials_exception
        
    return user

def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    現在のユーザーが管理者 (is_admin=True) であるか確認するデコレーター関数。
    管理者でない場合は403 Forbiddenを返します。
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理者権限が必要です。",
        )
    return current_user

def get_optional_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Optional[User]:
    """ログインしていなくてもエラーにしない任意認証"""
    if not token:
        return None
    token_data = decode_access_token(token)
    if token_data is None:
        return None
    user = db.query(User).filter(User.email == token_data["sub"]).first()
    return user