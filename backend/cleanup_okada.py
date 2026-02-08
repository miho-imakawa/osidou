import sqlite3

# DBに接続
conn = sqlite3.connect('osidou.db')
cursor = conn.cursor()

try:
    print("🧹 お掃除を開始します...")
    
    # 1. 32番（岡田斗司夫）を独立した本尊にする
    cursor.execute("UPDATE hobby_categories SET parent_id = NULL, master_id = NULL WHERE id = 32")
    
    # 2. 不要になった親の箱（31番）を削除する
    cursor.execute("DELETE FROM hobby_categories WHERE id = 31")
    
    conn.commit()
    print("✨ 岡田斗司夫が一人になりました！")

except Exception as e:
    print(f"❌ エラーが発生しました: {e}")
    conn.rollback()

finally:
    conn.close()
    print("🚪 接続を閉じました。")
    