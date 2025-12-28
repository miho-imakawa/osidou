from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel # Pydantic BaseModelのインポートを追加

from .. import models 
from ..database import get_db 
# 💡 修正: get_admin_user をインポート
from ..utils.security import get_current_user, get_admin_user 
from ..schemas.access_logs import (
    AccessLogCreate, 
    AccessLogUpdate, 
    AccessLogRead, 
    UsageAnalytics
)


# 💡 💡 💡 ここに APIRouter のインスタンスを定義します 💡 💡 💡
router = APIRouter(
    prefix="/access-logs", # 💡 プレフィックスを - に修正
    tags=["access logs"]
)

# --------------------------------------------------
# 1. 入室ログの作成 (チェックイン)
# --------------------------------------------------
@router.post("/entry", response_model=AccessLogRead, status_code=status.HTTP_201_CREATED, summary="ユーザーの入室を記録（チェックイン）")
def create_entry_log(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """認証済みユーザーの入室を記録します。"""
    
    # 💡 未退室のログが残っていないかチェック
    pending_log = db.query(models.AccessLog).filter(
        models.AccessLog.user_id == current_user.id,
        models.AccessLog.exit_time.is_(None) # None を比較する際は is_() を使用
    ).first()
    
    if pending_log:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="既に入室中です。退室処理を行ってください。"
        )
    
    db_log = models.AccessLog(
        user_id=current_user.id,
        entry_time=datetime.now()
    )

    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    
    return db_log


# --------------------------------------------------
# 2. 退室ログの記録 (チェックアウト)
# --------------------------------------------------
@router.patch("/exit", response_model=AccessLogRead, summary="最後の入室ログに退室時刻を記録（チェックアウト）")
def update_exit_log(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """最新の入室ログに退室時刻を記録します。"""
    
    # ユーザーの未退室ログを検索
    log_to_update = db.query(models.AccessLog).filter(
        models.AccessLog.user_id == current_user.id,
        models.AccessLog.exit_time.is_(None) 
    ).order_by(models.AccessLog.entry_time.desc()).first()
    
    if not log_to_update:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="現在入室中のログが見つかりません。"
        )

    # 退室時刻を更新
    exit_time = datetime.now()
    log_to_update.exit_time = exit_time

    db.add(log_to_update)
    db.commit()
    db.refresh(log_to_update)
    
    # 💡 滞在時間を計算してレスポンスに含める
    duration: timedelta = exit_time - log_to_update.entry_time
    duration_in_minutes = duration.total_seconds() / 60
    
    setattr(log_to_update, 'duration_minutes', round(duration_in_minutes))
    return log_to_update

# --------------------------------------------------
# 3. 自分の利用履歴の取得
# --------------------------------------------------
@router.get("/me", response_model=List[AccessLogRead], summary="自身の全てのアクセスログを取得")
def read_my_access_logs(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """認証済みユーザー自身のすべてのアクセスログを取得します。"""
    
    logs = db.query(models.AccessLog).filter(
        models.AccessLog.user_id == current_user.id
    ).order_by(models.AccessLog.entry_time.desc()).all()

    response_logs = []
    for log in logs:
        duration_minutes = None
        if log.exit_time:
            duration: timedelta = log.exit_time - log.entry_time
            duration_in_minutes = duration.total_seconds() / 60
            duration_minutes = round(duration_in_minutes)
            
        setattr(log, 'duration_minutes', duration_minutes)
        response_logs.append(log)
        
    return response_logs

# --------------------------------------------------
# 4. 💡 新規: 全ログ取得 (管理者専用)
# --------------------------------------------------
@router.get("/", response_model=List[AccessLogRead], summary="全ての入退室ログを取得（管理者専用）")
def get_all_access_logs(
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(get_admin_user), # 💡 管理者権限チェックを適用
    limit: int = Query(100, gt=0, le=500),
    offset: int = Query(0, ge=0)
):
    """
    全てのユーザーの入退室ログを新しい順に取得します。（管理者権限が必要）
    """
    logs = db.query(models.AccessLog).order_by(desc(models.AccessLog.entry_time)).offset(offset).limit(limit).all()
    
    response_logs = []
    for log in logs:
        # 滞在時間を計算してスキーマに追加
        duration_minutes = None
        if log.exit_time:
            duration: timedelta = log.exit_time - log.entry_time
            duration_minutes = int(duration.total_seconds() / 60)
            
        setattr(log, 'duration_minutes', duration_minutes)
        response_logs.append(log)
        
    return response_logs

# --------------------------------------------------
# 5. 自分の利用状況の分析を取得
# --------------------------------------------------
@router.get("/analytics/me", response_model=UsageAnalytics, summary="自身の総利用時間分析を取得")
def get_user_analytics(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """
    認証済みユーザーの総利用時間や平均滞在時間などの分析情報を返します。
    （月間フィルタリングロジックは簡略化しています）
    """
    
    # 1. 退室済みのログ（計算可能なログ）を取得
    completed_logs = db.query(models.AccessLog).filter(
        models.AccessLog.user_id == current_user.id,
        models.AccessLog.exit_time.isnot(None) 
    ).all()

    # データがない場合の初期化
    if not completed_logs:
        return UsageAnalytics(
            total_duration_hours=0.0,
            average_duration_minutes=0.0,
            logs_with_duration=[]
        )

    # 2. 利用時間の計算と集計
    total_duration_seconds = 0.0
    logs_with_duration = []

    for log in completed_logs:
        duration: timedelta = log.exit_time - log.entry_time
        duration_in_minutes = duration.total_seconds() / 60
        total_duration_seconds += duration.total_seconds()
        
        logs_with_duration.append(log)
        
    # 3. 分析結果の集計
    total_duration_hours = total_duration_seconds / 3600
    average_duration_minutes = (total_duration_seconds / 60) / len(completed_logs)

    # 4. 結果を UsageAnalytics スキーマで返却 (logs_with_duration に duration_minutes を動的に付与)
    final_logs = []
    for log in logs_with_duration:
        duration: timedelta = log.exit_time - log.entry_time
        duration_in_minutes = duration.total_seconds() / 60
        setattr(log, 'duration_minutes', round(duration_in_minutes))
        final_logs.append(log)

    return UsageAnalytics(
        total_duration_hours=round(total_duration_hours, 2),
        average_duration_minutes=round(average_duration_minutes, 2),
        logs_with_duration=final_logs
    )