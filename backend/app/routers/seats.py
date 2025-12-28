# C:\E-Basho\backend\app\routers\seats.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models # modelsとschemasをインポート
from ..database import get_db
from ..schemas.seats import SeatCreate, SeatRead

# ルーターを定義。プレフィックスは main.py で /seats に設定済みと仮定
router = APIRouter() 

# ------------------------------------
# 1. 座席の新規作成 (Create) - 管理者専用を想定
# ------------------------------------
@router.post("/", response_model=SeatRead, status_code=status.HTTP_201_CREATED, tags=["sdmin:seats"])
# 💡 修正: response_model=SeatRead (直接インポートした名前を使う)
def create_seat(seat_in: SeatCreate, db: Session = Depends(get_db)):
    # 💡 ToDo: ここに管理者権限チェックの依存性注入が必要です
    
    # DBに同じ名前の座席がないかチェック
    existing_seat = db.query(models.Seat).filter(models.Seat.name == seat_in.name).first()
    if existing_seat:
        raise HTTPException(status_code=400, detail="この名前の座席は既に登録されています。")
        
    # DBモデルの作成と保存
    db_seat = models.Seat(**seat_in.model_dump())
    db.add(db_seat)
    db.commit()
    db.refresh(db_seat)
    return db_seat

# ------------------------------------
# 2. 全座席の取得 (Read All) - ユーザーが予約時に参照する
# ------------------------------------
@router.get("/", response_model=list[SeatRead], tags=["seats"])
# 💡 修正: response_model=list[SeatRead]
def read_all_seats(db: Session = Depends(get_db)):
    seats = db.query(models.Seat).all()
    return seats
    
# 💡 ToDo: update_seat, delete_seat なども追加可能