from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

# 環境変数をロード
load_dotenv()

# 💡 修正：実行場所に関わらず、backend直下のosidou.dbを絶対パスで指定します
# Windowsのパス形式に合わせて、ドライブレターから指定します
SQLALCHEMY_DATABASE_URL = "sqlite:///C:/osidou/backend/osidou.db"

# データベースエンジンの作成
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

# セッション作成のためのクラス
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 全てのモデルの基底クラス
Base = declarative_base()

# ✅ DBセッションを取得するための依存関数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()