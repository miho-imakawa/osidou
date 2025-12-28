import enum
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from .. import models # DBモデル
from ..database import get_db # DBセッション
from ..schemas.events import BranchCreate, BranchResponse # 💡 events.py に定義されたスキーマを使用
from .auth import get_current_user # 認証機能

# 💡 ルーターを /branches に設定。prefixを付けているため、/branches/〇〇 となる
router = APIRouter(prefix="/branches", tags=["admin:branches"])

# ------------------------------------
# 1. 店舗の新規作成 (Create Branch) - 管理者専用を想定
# ------------------------------------
@router.post("/", response_model=BranchResponse, status_code=status.HTTP_201_CREATED, summary="新しい店舗を作成")
def create_branch(
    branch_in: BranchCreate, 
    db: Session = Depends(get_db),
    # 💡 権限チェックを追加することが望ましい（ここでは省略）
    # current_user: models.User = Depends(get_current_user)
):
    """新しい店舗情報を登録します。（管理者専用）"""
    
    # DBに同じ名前の店舗がないかチェック
    existing_branch = db.query(models.Branch).filter(models.Branch.name == branch_in.name).first()
    if existing_branch:
        raise HTTPException(status_code=400, detail="この名前の店舗は既に登録されています。")
        
    # DBモデルの作成と保存
    db_branch = models.Branch(**branch_in.model_dump())
    db.add(db_branch)
    db.commit()
    db.refresh(db_branch)
    return db_branch

# ------------------------------------
# 2. 全店舗の取得 (Read All Branches)
# ------------------------------------
@router.get("/", response_model=List[BranchResponse], summary="全ての店舗一覧を取得")
def read_all_branches(db: Session = Depends(get_db)):
    """登録されている全ての店舗情報を取得します。"""
    branches = db.query(models.Branch).all()
    return branches

# ------------------------------------
# 3. 特定店舗の詳細取得 (Read Single Branch)
# ------------------------------------
@router.get("/{branch_id}", response_model=BranchResponse, summary="特定の店舗の詳細を取得")
def read_branch(branch_id: int, db: Session = Depends(get_db)):
    """特定のIDの店舗情報を取得します。"""
    branch = db.query(models.Branch).filter(models.Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="店舗が見つかりません")
    return branch

# ------------------------------------
# 4. 店舗情報の更新 (Update Branch)
# ------------------------------------
@router.put("/{branch_id}", response_model=BranchResponse, summary="特定の店舗情報を更新")
def update_branch(
    branch_id: int, 
    branch_in: BranchCreate, # 💡 更新用スキーマも作成可能だが、ここではCreateを使用
    db: Session = Depends(get_db)
):
    """特定のIDの店舗情報を更新します。（管理者専用）"""
    branch = db.query(models.Branch).filter(models.Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="店舗が見つかりません")
    
    # 更新データを適用
    update_data = branch_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(branch, key, value)
        
    db.commit()
    db.refresh(branch)
    return branch

# ------------------------------------
# 5. 店舗の削除 (Delete Branch)
# ------------------------------------
@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT, summary="特定の店舗を削除")
def delete_branch(branch_id: int, db: Session = Depends(get_db)):
    """特定のIDの店舗を削除します。（管理者専用）"""
    branch = db.query(models.Branch).filter(models.Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="店舗が見つかりません")
        
    db.delete(branch)
    db.commit()
    return