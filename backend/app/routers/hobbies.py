# backend/app/routers/hobbies.py (改善版)

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, distinct, func
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
    """
    599人まで500円。
    600人以上は1人1円、かつ下2桁切り捨て。
    """
    if unique_users <= 599:
        return 500
    # 100単位で切り捨て (例: 1289 -> 1200)
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
    """cast_jsonにこのcategory_idが含まれている作品を返す"""
    all_details = db.query(models.CategoryDetail).filter(
        models.CategoryDetail.cast_json.like(f'%"master_id": {category_id}%')
    ).all()
    
    result = []
    # 現在のChatも含める
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
# 💡 カテゴリツリーの構築ヘルパー関数
# --------------------------------------------------

def build_category_tree(
    categories: List[models.HobbyCategory], 
    member_counts: Dict[int, int]
) -> List[HobbyCategoryResponse]:
    """
    フラットなカテゴリリストから入れ子構造のツリーを構築し、メンバー数を付与する。
    """
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
    """
    指定されたカテゴリIDの子孫（children, grandchildren, etc.）のIDをすべて取得
    キャッシュを使って効率化
    """
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

# --- [ 💡 修正：集計ロジックのアップグレード ] ---

def get_total_member_count(db, category, all_categories=None) -> int:
    # PEOPLEトップカテゴリは人数表示しない
    if category.name == "PEOPLE (人物)":
        return "-"
    
    # 子孫IDも含めてカウント（波及させる）
    target_ids = get_all_descendant_ids(category.id, all_categories) if all_categories else [category.id]
    
    count = db.query(func.count(distinct(models.UserHobbyLink.user_id))).filter(
        models.UserHobbyLink.hobby_category_id.in_(target_ids)
    ).scalar() or 0
    
    return count if count > 0 else "-"


# --------------------------------------------------
# 💡 トップレベルのカテゴリ取得
# --------------------------------------------------

@router.get("/top-categories")
def get_top_categories(db: Session = Depends(get_db)):
    global _top_categories_cache, _top_categories_cache_time
    
    # キャッシュが有効なら返す
    if _top_categories_cache and (time.time() - _top_categories_cache_time) < CACHE_TTL:
        return _top_categories_cache
    
    categories = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.parent_id == None,
        models.HobbyCategory.master_id == None
    ).all()
    
    counts = db.query(
        models.UserHobbyLink.hobby_category_id,
        func.count(distinct(models.UserHobbyLink.user_id))
    ).group_by(models.UserHobbyLink.hobby_category_id).all()
    
    count_map = {cat_id: cnt for cat_id, cnt in counts}
    
    result = []
    for cat in categories:
        schema = HobbyCategoryResponse.model_validate(cat)
        schema.member_count = count_map.get(cat.id, 0) or 0
        schema.children = []
        result.append(schema)
    
    # キャッシュに保存
    _top_categories_cache = result
    _top_categories_cache_time = time.time()
    
    return result

# --------------------------------------------------
# 💡 全カテゴリ取得エンドポイント
# --------------------------------------------------

@router.get(
    "",
    response_model=List[HobbyCategoryResponse],
    summary="全カテゴリーを「子孫も含めた合算人数」付きで取得"
)
def get_all_categories(db: Session = Depends(get_db)):
    """
    全カテゴリをツリー構造で返す。
    各カテゴリの member_count には、そのカテゴリとその子孫に参加している
    ユニークなユーザー数が含まれる。
    """
    # 1. 全カテゴリを一度だけ取得
    categories = db.query(models.HobbyCategory).all()
    if not categories:
        return []

    # 2. 各カテゴリのメンバー数を計算（全カテゴリを渡して効率化）
    member_counts = collections.defaultdict(int)
    
    for cat in categories:
        count = get_total_member_count(db, cat, all_categories=categories)
        member_counts[cat.id] = count
    
    # 3. ツリー構造にして返す
    return build_category_tree(categories, member_counts)

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
            models.HobbyCategory.master_id == None  # 本尊のみ
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

    # PEOPLE配下を上位に表示
    response_categories.sort(key=lambda x: 0 if _is_under_people(x, all_categories) else 1)

    return response_categories

def _is_under_people(cat, all_categories, people_id=196):
    """カテゴリがPEOPLE（id=196）配下かどうか判定"""
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
# 💡 カテゴリ詳細取得
# --------------------------------------------------

