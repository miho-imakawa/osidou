# backend/app/routers/hobbies.py (高速化版)

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, distinct, func, text
from sqlalchemy.exc import IntegrityError
from typing import List, Dict, Set, Optional
import collections
import json
from ..database import get_db
from .. import models, schemas 
from ..schemas.hobbies import HobbyCategoryResponse, HobbySearchParams, CategoryDetailBase
from .auth import get_current_user
from pydantic import BaseModel
from functools import lru_cache
import time
from sqlalchemy import text
 

# キャッシュ（5分間有効）
_top_categories_cache = None
_top_categories_cache_time = 0
CACHE_TTL = 300  # 5分

router = APIRouter(
    prefix="/hobby-categories",
    tags=["hobbies"],
    responses={404: {"description": "Not found"}},
)

# 💡 実料金計算ロジック
def calculate_ad_fee(unique_users: int) -> int:
    if unique_users <= 599:
        return 500
    return (unique_users // 100) * 100

class AdQuoteRequest(BaseModel):
    category_ids: list[int]

@router.post("/ad-quote")
async def get_ad_quote(request: AdQuoteRequest, db: Session = Depends(get_db)):
    category_ids = request.category_ids
    
    unique_user_count = db.query(func.count(distinct(models.UserHobbyLink.user_id)))\
        .filter(models.UserHobbyLink.master_id.in_(category_ids))\
        .scalar() or 0
    
    total_user_count = db.query(func.count(models.UserHobbyLink.user_id))\
        .filter(models.UserHobbyLink.master_id.in_(category_ids))\
        .scalar() or 0
    
    fee = calculate_ad_fee(unique_user_count)
    
    return {
        "unique_user_count": unique_user_count,
        "total_user_count": total_user_count,
        "estimated_fee": fee,
        "currency": "JPY"
    }

@router.get("/categories/{category_id}/related")
def get_related_categories(category_id: int, db: Session = Depends(get_db)):
    all_details = db.query(models.CategoryDetail).filter(
        models.CategoryDetail.cast_json.like(f'%"master_id": {category_id}%')
    ).all()
    
    result = []
    current = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == category_id
    ).first()
    if current:
        result.append({"id": current.id, "name": current.name, "member_count": 0})
    
    for detail in all_details:
        cat = db.query(models.HobbyCategory).filter(
            models.HobbyCategory.id == detail.category_id
        ).first()
        if cat and cat.id != category_id:
            result.append({"id": cat.id, "name": cat.name, "member_count": 0})
    
    return result

# --------------------------------------------------
# 💡 ヘルパー関数
# --------------------------------------------------

def build_category_tree(
    categories: List[models.HobbyCategory], 
    member_counts: Dict[int, int]
) -> List[HobbyCategoryResponse]:
    category_map: Dict[int, HobbyCategoryResponse] = {}
    for cat in categories:
        cat_schema = HobbyCategoryResponse.model_validate(cat)
        cat_schema.member_count = member_counts.get(cat.id, 0)
        category_map[cat.id] = cat_schema

    tree = []
    for cat_id, cat_schema in category_map.items():
        if cat_schema.parent_id is None:
            tree.append(cat_schema)
        else:
            parent = category_map.get(cat_schema.parent_id)
            if parent:
                parent.children.append(cat_schema)
    
    def sort_children(node: HobbyCategoryResponse):
        node.children.sort(key=lambda x: x.name)
        for child in node.children:
            sort_children(child)

    for root in tree:
        sort_children(root)
        
    return tree

def get_all_descendant_ids(
    category_id: int, 
    all_categories: List[models.HobbyCategory],
    cache: Dict[int, List[int]] = None
) -> List[int]:
    if cache is None:
        cache = {}
    
    if category_id in cache:
        return cache[category_id]
    
    descendants = [category_id]
    for cat in all_categories:
        if cat.parent_id == category_id:
            descendants.extend(get_all_descendant_ids(cat.id, all_categories, cache))
    
    cache[category_id] = descendants
    return descendants


