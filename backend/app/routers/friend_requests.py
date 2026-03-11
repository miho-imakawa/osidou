from pydantic import BaseModel, ConfigDict  # 💡 これを一番上に追加！
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from .. import models, schemas
from ..utils.security import get_current_user
from ..database import get_db

class FriendshipUpdate(BaseModel):
    friend_note: Optional[str] = None
    is_muted: Optional[bool] = None

router = APIRouter(tags=["Friend Requests"])

# -----------------------------------------------------
# 1. フレンド申請の送信
# -----------------------------------------------------
@router.post(
    "/{receiver_id}/friend_request",
    response_model=schemas.FriendRequestBase,
    status_code=status.HTTP_201_CREATED,
)
def send_friend_request(
    receiver_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.id == receiver_id:
        raise HTTPException(
            status_code=400,
            detail="自分自身にフレンド申請はできません。",
        )

    receiver = db.query(models.User).filter(models.User.id == receiver_id).first()
    if not receiver:
        raise HTTPException(
            status_code=404,
            detail="申請先のユーザーが見つかりません。",
        )

    existing_request = (
        db.query(models.FriendRequest)
        .filter(
            models.FriendRequest.requester_id == current_user.id,
            models.FriendRequest.receiver_id == receiver_id,
            models.FriendRequest.status == models.FriendRequestStatus.PENDING,
        )
        .first()
    )

    if existing_request:
        raise HTTPException(status_code=400, detail="既に申請済みです。")

    new_request = models.FriendRequest(
        requester_id=current_user.id,
        receiver_id=receiver_id,
        status=models.FriendRequestStatus.PENDING,
    )

    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request


# -----------------------------------------------------
# 2. 受信したフレンド申請
# -----------------------------------------------------
@router.get(
    "/me/friend-requests",
    response_model=List[schemas.FriendRequestResponse],
)
def get_friend_requests(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.FriendRequest)
        .options(joinedload(models.FriendRequest.requester))
        .filter(
            models.FriendRequest.receiver_id == current_user.id,
            models.FriendRequest.status == models.FriendRequestStatus.PENDING,
        )
        .all()
    )


# -----------------------------------------------------
# 3. フレンド申請の承認 / 拒否
# -----------------------------------------------------
@router.put(
    "/friend_requests/{request_id}/status",
    # response_model=schemas.FriendRequestResponse, # 💡 エラー時も考慮して一度外すか、Unionにするのが一般的です
)
def update_friend_request_status(
    request_id: int,
    payload: schemas.FriendRequestUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    request_obj = (
        db.query(models.FriendRequest)
        .filter(
            models.FriendRequest.id == request_id,
            models.FriendRequest.receiver_id == current_user.id,
        )
        .first()
    )

    if not request_obj:
        raise HTTPException(status_code=404, detail="申請が見つかりません。")

    if request_obj.status != models.FriendRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="既に処理済みです。")

    if payload.status == models.FriendRequestStatus.ACCEPTED:
        
        # 💡 --- ここから人数制限ロジックを追加 ---
        # 1. 現在のともだち人数を数える
        friend_count = db.query(models.Friendship).filter(
            models.Friendship.user_id == current_user.id
        ).count()

        # 2. 上限を計算 (無料10人 + 購入済みスロット)
        allowed_limit = 10 + (current_user.paid_friend_slots or 0)

        # 3. 上限チェック
        if friend_count >= allowed_limit:
            # Mihoさん流：英語圏の人にも一瞬で伝わるスマートな表記
            # 例: 「10 + 1 x Cost ¥100 /Month」
            upgrade_msg = f"{friend_count} + 1 x Cost ¥100 /Month"
            
            # 先ほど定義した箱（FriendLimitResponse）に近い形でエラーを投げます
            raise HTTPException(
                status_code=402, # Payment Required
                detail={
                    "upgrade_msg": upgrade_msg,
                    "current_count": friend_count,
                    "allowed_limit": allowed_limit
                }
            )
        # 💡 --- ここまで追加 ---

        request_obj.status = models.FriendRequestStatus.ACCEPTED
        friendships = [
            models.Friendship(
                user_id=request_obj.requester_id,
                friend_id=request_obj.receiver_id,
                is_muted=False,
                is_hidden=False,
            ),
            models.Friendship(
                user_id=request_obj.receiver_id,
                friend_id=request_obj.requester_id,
                is_muted=False,
                is_hidden=False,
            ),
        ]
        db.add_all(friendships)
        db.commit()

    elif payload.status == models.FriendRequestStatus.REJECTED:
        request_obj.status = models.FriendRequestStatus.REJECTED
        db.commit()

    db.refresh(request_obj)
    return request_obj


