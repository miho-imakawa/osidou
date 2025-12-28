# C:\E-Basho\backend\app\routers\events.py (新規作成)

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models # DBモデル
from datetime import datetime, timedelta
from ..database import get_db # DBセッション
from ..utils.security import get_current_user # 認証済みユーザー取得
from ..schemas.events import (
    EventCreate,
    EventResponse,
    EventRegistrationResponse,
)
from typing import List

router = APIRouter(
    tags=["events & networking"]
)

# ------------------------------------
# 1. イベントの新規作成 (Create Event)
# ------------------------------------
@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    event_in: EventCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """新規イベント作成"""

    branch = db.query(models.Branch).filter(models.Branch.id == event_in.branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="指定された店舗が見つかりません。")

    if event_in.capacity > branch.max_capacity:
        raise HTTPException(
            status_code=400, 
            detail=f"イベント定員({event_in.capacity})が最大収容人数({branch.max_capacity})を超えています。"
        )

    db_event = models.Event(
        owner_id=current_user.id,
        title=event_in.title,
        description=event_in.description,
        branch_id=event_in.branch_id,
        capacity=event_in.capacity,
        start_time=event_in.start_time,
        end_time=event_in.end_time,
        creator_price=event_in.creator_price
    )

    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    # 料金計算
    duration = db_event.end_time - db_event.start_time
    duration_hours = duration.total_seconds() / 3600
    branch_fee = branch.hourly_base_fee * duration_hours
    total_fee = branch_fee + db_event.creator_price

    return EventResponse(
        id=db_event.id,
        title=db_event.title,
        description=db_event.description,
        branch_id=db_event.branch_id,
        capacity=db_event.capacity,
        start_time=db_event.start_time,
        end_time=db_event.end_time,
        owner_id=db_event.owner_id,
        creator_price=db_event.creator_price,

        total_participant_fee=round(total_fee, 2),
        branch_hourly_fee=branch.hourly_base_fee,
        duration_hours=round(duration_hours, 2)
    )

# ------------------------------------
# 2. イベントの一覧取得 (Read All Events) - 料金計算ロジックを含む
# ------------------------------------
@router.get("/", response_model=List[EventResponse])
def read_all_events(db: Session = Depends(get_db)):
    """開催予定のすべてのイベントを取得します。（料金計算済み）"""
    
    db_events = db.query(models.Event).order_by(models.Event.start_time).all()
    
    response_list: List[EventResponse] = []
    
    # 💡 全てのイベントに対して料金計算を実行
    for db_event in db_events:
        
        # 1. Branch 情報を取得 (料金計算に必要)
        branch = db.query(models.Branch).filter(models.Branch.id == db_event.branch_id).first()
        if not branch:
            # 店舗情報が見つからない場合はスキップするか、エラーを出す
            continue 

        BRANCH_HOURLY_FEE = branch.hourly_base_fee 
        
        # 2. イベント時間と総額を計算
        duration: timedelta = db_event.end_time - db_event.start_time
        duration_hours = duration.total_seconds() / 3600
        
        branch_fee = BRANCH_HOURLY_FEE * duration_hours
        total_fee = branch_fee + db_event.creator_price
        
        # 3. 
        event_read = EventResponse(
            # DBから直接取得できるフィールド
            id=db_event.id,
            title=db_event.title,
            description=db_event.description,
            branch_id=db_event.branch_id,
            capacity=db_event.capacity,
            start_time=db_event.start_time,
            end_time=db_event.end_time,
            owner_id=db_event.owner_id,
            creator_price=db_event.creator_price,
            
            # 💡 計算フィールド
            total_participant_fee=round(total_fee, 2),
            branch_hourly_fee=BRANCH_HOURLY_FEE,
            duration_hours=round(duration_hours, 2)
        )
        response_list.append(event_read)
        
    return response_list

# ... (register_for_event 関数が続く) ...
    
# ------------------------------------
# 3. イベントへの参加登録 (Register for Event)
# ------------------------------------
@router.post("/{event_id}/register", response_model=EventRegistrationResponse)
def register_for_event(
    event_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """認証済みユーザーが指定されたイベントに参加登録します。"""
    
    # 1. イベントの存在確認
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="指定されたイベントが見つかりません。")
    
    # 💡 ToDo: イベントの存在確認、二重登録チェックロジックが必要
    
    # 参加登録レコードの作成
    registration = models.EventRegistration(
        user_id=current_user.id,
        event_id=event_id
    )

# 💡 3. イベントの定員チェック
    current_registrations_count = db.query(models.EventRegistration).filter(
        models.EventRegistration.event_id == event_id
    ).count()

    if current_registrations_count >= event.capacity:
        raise HTTPException(
            status_code=409, 
            detail=f"イベントの募集定員({event.capacity}人)に達しています。"
        )

    db.add(registration)
    db.commit()
    # db.refresh(registration) # 中間テーブルのため不要
    
    return EventRegistrationResponse(user_id=current_user.id, event_id=event_id)