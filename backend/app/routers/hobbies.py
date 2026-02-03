# backend/app/routers/hobbies.py (改善版)

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, distinct, func
from typing import List, Dict, Set
import collections

from ..database import get_db
from .. import models 
from ..schemas.hobbies import HobbyCategoryResponse, HobbySearchParams
from .auth import get_current_user

router = APIRouter(
    prefix="/hobby-categories",
    tags=["hobbies"],
    responses={404: {"description": "Not found"}},
)

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

def get_total_member_count(
    db: Session, 
    category: models.HobbyCategory,
    all_categories: List[models.HobbyCategory] = None
) -> int:
    """
    本尊・分身・そして『子孫カテゴリ』の人数をすべて合算して返す
    
    Args:
        db: データベースセッション
        category: 対象カテゴリ
        all_categories: 全カテゴリのリスト（パフォーマンス最適化用）
    """
    # 1. 全カテゴリを取得（外部から渡されていない場合のみ）
    if all_categories is None:
        all_categories = db.query(models.HobbyCategory).all()
    
    # 2. 本尊IDを特定
    master_id = category.master_id if category.master_id else category.id
    
    # 3. 子孫IDをすべて取得（再帰的）
    descendant_ids = get_all_descendant_ids(category.id, all_categories)
    
    # 4. 本尊・分身のIDを取得
    linked_ids = [
        c.id for c in all_categories 
        if (c.master_id == master_id or c.id == master_id)
    ]
    
    # 5. すべてのターゲットIDを統合（重複排除）
    target_ids = list(set(descendant_ids + linked_ids))
    
    # 6. ユニークなユーザー数をカウント
    count = db.query(func.count(distinct(models.UserHobbyLink.user_id))).filter(
        models.UserHobbyLink.hobby_category_id.in_(target_ids)
    ).scalar() or 0
    
    return count

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

@router.get(
    "/search",
    response_model=List[HobbyCategoryResponse],
    summary="趣味カテゴリーを全階層から検索"
)
def search_hobby_categories(
    db: Session = Depends(get_db),
    params: HobbySearchParams = Depends(),
):
    """キーワードやジャンルIDでカテゴリを検索"""
    query = db.query(models.HobbyCategory)

    # キーワード検索
    if params.keyword:
        query = query.filter(models.HobbyCategory.name.ilike(f"%{params.keyword}%"))

    # ジャンルIDフィルタ
    if params.genre_id is not None:
        query = query.filter(models.HobbyCategory.parent_id == params.genre_id)
    
    searched_categories = query.order_by(models.HobbyCategory.name).all()
    
    if not searched_categories:
        return []
    
    # 全カテゴリを取得（メンバー数計算用）
    all_categories = db.query(models.HobbyCategory).all()
    
    # メンバー数を計算
    response_categories = []
    for cat in searched_categories:
        cat_schema = HobbyCategoryResponse.model_validate(cat)
        cat_schema.member_count = get_total_member_count(db, cat, all_categories)
        cat_schema.children = []
        response_categories.append(cat_schema)
        
    return response_categories

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

@router.post("/categories/{category_id}/join", tags=["groups"])
def join_hobby_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """カテゴリに参加する"""
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == category_id
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail="カテゴリが見つかりません")
    
    # 本尊IDを取得
    target_id = category.master_id if category.master_id else category.id
    
    # 既に参加済みかチェック
    existing = db.query(models.UserHobbyLink).filter(
        models.UserHobbyLink.user_id == current_user.id,
        models.UserHobbyLink.hobby_category_id == target_id
    ).first()
    
    if existing:
        return {"message": "既に参加済みです", "category_id": target_id}
    
    # 参加登録
    link = models.UserHobbyLink(user_id=current_user.id, hobby_category_id=target_id)
    db.add(link)
    db.commit()
    
    return {"message": "コミュニティに参加しました", "category_id": target_id}

@router.delete("/categories/{category_id}/leave", tags=["groups"])
def leave_hobby_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """カテゴリから脱退する"""
    link = db.query(models.UserHobbyLink).filter(
        models.UserHobbyLink.user_id == current_user.id,
        models.UserHobbyLink.hobby_category_id == category_id
    ).first()
    
    if not link:
        raise HTTPException(status_code=404, detail="このカテゴリに参加していません")
    
    db.delete(link)
    db.commit()
    
    return {"message": "カテゴリから脱退しました", "category_id": category_id}

@router.get("/my-categories", response_model=List[HobbyCategoryResponse], tags=["groups"])
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
    
    categories = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id.in_([l.hobby_category_id for l in links])
    ).all()
    
    # 重複排除：本尊が同じなら1つにまとめる
    unique_map = {}
    for cat in categories:
        mid = cat.master_id if cat.master_id else cat.id
        if mid not in unique_map:
            unique_map[mid] = cat

    # 全カテゴリを取得（メンバー数計算用）
    all_categories = db.query(models.HobbyCategory).all()
    
    res = []
    for cat in unique_map.values():
        schema = HobbyCategoryResponse.model_validate(cat)
        schema.member_count = get_total_member_count(db, cat, all_categories)
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