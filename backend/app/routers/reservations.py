# C:\E-Basho\backend\app\routers\reservations.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, date, time
from .. import models
from ..database import get_db
from ..utils.security import get_current_user # 仮にauth.pyにあると想定
from ..schemas.reservations import ReservationCreate, ReservationRead, ReservationUpdate

router = APIRouter() 

# ------------------------------------
# 1. 新規予約の作成 (Create)
# ------------------------------------
@router.post("/", response_model=ReservationRead, status_code=status.HTTP_201_CREATED, tags=["reservations"])
def create_reservation(
    reservation_in: ReservationCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. 予約期間のバリデーション (開始時刻が未来であるか、終了時刻が開始時刻より後であるか)
    if reservation_in.end_time <= reservation_in.start_time:
        raise HTTPException(
            status_code=400,
            detail="終了時刻は開始時刻よりも後に設定してください。"
        )

    # 2. 💡 予約重複チェックロジック (最重要)
    # 既存のアクティブな予約と、今回リクエストされた予約期間が重複していないか確認します。
    # 重複条件: (リクエスト終了時刻 > 既存の開始時刻) AND (リクエスト開始時刻 < 既存の終了時刻)
    conflicting_reservation = db.query(models.Reservation).filter(
        models.Reservation.seat_id == reservation_in.seat_id,
        models.Reservation.status == "active", # アクティブな予約のみを対象とする
        models.Reservation.end_time > reservation_in.start_time,
        models.Reservation.start_time < reservation_in.end_time
    ).first()

    if conflicting_reservation:
        # 予約が重複していた場合は、競合 (409 Conflict) エラーを返す
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="指定された時間帯に、この座席は既に予約されています。"
        )
        
    # 3. 予約データの作成と保存
    db_reservation = models.Reservation(
        user_id=current_user.id, 
        **reservation_in.model_dump()
    )
    
    db.add(db_reservation)
    db.commit()
    db.refresh(db_reservation)
    return db_reservation

# ------------------------------------
# 2. 自分の予約一覧の取得 (Read My Reservations)
# ------------------------------------
@router.get("/me", response_model=list[ReservationRead], tags=["reservations"])
def read_my_reservations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    reservations = db.query(models.Reservation).filter(
        models.Reservation.user_id == current_user.id
    ).all()
    return reservations

# C:\E-Basho\backend\app\routers\reservations.py (追記)

# 3. 予約のキャンセル (Update Status)
@router.put("/{reservation_id}/cancel", response_model=ReservationRead, tags=["reservations"])
def cancel_reservation(
    reservation_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """予約IDを指定して、予約をキャンセルします。"""
    
    # 1. 予約の検索
    reservation = db.query(models.Reservation).filter(
        models.Reservation.id == reservation_id
    ).first()
    
    if not reservation:
        raise HTTPException(status_code=404, detail="予約が見つかりません。")
        
    # 2. 権限チェック: 自分の予約か確認
    if reservation.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="この予約をキャンセルする権限がありません。")

    # 3. 状態チェック: 既にキャンセル済みでないか
    if reservation.status == "cancelled":
        raise HTTPException(status_code=400, detail="この予約は既にキャンセル済みです。")

    # 4. 💡 キャンセルデッドラインのチェック (当日8:30決済ポリシーの反映)
    
    # 予約開始日を取得
    reservation_date: date = reservation.start_time.date()
    
    # 今日の日付と時刻を取得
    now = datetime.now()
    today_date: date = now.date()
    
    # 決済デッドライン時刻 (当日8時30分)
    PAYMENT_DEADLINE_TIME = time(8, 30, 0) # 8:30:00
    
    # 予約開始日の当日8:30というデッドラインを datetime オブジェクトとして作成
    deadline = datetime.combine(reservation_date, PAYMENT_DEADLINE_TIME)
    
    # 予約当日、かつ、既に8:30を過ぎているかチェック
    if now > deadline and reservation_date == today_date:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="この予約のキャンセル期限（本日8:30）を過ぎています。既に決済処理が行われているため、キャンセルはできません。"
        )
    
    # 5. キャンセルの実行
    reservation.status = "cancelled"
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    
    return reservation