# -----------------------------------------------------
# 4. 送信したフレンド申請
# -----------------------------------------------------
@router.get(
    "/me/sent-friend-requests",
    response_model=List[schemas.FriendRequestResponse],
)
def get_sent_friend_requests(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.FriendRequest)
        .options(joinedload(models.FriendRequest.receiver))
        .filter(models.FriendRequest.requester_id == current_user.id)
        .all()
    )


# -----------------------------------------------------
# 5. 自分のフレンド一覧（情報の結合を追加）
# -----------------------------------------------------
@router.get(
    "/me/friends",
    response_model=List[schemas.FriendshipResponse],
)
def get_my_friends(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 💡 相手のユーザー情報(friend)を一緒に読み込むように修正
    friends = (
        db.query(models.Friendship)
        .options(joinedload(models.Friendship.friend)) 
        .filter(models.Friendship.user_id == current_user.id)
        .all()
    )
    return friends

# -----------------------------------------------------
# 6. フレンド表示・ミュート設定
# -----------------------------------------------------
@router.patch("/friends/{friend_id}/status")
def update_friend_relation_status(
    friend_id: int,
    payload: schemas.FriendStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    relation = (
        db.query(models.Friendship)
        .filter(
            models.Friendship.user_id == current_user.id,
            models.Friendship.friend_id == friend_id,
        )
        .first()
    )

    if not relation:
        raise HTTPException(status_code=404, detail="フレンド関係が見つかりません。")

    if payload.action == "hide":
        relation.is_hidden = True
    elif payload.action == "show":
        relation.is_hidden = False
    elif payload.action == "mute":
        relation.is_muted = True
    elif payload.action == "unmute":
        relation.is_muted = False
    else:
        raise HTTPException(status_code=400, detail="無効なアクションです。")

    db.commit()
    return {"message": "更新しました。"}


# -----------------------------------------------------
# 7. フレンドシップのメモ・ミュート更新（修正版）
# -----------------------------------------------------
@router.put("/friendships/{friendship_id}")
def update_friendship(
    friendship_id: int,
    payload: FriendshipUpdate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 1. 編集したい友達関係を探す
    friendship = db.query(models.Friendship).filter(
        models.Friendship.id == friendship_id,
        models.Friendship.user_id == current_user.id
    ).first()

    if not friendship:
        raise HTTPException(status_code=404, detail="関係が見つかりません。")

    # 2. メモ(friend_note)を上書き保存する
    if payload.friend_note is not None:
        friendship.friend_note = payload.friend_note
    
    db.commit() # 💡 ここで実際に保存されます
    return {"message": "保存しました"}


# --- ともだち申請から承認 ---
# --- ともだち申請から承認 カウント ---

@router.get("/pending/count", summary="未承認のフレンド申請数を取得")
def get_pending_friend_requests_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """承認待ち（PENDING）の申請数を返します。"""
    count = db.query(models.FriendRequest).filter(
        models.FriendRequest.receiver_id == current_user.id,
        models.FriendRequest.status == models.FriendRequestStatus.PENDING
    ).count()
    return {"pending_count": count}

# --- ファイルの最後に追加 ---

class FriendLimitResponse(BaseModel):
    """
    上限に達した際にフロントエンドへ返す、課金誘導用の情報をまとめた箱。
    Mihoさん流：10 + 1 x Cost ¥100 /Month というメッセージを運びます。
    """
    current_count: int
    allowed_limit: int
    upgrade_msg: str  # 💡 ここに "27 + 1 x Cost ¥100 /Month" が入ります
    stripe_url: Optional[str] = None # 将来的に決済リンクを直接送る場合用

    model_config = ConfigDict(from_attributes=True)