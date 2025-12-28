from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, date, timedelta # 💡 datetime, date, timedelta をインポート

from .. import models # DBモデル
from ..database import get_db # DBセッション
from ..utils.security import get_current_user, get_admin_user # 認証機能
# 💡 修正: InvoiceRead と SubscriptionResponse のみを使用
from ..schemas.invoices import (
    InvoiceCreate, InvoiceRead, 
    SubscriptionCreate, SubscriptionResponse
)

router = APIRouter(prefix="/invoices", tags=["invoices"])

# ------------------------------------
# 💡 1. Subscription (サブスクリプション) 管理 - 管理者専用
# ------------------------------------

@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED, summary="新規サブスクリプションの作成（管理者専用）")
def create_subscription(
    sub_in: SubscriptionCreate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(get_admin_user) # 💡 管理者権限チェック
):
    """新しいユーザーのサブスクリプションを登録します。"""
    
    # ユーザー存在チェック
    user = db.query(models.User).filter(models.User.id == sub_in.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="指定されたユーザーが見つかりません。")
        
    # 重複チェック (プランタイプとユーザーの組み合わせでユニーク性を確保することも可能だが、ここでは単純に登録)
    
    db_sub = models.UserSubscription(**sub_in.model_dump())
    db.add(db_sub)
    db.commit()
    db.refresh(db_sub)
    return db_sub

@router.get("/subscriptions", response_model=List[SubscriptionResponse], summary="全サブスクリプション一覧を取得（管理者専用）")
def read_all_subscriptions(
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(get_admin_user) # 💡 管理者権限チェック
):
    """全てのサブスクリプション情報を取得します。"""
    subs = db.query(models.UserSubscription).all()
    return subs

# ------------------------------------
# 💡 2. Invoice (請求書) 管理 - 管理者専用
# ------------------------------------

@router.post("/", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED, summary="新しい請求書を作成（管理者専用）")
def create_invoice(
    invoice_in: InvoiceCreate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(get_admin_user) # 💡 管理者権限チェック
):
    """新しい請求書を登録します。"""
    
    # ユーザー存在チェック
    user = db.query(models.User).filter(models.User.id == invoice_in.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="指定されたユーザーが見つかりません。")
        
    db_invoice = models.Invoice(**invoice_in.model_dump())
    db.add(db_invoice)
    db.commit()
    db.refresh(db_invoice)
    return db_invoice

@router.get("/", response_model=List[InvoiceRead], summary="全請求書一覧を取得（管理者専用）")
def read_all_invoices(
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(get_admin_user) # 💡 管理者権限チェック
):
    """全ての請求書情報を取得します。"""
    invoices = db.query(models.Invoice).order_by(desc(models.Invoice.billing_end_date)).all()
    return invoices

@router.get("/{invoice_id}", response_model=InvoiceRead, summary="特定の請求書の詳細を取得（管理者専用）")
def read_invoice(invoice_id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(get_admin_user)):
    """特定のIDの請求書情報を取得します。"""
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="請求書が見つかりません")
    return invoice

# ------------------------------------
# 💡 3. Invoice (請求書) - ユーザー自身
# ------------------------------------

@router.get("/me", response_model=List[InvoiceRead], summary="自分の請求書一覧を取得")
def read_my_invoices(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """認証済みユーザー自身の請求書一覧を取得します。"""
    invoices = db.query(models.Invoice).filter(
        models.Invoice.user_id == current_user.id
    ).order_by(desc(models.Invoice.billing_end_date)).all()
    return invoices