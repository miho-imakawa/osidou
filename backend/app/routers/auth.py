# app/routers/auth.py
import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime

# Local imports
from .. import models # app/models.py
from ..database import get_db

# ✅ スキーマのインポート: schemasディレクトリ内のファイルからインポート
from ..schemas.auth import Token, TokenData # JWT関連
from ..schemas.users import UserCreate, UserMe, UserPublic # ユーザー登録/取得関連

# ✅ security.py から認証関連の関数/定数をインポート
# security.pyは utils/security.py に移動済み
from ..utils.auth import generate_public_code
from ..utils.security import (
    authenticate_user,
    create_access_token,
    # 💡 修正のため、デバッグ用のget_current_userを一時的に定義（本来はsecurity.pyにあります）
    # get_current_userはユーザーモジュールで利用するため、ここではsecurity.py内のそのままを使用
    get_current_user,
    get_password_hash, # ユーザー登録用に追加
    # 💡 修正: ACCESS_TOKEN_EXPIRE_MINUTESをインポート
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(tags=["auth"])

# ユーザー登録エンドポイント
@router.post("/register", response_model=UserMe, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    try:
        # 既存ユーザー確認
        existing = db.query(models.User).filter(models.User.email == user_in.email).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="このメールアドレスは既に使われています。")

        existing_username = db.query(models.User).filter(models.User.username == user_in.username).first()
        if existing_username:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="このユーザー名は既に使われています。")
        
        # 1. パスワードをハッシュ化して変数に格納
        hashed_password = get_password_hash(user_in.password) 
        
        # 2. DBモデルを作成
        db_user = models.User(
            username=user_in.username,
            email=user_in.email,
            hashed_password=hashed_password,
            public_code=generate_public_code(),
            is_active=True,
        )

        # 3. DBに保存
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        # ↓ここから追加（ウェルカムメール）
        # ウェルカムメール送信
        try:
            import httpx
            from ..utils.email import welcome_email_html
            with httpx.Client(timeout=5.0) as client:
                client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {os.getenv('RESEND_API_KEY')}"},
                    json={
                        "from": "system@osidou.com",
                        "to": db_user.email,
                        "subject": "推し道へようこそ！",
                        "html": welcome_email_html(db_user.username),
                    },
                )
        except Exception as e:
            print(f"ウェルカムメール送信エラー: {e}")

        return db_user
        
    except HTTPException as http_e:
        raise http_e
    except Exception as e:
        # その他の予期せぬエラー
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登録時に予期せぬ問題が発生しました: {e}"
        )


# JWTトークンを発行するためのエンドポイント
@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザー名またはパスワードが間違っています",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
   # 💡 修正: トークンの有効期限を大幅に延長 (例: 1日 = 24 * 60分)
    # ACCESS_TOKEN_EXPIRE_MINUTES がデフォルト 30 分の場合、ここでは 1440 分に上書きする
    # 環境変数などを使わない場合は、ここでは定数値を直接設定してテストを容易にする
    TOKEN_EXPIRE_MINUTES = 24 * 60 # 1日 (本番では短く設定してください)
    
    access_token_expires = timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# 認証済みユーザー情報を取得するテストエンドポイント
@router.get("/me", response_model=UserMe)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

import secrets
from datetime import timezone
from ..utils.email import send_email, password_reset_email_html

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://osidou.com")

@router.post("/password-reset-request")
async def password_reset_request(
    email: str,
    db: Session = Depends(get_db)
):
    # ユーザーが存在しなくても同じレスポンスを返す（メアド推測を防ぐ）
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        # 既存の未使用トークンを無効化
        db.query(models.PasswordResetToken).filter(
            models.PasswordResetToken.user_id == user.id,
            models.PasswordResetToken.is_used == False
        ).update({"is_used": True})

        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=1)

        db.add(models.PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
        ))
        db.commit()

        reset_url = f"{FRONTEND_URL}/reset-password?token={token}"
        nickname = user.nickname or user.username
        await send_email(
            to=user.email,
            subject="【推し道】パスワードの再設定",
            html=password_reset_email_html(nickname, reset_url),
        )

    return {"message": "メールアドレスが登録されている場合、再設定メールを送信しました。"}


@router.post("/password-reset")
def password_reset(
    token: str,
    new_password: str,
    db: Session = Depends(get_db)
):
    now = datetime.utcnow().replace(tzinfo=timezone.utc)

    reset_token = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token == token,
        models.PasswordResetToken.is_used == False,
        models.PasswordResetToken.expires_at > now,
    ).first()

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="リンクが無効または期限切れです。再度お試しください。"
        )

    user = db.query(models.User).filter(
        models.User.id == reset_token.user_id
    ).first()

    user.hashed_password = get_password_hash(new_password)
    reset_token.is_used = True
    db.commit()

    return {"message": "パスワードを変更しました。ログインしてください。"}