# ✅ 【高速化】member_count を一括取得するヘルパー
# 子カテゴリのIDリストを受け取り、1回のSQLで全員数を返す
def get_member_counts_bulk(db: Session, category_ids: List[int]) -> Dict[int, int]:
    """
    指定したカテゴリIDリストのmember_countを1回のSQLで一括取得。
    N+1問題を完全に解消する。
    """
    rows = db.query(
        models.UserHobbyLink.master_id,
        func.count(distinct(models.UserHobbyLink.user_id))
    ).filter(
        models.UserHobbyLink.master_id.in_(category_ids)
    ).group_by(
        models.UserHobbyLink.master_id
    ).all()
    
    return {row[0]: row[1] for row in rows}


def get_total_member_count(db, category, all_categories=None) -> int:
    if category.name == "PEOPLE (人物)":
        return 0
    
    target_ids = get_all_descendant_ids(category.id, all_categories) if all_categories else [category.id]
    
    count = db.query(func.count(distinct(models.UserHobbyLink.user_id))).filter(
        models.UserHobbyLink.hobby_category_id.in_(target_ids)
    ).scalar() or 0
    
    return count

###==========================
### TOP CATEGORIES
###==========================

@router.get("/top-categories")
def get_top_categories(db: Session = Depends(get_db)):
    categories = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.parent_id == None,
        models.HobbyCategory.master_id == None
    ).all()

    all_categories = db.query(models.HobbyCategory).all()
    
    counts = dict(
        db.query(
            models.UserHobbyLink.master_id,
            func.count(distinct(models.UserHobbyLink.user_id))
        ).group_by(models.UserHobbyLink.master_id).all()
    )

    result = []
    for cat in categories:
        if cat.name == "PEOPLE（人物）":
            member_count = "-"
        else:
            descendant_ids = get_all_descendant_ids(cat.id, all_categories)
            member_count = sum(counts.get(id, 0) for id in descendant_ids)

        result.append({
            "id": cat.id,
            "name": cat.name,
            "member_count": member_count,
            "children": []
        })
    return result

@router.get("/categories/{category_id}/detail")
def get_category_detail_info(category_id: int, db: Session = Depends(get_db)):
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == category_id
    ).first()

    detail = db.query(models.CategoryDetail).filter(
        models.CategoryDetail.category_id == category_id
    ).first()

    target_id = category.master_id if category and category.master_id else category_id

    matched_details = db.query(models.CategoryDetail).filter(
        models.CategoryDetail.cast_json.like(f'%"master_id": {target_id}%'),
        models.CategoryDetail.category_id != category_id
    ).limit(50).all()

    appearances = []
    for d in matched_details:
        try:
            cast_list = json.loads(d.cast_json or "[]")
            if any(str(c.get('master_id')) == str(target_id) for c in cast_list):
                work_cat = db.query(models.HobbyCategory).filter(
                    models.HobbyCategory.id == d.category_id
                ).first()
                if work_cat:
                    appearances.append({"id": work_cat.id, "name": work_cat.name})
        except:
            continue

    response_data = {
        "description": detail.description if detail else "",
        "alias": category.alias_name or "" if category else "",
        "cast": json.loads(detail.cast_json or "[]") if detail else [],
        "sections": json.loads(detail.sections_json or "[]") if detail else [],
        "appearances": appearances
    }
    return response_data
    

###==========================
### ALL CATEGORIES
###==========================

@router.get("", response_model=List[HobbyCategoryResponse])
def get_all_categories(db: Session = Depends(get_db)):
    categories = db.query(models.HobbyCategory).all()
    
    res = []
    for cat in categories:
        res.append({
            "id": cat.id,
            "name": cat.name,
            "parent_id": cat.parent_id,
            "member_count": 0,
            "children": []
        })
    return res

# --------------------------------------------------
# 💡 カテゴリ検索
# --------------------------------------------------