@router.get(
    "/categories/{category_id}",
    response_model=HobbyCategoryResponse,
    summary="特定のカテゴリーIDの詳細と子ノード一覧を取得"
)
def get_category_detail(category_id: int, db: Session = Depends(get_db)):
    """指定されたカテゴリIDの詳細情報を取得"""
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == category_id
    ).first()

    if not category:
        raise HTTPException(status_code=404, detail="カテゴリが見つかりません")

    # 直下の子カテゴリを取得
    children = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.parent_id == category_id
    ).order_by(models.HobbyCategory.name).all()

    # 全カテゴリを取得（メンバー数計算用）
    all_categories = db.query(models.HobbyCategory).all()
    
    # レスポンススキーマの構築
    response_category = HobbyCategoryResponse.model_validate(category)
    response_category.member_count = get_total_member_count(db, category, all_categories)
    
    # 子ノードをスキーマに変換
    response_category.children = []
    for child in children:
        child_schema = HobbyCategoryResponse.model_validate(child)
        child_schema.member_count = get_total_member_count(db, child, all_categories)
        child_schema.children = []
        response_category.children.append(child_schema)
        
    return response_category

# --------------------------------------------------
# 💡 コミュニティ参加/脱退
# --------------------------------------------------

# backend/app/routers/hobbies.py (join_hobby_category 修正案)

# ✅ 正しいコード
@router.post("/categories/{category_id}/join")
def join_hobby_category(category_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    category = db.query(models.HobbyCategory).get(category_id)
    
    if not category:
        raise HTTPException(status_code=404, detail="カテゴリが見つかりません")
    
    master_id = category.master_id if category.master_id else category.id

    try:
        link = models.UserHobbyLink(
            user_id=current_user.id,
            hobby_category_id=category_id,  # 入口を記録
            master_id=master_id             # 本尊を記録
        )
        db.add(link)
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"message": "このChatにはすでに参加済みです", "master_id": master_id}
    
    return {"message": "コミュニティに参加しました", "category_id": master_id}

@router.delete("/categories/{category_id}/leave", tags=["groups"])
def leave_hobby_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == category_id
    ).first()
    
    # master_idで検索して削除
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
    """自分が参加しているカテゴリ一覧を取得"""
    links = db.query(models.UserHobbyLink).filter(
        models.UserHobbyLink.user_id == current_user.id
    ).all()

    if not links:
        return []

    # master_idで重複排除してからカテゴリ取得
    unique_master_ids = list({l.master_id for l in links})

    categories = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id.in_(unique_master_ids)
    ).all()

    # デバッグ用
    for cat in categories:
        print(f"id={cat.id}, name={cat.name}, master_id={cat.master_id}")

    res = []
    for cat in categories:
        schema = HobbyCategoryResponse.model_validate(cat)
        schema.member_count = get_total_member_count(db, cat, categories)
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
    """既存の似た名前のカテゴリを検索"""
    existing = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.name.ilike(f"%{name}%")
    ).first()

    if existing:
        # 親の情報を辿る
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

@router.get("/categories/{category_id}/detail")
def get_category_detail_info(category_id: int, db: Session = Depends(get_db)):
    # 1. カテゴリ自体の情報を取得
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == category_id
    ).first()
    
    # 2. カテゴリのDETAIL情報を取得
    detail = db.query(models.CategoryDetail).filter(
        models.CategoryDetail.category_id == category_id
    ).first()
    
    # --- 💡 出演作品の逆引きロジック ---
    # 自分のID（または master_id）が cast_json に含まれている作品を探す
    target_id = category.master_id if category and category.master_id else category_id
    appearances = []
    
    # 全ての作品のDetailをチェック（地道にスキャン）
    # ※ 将来的にはSQLのJSON関数で高速化可能ですが、まずはこのロジックで確実に動かします
    all_details = db.query(models.CategoryDetail).all()
    for d in all_details:
        if d.category_id == category_id:
            continue  # 自分自身のDETAILはスキップ
            
        try:
            cast_list = json.loads(d.cast_json or "[]")
            # キャストの中に自分のIDを master_id として持っている人がいるか
            if any(str(c.get('master_id')) == str(target_id) for c in cast_list):
                work_cat = db.query(models.HobbyCategory).filter(models.HobbyCategory.id == d.category_id).first()
                if work_cat:
                    appearances.append({
                        "id": work_cat.id,
                        "name": work_cat.name
                    })
        except:
            continue
    # --- 逆引きここまで ---

    # 基本データの構築
    response_data = {
        "description": detail.description if detail else "",
        "alias": category.alias_name or "" if category else "",
        "cast": json.loads(detail.cast_json or "[]") if detail else [],
        "sections": json.loads(detail.sections_json or "[]") if detail else [],
        "appearances": appearances  # 💡 これをフロントに渡す
    }
    
    return response_data

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
    role_type: Optional[str] = None  # "doer" / "fan" / None

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
        unique_code=str(uuid.uuid4())[:8],  # ★ 追加
        role_type=data.role_type,  # ★追加
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