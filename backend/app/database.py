from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
# ⚠️ 不要な sqlite3 のインポートを削除しました

# 環境変数をロード (SECRET_KEYやDB_URLなど)
load_dotenv()

# DB_URLはSQLiteファイル名としてdotenvから読み込む
# 例: SQLALCHEMY_DATABASE_URL="sqlite:///./e_basho.db"
SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL", "sqlite:///./osidou.db")

# データベースエンジンの作成
# SQLiteを使用する場合、check_same_thread=False が必須
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# セッション作成のためのクラス
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 全てのモデルの基底クラス
Base = declarative_base()

# ✅ DBセッションを取得するための依存関数 (正しい定義)
def get_db():
    # SessionLocal を使用して SQLAlchemy の Session を作成
    db = SessionLocal()
    try:
        # yield でセッションをルーター関数に渡す
        yield db
    finally:
        # リクエスト処理後にセッションを確実にクローズする
        db.close()

# ⚠️ 重複定義されていた古い get_db() 関数は削除されました