@router.get("/search", response_model=List[HobbyCategoryResponse])
def search_hobby_categories(
    db: Session = Depends(get_db),
    params: HobbySearchParams = Depends(),
):
    query = db.query(models.HobbyCategory)

    if params.keyword:
        query = query.filter(
            or_(
                models.HobbyCategory.name.ilike(f"%{params.keyword}%"),
                models.HobbyCategory.alias_name.ilike(f"%{params.keyword}%")
            )
        ).filter(
            models.HobbyCategory.master_id == None
        )

    if params.genre_id is not None:
        query = query.filter(models.HobbyCategory.parent_id == params.genre_id)

    searched_categories = query.order_by(models.HobbyCategory.name).all()

    if not searched_categories:
        return []

    all_categories = db.query(models.HobbyCategory).all()

    response_categories = []
    for cat in searched_categories:
        cat_schema = HobbyCategoryResponse.model_validate(cat)
        cat_schema.member_count = get_total_member_count(db, cat, all_categories)
        cat_schema.children = []
        response_categories.append(cat_schema)

    response_categories.sort(key=lambda x: 0 if _is_under_people(x, all_categories) else 1)

    return response_categories

def _is_under_people(cat, all_categories, people_id=196):
    current_id = cat.parent_id
    visited = set()
    while current_id and current_id not in visited:
        if current_id == people_id:
            return True
        visited.add(current_id)
        parent = next((c for c in all_categories if c.id == current_id), None)
        current_id = parent.parent_id if parent else None
    return False

# --------------------------------------------------
# ✅ 【高速化】カテゴリ詳細取得
# --------------------------------------------------

@router.get("/categories/{category_id}", response_model=HobbyCategoryResponse)
def get_category_detail(category_id: int, db: Session = Depends(get_db)):
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == category_id
    ).first()

    if not category:
        raise HTTPException(status_code=404, detail="カテゴリが見つかりません")

    # 全カテゴリを一度だけ取得（N+1対策）
    all_categories = db.query(models.HobbyCategory).all()

    # 全UserHobbyLinkのmaster_idカウントを一括取得
    all_counts = dict(
        db.query(
            models.UserHobbyLink.master_id,
            func.count(distinct(models.UserHobbyLink.user_id))
        ).group_by(models.UserHobbyLink.master_id).all()
    )

    def get_subtree_count(cat_id: int) -> int:
        """指定カテゴリ以下の全子孫のmember_countを合算"""
        descendant_ids = get_all_descendant_ids(cat_id, all_categories)
        return sum(all_counts.get(did, 0) for did in descendant_ids)

    # 直下の子カテゴリを取得
    children = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.parent_id == category_id
    ).order_by(models.HobbyCategory.name).all()

    # 親カテゴリのレスポンス構築（子孫全合算）
    response_category = HobbyCategoryResponse.model_validate(category)
    response_category.member_count = get_subtree_count(category_id)

    # 子カテゴリも同様に子孫全合算
    response_category.children = []
    for child in children:
        child_schema = HobbyCategoryResponse.model_validate(child)
        child_schema.member_count = get_subtree_count(child.id)
        child_schema.children = []
        response_category.children.append(child_schema)

    return response_category

# --------------------------------------------------
# 💡 コミュニティ参加/脱退
# --------------------------------------------------

@router.post("/categories/{category_id}/join")
def join_hobby_category(category_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    category = db.query(models.HobbyCategory).get(category_id)
    
    if not category:
        raise HTTPException(status_code=404, detail="カテゴリが見つかりません")
    
    master_id = category.master_id if category.master_id else category.id

    try:
        link = models.UserHobbyLink(
            user_id=current_user.id,
            hobby_category_id=category_id,
            master_id=master_id
        )
        db.add(link)
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"message": "このChatにはすでに参加済みです", "master_id": master_id}

    # ✅ これだけ追加！
    _notify_region_milestone(
        db=db,
        category_id=master_id,
        category_name=category.name,
        new_user=current_user,
    )
    
    return {"message": "コミュニティに参加しました", "category_id": master_id}

