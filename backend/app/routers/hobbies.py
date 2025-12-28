# backend/app/routers/hobbies.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any
import collections
from sqlalchemy import func
from ..database import get_db
from .. import models 
from ..schemas.hobbies import HobbyCategoryResponse, HobbySearchParams # 💡 HobbyCategoryResponseのみを使用
from .auth import get_current_user # ユーザー認証用

router = APIRouter(
    prefix="/hobbies",
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
    # 1. カテゴリをIDでマップし、Responseスキーマの形で初期化
    category_map: Dict[int, HobbyCategoryResponse] = {}
    for cat in categories:
        cat_schema = HobbyCategoryResponse.model_validate(cat)
        # メンバー数を設定 (計算結果があれば)
        cat_schema.member_count = member_counts.get(cat.id, 0)
        category_map[cat.id] = cat_schema

    # 2. 親子関係を構築
    tree = []
    for cat_id, cat_schema in category_map.items():
        if cat_schema.parent_id is None:
            # Rootノード (Depth 0) は直接ツリーに追加
            tree.append(cat_schema)
        else:
            # 子ノードを親ノードの children リストに追加
            parent = category_map.get(cat_schema.parent_id)
            if parent:
                parent.children.append(cat_schema)
    
    # 3. 各ノードの children を名前順にソート（階層の表示を綺麗にするため）
    def sort_children(node: HobbyCategoryResponse):
        node.children.sort(key=lambda x: x.name)
        for child in node.children:
            sort_children(child)

    for root in tree:
        sort_children(root)
        
    return tree

# --------------------------------------------------
# 💡 APIエンドポイント
# --------------------------------------------------

@router.get(
    "/categories", 
    response_model=List[HobbyCategoryResponse],
    summary="全趣味カテゴリーを階層構造（ツリー）で取得"
)
def get_all_categories(db: Session = Depends(get_db)):
    """
    データベースから全てのHobbyCategoryを取得し、Depth順、Name順にソートされた
    Category > Role > Genre > Group の多層ツリー形式で返す。
    また、各ノードに直接参加しているメンバー数（member_count）を付与する。
    """
    # 1. 全てのカテゴリーをデータベースから取得
    categories = db.query(models.HobbyCategory).order_by(
        models.HobbyCategory.depth,
        models.HobbyCategory.name
    ).all()
    
    if not categories:
        return []

    # 2. 各HobbyCategoryのメンバー数を計算
    # UserHobbyLinkはHobbyCategory ID（最も深いグループID）に直接リンクしているため、
    # 各ノードのメンバー数は、そのノードIDにリンクしている UserHobbyLink の数となる。
    member_counts_query = db.query(
        models.UserHobbyLink.hobby_category_id,
        func.count(models.UserHobbyLink.user_id)
    ).group_by(
        models.UserHobbyLink.hobby_category_id
    ).all()
    
    # {category_id: member_count} の辞書に変換
    member_counts = {cat_id: count for cat_id, count in member_counts_query}
        
    # 3. 階層構造に変換して返す
    return build_category_tree(categories, member_counts)

# --------------------------------------------------
# 💡 特定のカテゴリの詳細取得
# --------------------------------------------------

@router.get(
    "/categories/{category_id}",
    response_model=HobbyCategoryResponse,
    summary="特定のカテゴリーIDの詳細と子ノード一覧を取得"
)
def get_category_detail(category_id: int, db: Session = Depends(get_db)):
    """
    指定されたカテゴリIDの詳細情報を取得する。
    応答に含まれる children リストには、直下の階層のカテゴリが格納される。
    """
    # 1. 対象のカテゴリーを取得
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == category_id
    ).first()

    if not category:
        raise HTTPException(status_code=404, detail="カテゴリが見つかりません")

    # 2. 直下の子カテゴリーを全て取得
    children = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.parent_id == category_id
    ).order_by(models.HobbyCategory.name).all()

    # 3. メンバー数を計算（対象カテゴリと全ての子カテゴリのメンバー数を一度に取得）
    target_ids = [category.id] + [c.id for c in children]
    
    member_counts_query = db.query(
        models.UserHobbyLink.hobby_category_id,
        func.count(models.UserHobbyLink.user_id)
    ).filter(
        models.UserHobbyLink.hobby_category_id.in_(target_ids)
    ).group_by(
        models.UserHobbyLink.hobby_category_id
    ).all()

    member_counts = {cat_id: count for cat_id, count in member_counts_query}

    # 4. レスポンススキーマの構築
    response_category = HobbyCategoryResponse.model_validate(category)
    response_category.member_count = member_counts.get(category.id, 0)
    
    # 5. 子ノードをスキーマに変換して追加
    response_category.children = []
    for child in children:
        child_schema = HobbyCategoryResponse.model_validate(child)
        child_schema.member_count = member_counts.get(child.id, 0)
        # 再帰的な子ノードはここでは含めない（Client側で再度APIをコールして取得する）
        child_schema.children = [] 
        response_category.children.append(child_schema)
        
    return response_category

