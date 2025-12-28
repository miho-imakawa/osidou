# backend/app/routers/community.py
import enum
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user # auth.pyにある現ユーザー取得関数をインポート

# 💡 ルーターインスタンスには prefix は設定しない（他ルーターとの競合回避のため）
router = APIRouter(tags=["deprecated_community"])

# ------------------------------------------------------------------
# 1. カテゴリ関連 (Category) - 例: 音楽, スポーツ
# ------------------------------------------------------------------
# 💡 修正: CategoryCreate スキーマが存在しないため、ダミーの BaseModel を使用してエラーを回避
class CategoryCreateDummy(schemas.HobbyCategoryResponse):
    pass

# 💡 修正: CategoryResponse -> HobbyCategoryResponse
@router.post("/categories/", response_model=schemas.HobbyCategoryResponse)
# 💡 修正: schemas.CategoryCreate -> CategoryCreateDummy に置き換え、AttributeErrorを回避
def create_category(category: CategoryCreateDummy, db: Session = Depends(get_db)):
    """カテゴリを作成する（管理者用・初期データ投入用）"""
    # 💡 修正: models.Category -> models.HobbyCategory
    db_category = models.HobbyCategory(name=category.name, depth=0) 
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

# 💡 修正: CategoryResponse -> HobbyCategoryResponse
@router.get("/categories/", response_model=List[schemas.HobbyCategoryResponse])
def read_categories(db: Session = Depends(get_db)):
    """全カテゴリを取得"""
    # 💡 修正: models.Category -> models.HobbyCategory
    return db.query(models.HobbyCategory).all()

# ------------------------------------------------------------------
# 2. コミュニティグループ関連 (Groups)
# ------------------------------------------------------------------
# 💡 修正: CommunityGroupResponse/CommunityGroup/UserGroupLink はモデルに存在しないため、
# 💡 Hobbies/Posts ルーターへの移行が完了したとみなし、このセクションはデッドコード化します。

# ------------------------------------------------------------------
# 3. 投稿機能 (Posts)
# ------------------------------------------------------------------
# 💡 修正: CommunityPostResponse/CommunityPost はモデルに存在しないため、
# 💡 posts.py ルーターへの移行が完了したとみなし、このセクションはデッドコード化します。

# ------------------------------------------------------------------
# 4. 【重要】地域グループ自動生成ロジック (Helper Function)
# ------------------------------------------------------------------
# 💡 修正: 既にこのロジックは削除され、posts.py内の check_region_member_limit に移行済みです。
# 💡 この関数が users.py でインポートされている限り、インポートエラーを回避するために関数を残しますが、ロジックは無視されます。

def check_and_create_region_group(db: Session, prefecture: str, city: str):
    """
    ユーザー登録やプロフィール更新時に呼び出されていたが、現在は廃止された関数。
    ロジックは check_region_member_limit に移行済み。
    """
    return # 何も実行しない