def _notify_region_milestone(db, category_id: int, category_name: str, new_user):
    """
    JOIN後に都道府県・市区町村のメンバー数をチェックし、
    マイルストーン（都道府県50人単位、市区町村10人単位）に
    達したら同コミュニティの同地域メンバー全員に通知する。
    1日1回制限あり。古い通知は置き換え。
    """
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import text

    pref = new_user.prefecture
    city = new_user.city

    checks = []
    if pref:
        checks.append(("prefecture", pref, 50, f"👥 【{category_name}】{pref}のメンバーが{{count}}人に達しました！"))
    if city:
        checks.append(("city", city, 10, f"🏘️ 【{category_name}】{city}のメンバーが{{count}}人に達しました！"))

    for (field, value, threshold, msg_template) in checks:

        # 同地域・同コミュニティのメンバー数を取得
        if field == "prefecture":
            count = db.execute(text("""
                SELECT COUNT(DISTINCT u.id)
                FROM user_hobby_links uhl
                JOIN users u ON u.id = uhl.user_id
                WHERE uhl.master_id = :cat_id
                  AND u.prefecture = :val
            """), {"cat_id": category_id, "val": value}).scalar() or 0
        else:
            count = db.execute(text("""
                SELECT COUNT(DISTINCT u.id)
                FROM user_hobby_links uhl
                JOIN users u ON u.id = uhl.user_id
                WHERE uhl.master_id = :cat_id
                  AND u.city = :val
            """), {"cat_id": category_id, "val": value}).scalar() or 0

        # マイルストーン判定
        if count == 0 or count % threshold != 0:
            continue

        message = msg_template.format(count=count)

        # 同地域・同コミュニティのメンバー全員を取得
        if field == "prefecture":
            target_users = db.execute(text("""
                SELECT DISTINCT u.id
                FROM user_hobby_links uhl
                JOIN users u ON u.id = uhl.user_id
                WHERE uhl.master_id = :cat_id
                  AND u.prefecture = :val
            """), {"cat_id": category_id, "val": value}).fetchall()
        else:
            target_users = db.execute(text("""
                SELECT DISTINCT u.id
                FROM user_hobby_links uhl
                JOIN users u ON u.id = uhl.user_id
                WHERE uhl.master_id = :cat_id
                  AND u.city = :val
            """), {"cat_id": category_id, "val": value}).fetchall()

        since = datetime.now(timezone.utc) - timedelta(hours=24)

        for row in target_users:
            recipient_id = row[0]

            # 1日1回制限：同じコミュニティ×地域の通知が24時間以内にあればスキップ
            recent = db.execute(text("""
                SELECT id FROM notifications
                WHERE recipient_id = :uid
                  AND hobby_category_id = :cat_id
                  AND message LIKE :msg_like
                  AND created_at > :since
                LIMIT 1
            """), {
                "uid": recipient_id,
                "cat_id": category_id,
                "msg_like": f"%{value}%",
                "since": since,
            }).fetchone()

            if recent:
                # 古い通知を置き換え
                db.execute(text("""
                    UPDATE notifications
                    SET message = :msg, is_read = false, created_at = NOW()
                    WHERE id = :nid
                """), {"msg": message, "nid": recent.id})
            else:
                # 新規通知を作成
                db.execute(text("""
                    INSERT INTO notifications
                        (recipient_id, sender_id, hobby_category_id, message, is_read, created_at)
                    VALUES
                        (:uid, :sender, :cat_id, :msg, false, NOW())
                """), {
                    "uid": recipient_id,
                    "sender": new_user.id,
                    "cat_id": category_id,
                    "msg": message,
                })

    db.commit()


@router.delete("/categories/{category_id}/leave", tags=["groups"])
def leave_hobby_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == category_id
    ).first()
    
    master_id = category.master_id if category and category.master_id else category_id
    
    link = db.query(models.UserHobbyLink).filter(
        models.UserHobbyLink.user_id == current_user.id,
        models.UserHobbyLink.hobby_category_id == master_id
    ).first()
    
    if not link:
        raise HTTPException(status_code=404, detail="このカテゴリに参加していません")
    
    db.delete(link)
    db.commit()
    
    return {"message": "カテゴリから脱退しました", "category_id": master_id}

@router.get("/my-communities", response_model=List[HobbyCategoryResponse], tags=["groups"])
def get_my_categories(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    links = db.query(models.UserHobbyLink).filter(
        models.UserHobbyLink.user_id == current_user.id
    ).all()

    if not links:
        return []

    unique_master_ids = list({l.master_id for l in links})

    categories = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id.in_(unique_master_ids)
    ).all()

    # ✅ 一括取得に変更
    counts = get_member_counts_bulk(db, unique_master_ids)

    res = []
    for cat in categories:
        schema = HobbyCategoryResponse.model_validate(cat)
        schema.member_count = counts.get(cat.id, 0)
        res.append(schema)

    return res

