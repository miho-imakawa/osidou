import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base

# ルーターのインポート
from .routers import (
    auth, users, access_logs,
    branches, events, reservations,
    invoices,
    hobbies, posts, notifications,
    moods, 
    friend_requests, community,
    meetup_chat  # 💡 1. チャット用ルーターをインポート
)

# データベーステーブルの作成
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="推し道 API (Osidou API)",
    description="推し活コミュニティ「推し道」とコミュニティセンター「推集炉」のバックエンドシステム",
    version="1.0.0",
)

# ✨ CORS設定（二重になっていたものを整理しました）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ルーターの登録 ---

# 認証系
app.include_router(auth.router, prefix="/auth")

# ユーザー系
app.include_router(users.router, prefix="/users") 

# SNS・コミュニティ系
app.include_router(hobbies.router) 
app.include_router(community.router, prefix="/hobby-categories")
app.include_router(posts.router) 
app.include_router(notifications.router)
app.include_router(moods.router, prefix="/users")
app.include_router(friend_requests.router, prefix="/friends")

# 💡 2. MEETUPチャット系ルーターを登録
app.include_router(meetup_chat.router) 

# 店舗・イベント・予約・決済系
app.include_router(branches.router)
app.include_router(events.router) 
app.include_router(reservations.router)
app.include_router(invoices.router)

# アクセスログ
app.include_router(access_logs.router) 

@app.get("/")
def read_root():
    return {"message": "推し道 APIが正常に動作中です"}