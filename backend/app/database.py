from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,           # 常時キープする接続数
        max_overflow=10,       # 追加で最大10接続まで許可
        pool_pre_ping=True,    # 接続が切れていたら自動再接続
        pool_recycle=300,      # 5分で接続を再利用（タイムアウト防止）
    )
else:
    # ローカル開発：SQLite
    DATABASE_URL = "sqlite:///C:/osidou/backend/osidou.db"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