# --------------------------------------------------
# 💡 重複チェック
# --------------------------------------------------

@router.get(
    "/check-duplicate",
    response_model=dict,
    summary="新規登録前に似た名前のカテゴリーが存在するかチェック"
)
def check_duplicate_category(
    name: str = Query(..., description="チェックしたいカテゴリー名"),
    db: Session = Depends(get_db)
):
    existing = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.name.ilike(f"%{name}%")
    ).first()

    if existing:
        path_elements = []
        current = existing
        while current.parent and len(path_elements) < 3:
            path_elements.insert(0, current.parent.name)
            current = current.parent
        
        parent_path = " > ".join(path_elements) if path_elements else "トップカテゴリー"

        return {
            "is_duplicate": True,
            "existing_id": existing.id,
            "existing_name": existing.name,
            "parent_path": parent_path,
            "message": f"おや？ '{parent_path}' の下にすでに '{existing.name}' が存在します。"
        }
    
    return {"is_duplicate": False}


@router.put("/categories/{category_id}/detail")
def update_category_detail_info(
    category_id: int,
    data: CategoryDetailBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == category_id
    ).first()
    if category:
        category.alias_name = data.alias

    detail = db.query(models.CategoryDetail).filter(
        models.CategoryDetail.category_id == category_id
    ).first()
    if not detail:
        detail = models.CategoryDetail(category_id=category_id)
        db.add(detail)
    
    detail.description = data.description
    detail.cast_json = json.dumps([c.dict() for c in data.cast], ensure_ascii=False)
    detail.sections_json = json.dumps([s.dict() for s in data.sections], ensure_ascii=False)
    detail.updated_by = current_user.id
    
    db.commit()
    return {"message": "保存しました"}

# Sub Chat作成用スキーマ
class SubCategoryCreate(BaseModel):
    name: str
    parent_id: int
    master_id: Optional[int] = None
    role_type: Optional[str] = None

@router.post("/create-sub", tags=["hobbies"])
def create_sub_category(
    data: SubCategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    parent = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == data.parent_id
    ).first()
    if not parent:
        raise HTTPException(status_code=404, detail="親カテゴリが見つかりません")
    
    existing = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.name == data.name,
        models.HobbyCategory.parent_id == data.parent_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"「{data.name}」はすでに存在します")
    
    new_cat = models.HobbyCategory(
        name=data.name,
        parent_id=data.parent_id,
        master_id=data.master_id,
        depth=(parent.depth or 0) + 1,
        unique_code=str(uuid.uuid4())[:7],
        role_type=data.role_type,
    )
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    
    return {
        "id": new_cat.id,
        "name": new_cat.name,
        "parent_id": new_cat.parent_id,
        "message": f"「{new_cat.name}」を作成しました！"
    }

# --------------------------------------------------
# 💡 開催確定忘れMEETUP取得（主催者向けバナー用）
# --------------------------------------------------
@router.get("/my-unconfirmed-meetups")
def get_my_unconfirmed_meetups(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    自分が主催していて、開催時間を過ぎているのに
    meetup_confirmed_at が NULL のMEETUPを返す。
    HOME・MYPAGEのバナー表示用。
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    rows = db.execute(text("""
        SELECT id, content, meetup_date, hobby_category_id
        FROM hobby_posts
        WHERE user_id = :uid
          AND is_meetup = true
          AND is_hidden = false
          AND meetup_status != 'cancelled'
          AND meetup_confirmed_at IS NULL
          AND meetup_date IS NOT NULL
          AND meetup_date <= :now
          AND meetup_date >= :now - INTERVAL '4 hours'
        ORDER BY meetup_date DESC
    """), {"uid": current_user.id, "now": now}).fetchall()

    return [
        {
            "id": r.id,
            "title": r.content.split('\n')[0],
            "meetup_date": r.meetup_date.isoformat() if r.meetup_date else None,
            "hobby_category_id": r.hobby_category_id,
        }
        for r in rows
    ]