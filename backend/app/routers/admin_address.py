from fastapi import APIRouter
from ..database import get_db

router = APIRouter(prefix="/admin/address", tags=["admin_address"])

# -----------------------
# 都道府県追加
# -----------------------
@router.post("/prefecture")
def add_prefecture(name: str):
    db = get_db()
    db.execute("INSERT INTO prefectures (name) VALUES (?)", (name,))
    db.commit()
    return {"status": "ok", "message": f"{name} を登録しました"}


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
