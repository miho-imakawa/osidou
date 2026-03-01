import sqlite3
from datetime import datetime

def fix_empty_dates():
    conn = sqlite3.connect("osidou.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 修正対象のテーブルとカラム
    targets = {
        "users": ["created_at", "updated_at", "mood_updated_at"],
        "hobby_posts": ["created_at", "updated_at"],
        "meetup_messages": ["created_at"]
    }

    print("🛠️ 空の日付データを修正中...")
    for table, columns in targets.items():
        for col in columns:
            # 空文字('') または NULL のデータを現在の時刻で上書き
            cursor.execute(f"UPDATE {table} SET {col} = ? WHERE {col} = '' OR {col} IS NULL", (now,))
            print(f"✅ {table}.{col} の修正完了")

    conn.commit()
    conn.close()
    print("✨ 修正が完了しました。サーバーを再起動してください。")

if __name__ == "__main__":
    fix_empty_dates()