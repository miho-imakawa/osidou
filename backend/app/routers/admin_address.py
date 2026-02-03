from fastapi import APIRouter
from ..database import get_db

router = APIRouter(prefix="/admin/address", tags=["admin_address"])

# -----------------------
# 都道府県一覧を取得
# -----------------------
@router.get("/prefectures")
def get_prefectures():
    db = get_db()
    # address.db の prefectures テーブルから全件取得
    rows = db.execute("SELECT id, name FROM prefectures ORDER BY id").fetchall()
    return [{"id": row[0], "name": row[1]} for row in rows]

# -----------------------
# 特定の都道府県に属する市区町村を取得
# -----------------------
@router.get("/cities/{prefecture_id}")
def get_cities(prefecture_id: int):
    db = get_db()
    rows = db.execute(
        "SELECT id, name FROM cities WHERE prefecture_id = ? ORDER BY id",
        (prefecture_id,)
    ).fetchall()
    return [{"id": row[0], "name": row[1]} for row in rows]

# -----------------------
# 市区町村追加
# -----------------------
@router.post("/city")
def add_city(prefecture_id: int, name: str):
    db = get_db()
    db.execute(
        "INSERT INTO cities (prefecture_id, name) VALUES (?, ?)",
        (prefecture_id, name),
    )
    db.commit()
    return {"status": "ok", "message": f"{name} を登録しました"}


# -----------------------
# 表記ゆれ Synonym 追加
# -----------------------
@router.post("/synonym")
def add_synonym(city_id: int, synonym: str, type: str = "other"):
    db = get_db()
    db.execute(
        "INSERT INTO synonyms (city_id, synonym, type) VALUES (?, ?, ?)",
        (city_id, synonym, type),
    )
    db.commit()
    return {"status": "ok", "message": f"{synonym} を登録しました"}

@router.get("/member-count")
def get_member_count(prefecture: str, city: str):
    db = get_db()
    # usersテーブルから、同じ都道府県・市区町村の人数を数える
    # (注意: ここは osidou.db を参照する必要があります)
    count = db.execute(
        "SELECT COUNT(*) FROM users WHERE prefecture = ? AND city = ?",
        (prefecture, city)
    ).fetchone()[0]
    return {"count": count}