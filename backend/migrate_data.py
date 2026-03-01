import sqlite3
import uuid
from datetime import datetime

OLD_DB = "osidou_backup.db"
NEW_DB = "osidou.db"

def migrate():
    try:
        old_conn = sqlite3.connect(OLD_DB)
        new_conn = sqlite3.connect(NEW_DB)
        old_conn.row_factory = sqlite3.Row
        old_cursor = old_conn.cursor()
        new_cursor = new_conn.cursor()

        print("🚀 不足データを補完しながら移行を開始します...")

        tables = ["users", "hobby_categories", "hobby_posts", "meetup_messages"]

        for table in tables:
            print(f"--- {table} テーブルを処理中 ---")
            try:
                old_cursor.execute(f"SELECT * FROM {table}")
                rows = old_cursor.fetchall()
            except sqlite3.OperationalError:
                continue

            new_cursor.execute(f"PRAGMA table_info({table})")
            new_columns = {col[1]: col[2] for col in new_cursor.fetchall()} # 型情報も取得

            for row in rows:
                data = dict(row)
                insert_data = {}
                
                for col, col_type in new_columns.items():
                    if col == 'id':
                        insert_data[col] = None
                    elif col == 'public_code' and (not data.get(col)):
                        # 💡 public_codeが空ならランダムな文字列を生成して入れる
                        insert_data[col] = str(uuid.uuid4())[:8]
                    elif col in ['created_at', 'updated_at']:
                        insert_data[col] = data.get(col) or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    elif col in data:
                        # 💡 必須項目がNoneの場合のデフォルト値設定
                        val = data[col]
                        if val is None:
                            if "INTEGER" in col_type: val = 0
                            elif "BOOLEAN" in col_type: val = 0
                            else: val = "" # 文字列型など
                        insert_data[col] = val
                    else:
                        insert_data[col] = 0 if "INTEGER" in col_type else ""

                placeholders = ", ".join(["?"] * len(insert_data))
                columns_str = ", ".join(insert_data.keys())
                sql = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
                new_cursor.execute(sql, list(insert_data.values()))

            print(f"✅ {table}: {len(rows)} 件の移行完了")

        new_conn.commit()
        print("\n✨ エラーを回避して移行に成功しました！")

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
    finally:
        old_conn.close()
        new_conn.close()

if __name__ == "__main__":
    migrate()