from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # 既存の名前を変更
    conn.execute(text("UPDATE hobby_categories SET name = '🏠 HOME' WHERE id = 815"))
    conn.execute(text("UPDATE hobby_categories SET name = '💬 コミュニティ | COMMUNITY' WHERE id = 816"))
    conn.execute(text("UPDATE hobby_categories SET name = '👥 ともだち | FRIENDS' WHERE id = 817"))
    conn.execute(text("UPDATE hobby_categories SET name = '📧 Contact (お問い合わせ)' WHERE id = 818"))
    
    # How to walk the osidou を削除（不要なので）
    conn.execute(text("DELETE FROM hobby_categories WHERE id = 814"))
    
    # MY PAGE を新規追加
    conn.execute(text("""
        INSERT INTO hobby_categories (name, parent_id, depth, is_public, unique_code)
        VALUES ('👤 MY PAGE', 813, 1, 1, 'G_MYPAGE')
    """))
    
    conn.commit()
    print("完了")