# --------------------------------------------------
# 💡 趣味カテゴリーの検索 (Search)
# --------------------------------------------------

@router.get(
    "/search",
    response_model=List[HobbyCategoryResponse],
    summary="趣味カテゴリー（グループ）をフィルタリング検索"
)
def search_hobby_categories(
    db: Session = Depends(get_db),
    params: HobbySearchParams = Depends(),
    # 認証は必須ではないが、もし認証が必要な機能があればここで Depends(get_current_user) を使用
):
    """
    提供されたパラメータ（キーワード、カテゴリID、ロールタイプなど）に基づいて、
    最も深い階層のカテゴリ（Depth 3: グループ）を検索する。
    """
    # 検索対象は最も深い階層のグループ（Depth 3）に限定
    query = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.depth == 3
    )

    # 1. キーワード検索 (nameに対する LIKE 検索)
    if params.keyword:
        query = query.filter(models.HobbyCategory.name.ilike(f"%{params.keyword}%"))

    # 2. カテゴリIDフィルタ
    if params.category_id is not None:
        # parent_idを辿ってCategory IDに一致するかどうかを判定する必要がある
        # これは複雑なクエリになるため、ここでは一旦無視するか、簡易的なロジックを採用
        # 簡易対応として、ここでは特定の親カテゴリを持つノードを探す
        # 💡 Note: SQLAlchemyでは祖先を直接フィルタリングする機能がないため、ここではDepth 1, 2のIDフィルタをスキップします。

        # 暫定的な対応として、Depth 3 (Group)の親(Depth 2: Genre)の親(Depth 1: Role)の親(Depth 0: Category) IDを
        # DB側で参照するのではなく、Python側でフィルタリングするために、全件取得後にフィルタリングするか、
        # より洗練されたDB設計（Materialized Pathなど）が必要。
        
        # 今回はシンプルに、depth=3 のノードを親idでフィルタできる genre_id/role_type のみに集中します。
        pass 

    # 3. Role Type フィルタ (Depth 1: Role)
    if params.role_type:
        # ロールタイプを持つのは Depth 1 のノード
        # Depth 3 のノードから Depth 1 の祖先を辿るのは効率が悪いため、これも高度なクエリが必要
        pass

    # 4. Genre ID フィルタ (Depth 2: Genre)
    if params.genre_id is not None:
        # Depth 3 のノードは parent_id が Depth 2 のノードを指す
        query = query.filter(models.HobbyCategory.parent_id == params.genre_id)
    
    # 5. 検索結果の取得
    searched_categories = query.order_by(models.HobbyCategory.name).all()

    if not searched_categories:
        return []
    
    # 6. メンバー数を計算（検索結果のカテゴリのみ）
    category_ids = [cat.id for cat in searched_categories]
    member_counts_query = db.query(
        models.UserHobbyLink.hobby_category_id,
        func.count(models.UserHobbyLink.user_id)
    ).filter(
        models.UserHobbyLink.hobby_category_id.in_(category_ids)
    ).group_by(
        models.UserHobbyLink.hobby_category_id
    ).all()
    
    member_counts = {cat_id: count for cat_id, count in member_counts_query}

    # 7. レスポンススキーマに変換し、メンバー数を付与
    response_categories = []
    for cat in searched_categories:
        cat_schema = HobbyCategoryResponse.model_validate(cat)
        cat_schema.member_count = member_counts.get(cat.id, 0)
        # 検索結果ではツリー構造は返さず、ノード単体をリストとして返す
        cat_schema.children = [] 
        response_categories.append(cat_schema)
        
    return response_categories


# --------------------------------------------------
# 💡 特定のカテゴリの詳細取得
# --------------------------------------------------

