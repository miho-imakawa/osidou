from pydantic import BaseModel
from typing import Optional

# ログイン時のレスポンストークン
class Token(BaseModel):
    access_token: str
    token_type: str

# 💡 security.py で使用するトークンの中身のデータ構造もここに追加
class TokenData(BaseModel):
    username: Optional[str] = None # JWTの 'sub' クレームに対応