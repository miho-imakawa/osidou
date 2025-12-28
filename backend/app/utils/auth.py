# app/utils/auth.py
from typing import Optional
from datetime import datetime, timedelta

from passlib.context import CryptContext
from jose import jwt, JWTError

# JWT settings (本番では環境変数から読み込むこと)
SECRET_KEY = "YOUR-SUPER-SECRET-AND-COMPLEX-KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # デフォルト30分

# passlib 設定 (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt は 72 バイト制限があるので安全に切り詰める
def _truncate_to_72_bytes(text: str) -> str:
    b = text.encode("utf-8")[:72]
    return b.decode("utf-8", errors="ignore")

def hash_password(password: str) -> str:
    safe = _truncate_to_72_bytes(password)
    return pwd_context.hash(safe)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    safe = _truncate_to_72_bytes(plain_password)
    try:
        return pwd_context.verify(safe, hashed_password)
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