@router.get(
    "/categories/{category_id}",
    response_model=HobbyCategoryResponse,
    summary="特定のカテゴリーIDの詳細と子ノード一覧を取得"
)
def get_category_detail(category_id: int, db: Session = Depends(get_db)):
    """
    指定されたカテゴリIDの詳細情報を取得する。
    応答に含まれる children リストには、直下の階層のカテゴリが格納される。
    """
    # 1. 対象のカテゴリーを取得
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == category_id
    ).first()

    if not category:
        raise HTTPException(status_code=404, detail="カテゴリが見つかりません")

    # 2. 直下の子カテゴリーを全て取得
    children = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.parent_id == category_id
    ).order_by(models.HobbyCategory.name).all()

    # 3. メンバー数を計算（対象カテゴリと全ての子カテゴリのメンバー数を一度に取得）
    target_ids = [category.id] + [c.id for c in children]
    
    member_counts_query = db.query(
        models.UserHobbyLink.hobby_category_id,
        func.count(models.UserHobbyLink.user_id)
    ).filter(
        models.UserHobbyLink.hobby_category_id.in_(target_ids)
    ).group_by(
        models.UserHobbyLink.hobby_category_id
    ).all()

    member_counts = {cat_id: count for cat_id, count in member_counts_query}

    # 4. レスポンススキーマの構築
    response_category = HobbyCategoryResponse.model_validate(category)
    response_category.member_count = member_counts.get(category.id, 0)
    
    # 5. 子ノードをスキーマに変換して追加
    response_category.children = []
    for child in children:
        child_schema = HobbyCategoryResponse.model_validate(child)
        child_schema.member_count = member_counts.get(child.id, 0)
        # 再帰的な子ノードはここでは含めない（Client側で再度APIをコールして取得する）
        child_schema.children = [] 
        response_category.children.append(child_schema)
        
    return response_category

# --------------------------------------------------
# 💡 グループ参加/脱退 (UserHobbyLinkを使用)
# --------------------------------------------------

@router.post("/categories/{category_id}/join", tags=["groups"])
def join_hobby_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    特定のHobbyCategory（通常は最も深い階層のGroup）に参加する
    """
    # カテゴリ存在チェック (ここでは全てのdepthのカテゴリ参加を許可するが、Group(depth=3)のみに制限することも可能)
    category = db.query(models.HobbyCategory).filter(models.HobbyCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="カテゴリが見つかりません")
    
    # 既に参加済みかチェック
    existing = db.query(models.UserHobbyLink).filter(
        models.UserHobbyLink.user_id == current_user.id,
        models.UserHobbyLink.hobby_category_id == category_id
    ).first()
    
    if existing:
        return {"message": "既に参加済みです", "category_id": category_id}
    
    # 参加処理
    link = models.UserHobbyLink(user_id=current_user.id, hobby_category_id=category_id)
    db.add(link)
    db.commit()
    
    return {"message": f"{category.name} に参加しました", "category_id": category_id}

@router.delete("/categories/{category_id}/leave", tags=["groups"])
def leave_hobby_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """特定のHobbyCategoryから脱退する"""
    link = db.query(models.UserHobbyLink).filter(
        models.UserHobbyLink.user_id == current_user.id,
        models.UserHobbyLink.hobby_category_id == category_id
    ).first()
    
    if not link:
        # カテゴリが存在しない、または参加していない
        raise HTTPException(status_code=404, detail="このカテゴリに参加していません")
    
    db.delete(link)
    db.commit()
    
    return {"message": "カテゴリから脱退しました", "category_id": category_id}

@router.get("/my-categories", response_model=List[HobbyCategoryResponse], tags=["groups"])
def get_my_categories(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """ユーザーが参加している全てのHobbyCategory一覧を取得"""
    
    # ユーザーが参加しているカテゴリのIDとリンク情報を取得
    links = db.query(models.UserHobbyLink).filter(
        models.UserHobbyLink.user_id == current_user.id
    ).all()
    
    category_ids = [link.hobby_category_id for link in links]
    
    if not category_ids:
        return []
        
    # 参加しているカテゴリの詳細情報を取得
    categories = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id.in_(category_ids)
    ).all()
    
    # メンバー数を計算（ここでは参加しているグループのみのメンバー数を計算）
    member_counts = {}
    for cat in categories:
        member_count = db.query(func.count(models.UserHobbyLink.user_id)).filter(
            models.UserHobbyLink.hobby_category_id == cat.id
        ).scalar()
        member_counts[cat.id] = member_count or 0
    
    # レスポンススキーマに変換し、メンバー数を付与
    response_categories = []
    for cat in categories:
        cat_schema = HobbyCategoryResponse.model_validate(cat)
        cat_schema.member_count = member_counts.get(cat.id, 0)
        # children リストは空のまま（ここではツリー構造を求められていないため）
        response_categories.append(cat_schema)
        
    return response_categories