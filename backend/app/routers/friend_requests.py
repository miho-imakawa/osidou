from pydantic import BaseModel, ConfigDict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text
from typing import List, Optional

from .. import models, schemas
from ..utils.security import get_current_user
from ..database import get_db

# stripe_payment から定数と共通関数をインポート
from ..routers.stripe_payment import (
    FRIEND_FREE_LIMIT,
    _create_subscription_for_requester,
)

class FriendshipUpdate(BaseModel):
    friend_note: Optional[str] = None
    is_muted: Optional[bool] = None

router = APIRouter(tags=["Friend Requests"])


# -----------------------------------------------------
# 1. フレンド申請の送信
#    申請者が FRIEND_FREE_LIMIT 人以上 → 402 を返す
#    フロントは 402 を受け取ったら setup-intent エンドポイントへ
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
        raise HTTPException(status_code=400, detail="自分自身にフレンド申請はできません。")

    receiver = db.query(models.User).filter(models.User.id == receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="申請先のユーザーが見つかりません。")

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

    # ── 申請者の友達数チェック ──
    friend_count = (
        db.query(models.Friendship)
        .filter(models.Friendship.user_id == current_user.id)
        .count()
    )
    # Railwayのログで確認するためのデバッグ行
    print(f"DEBUG: user={current_user.id} friend_count={friend_count} limit={FRIEND_FREE_LIMIT}")

    # 友達数がリミット以上の場合のみ、サブスク（カード登録）チェックを行う
    if friend_count >= FRIEND_FREE_LIMIT:
        # アクティブなサブスクがすでにあれば追加課金は承認後に自動処理 → 申請OK
        sub_row = db.execute(
            text("""
                SELECT status FROM friend_manager_subscriptions
                WHERE user_id = :uid
            """),
            {"uid": current_user.id}
        ).fetchone()

        already_subscribed = sub_row and sub_row.status == "active"

        if not already_subscribed:
            # カード未登録 → フロントに SetupIntent へ誘導させる
            raise HTTPException(
                status_code=402,
                detail={
                    "requires_setup": True,
                    "current_count":  friend_count,
                    "receiver_id":    receiver_id,
                    "msg": (
                        f"友達が{FRIEND_FREE_LIMIT}人以上のため、"
                        f"カード登録が必要です（¥100/月）"
                    ),
                }
            )

    # 上記のチェック（402）を通過した場合、または友達数がリミット未満の場合に実行
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
@router.get("/me/friend-requests", response_model=List[schemas.FriendRequestResponse])
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
#    承認時：Friendship 作成 → 申請者のサブスク開始（カード登録済みの場合）
#    拒否時：ステータス更新のみ。課金なし。
# -----------------------------------------------------
@router.put("/friend_requests/{request_id}/status")
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
        # Friendship を双方向で作成
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

        # 申請者のサブスクを開始（カード登録済みの場合のみ）
        # エラーが起きてもフレンド追加自体はロールバックしない
        try:
            _create_subscription_for_requester(request_obj.requester_id, db)
        except Exception as e:
            # サブスク作成失敗はログに残すが承認は成立させる
            print(f"[WARN] subscribe failed for user {request_obj.requester_id}: {e}")

    elif payload.status == models.FriendRequestStatus.REJECTED:
        # 拒否：ステータス更新のみ。課金なし。SetupIntentはStripe側で自然失効。
        request_obj.status = models.FriendRequestStatus.REJECTED
        db.commit()

    db.refresh(request_obj)
    return request_obj


# -----------------------------------------------------
# 4. 送信したフレンド申請
# -----------------------------------------------------
@router.get("/me/sent-friend-requests", response_model=List[schemas.FriendRequestResponse])
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
# 5. 自分のフレンド一覧
# -----------------------------------------------------
@router.get("/me/friends", response_model=List[schemas.FriendshipResponse])
def get_my_friends(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Friendship)
        .options(joinedload(models.Friendship.friend))
        .filter(models.Friendship.user_id == current_user.id)
        .all()
    )


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
# 7. フレンドシップのメモ・ミュート更新
# -----------------------------------------------------
@router.put("/friendships/{friendship_id}")
def update_friendship(
    friendship_id: int,
    payload: FriendshipUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    friendship = db.query(models.Friendship).filter(
        models.Friendship.id == friendship_id,
        models.Friendship.user_id == current_user.id
    ).first()

    if not friendship:
        raise HTTPException(status_code=404, detail="関係が見つかりません。")

    if payload.friend_note is not None:
        friendship.friend_note = payload.friend_note

    if payload.is_muted is not None:
        friendship.is_muted = payload.is_muted

    db.commit()
    return {"message": "保存しました"}


# -----------------------------------------------------
# 8. 承認待ちの申請数
# -----------------------------------------------------
@router.get("/pending/count", summary="未承認のフレンド申請数を取得")
def get_pending_friend_requests_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    count = db.query(models.FriendRequest).filter(
        models.FriendRequest.receiver_id == current_user.id,
        models.FriendRequest.status == models.FriendRequestStatus.PENDING
    ).count()
    return {"pending_count": count}


# -----------------------------------------------------
# 9. 友達数カウント（HomeFeed用）
# -----------------------------------------------------
@router.get("/me/friends/count", summary="自分の友達数を取得")
def get_friend_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    total = db.query(models.Friendship).filter(
        models.Friendship.user_id == current_user.id
    ).count()

    over = max(0, total - FRIEND_FREE_LIMIT)

    return {
        "total":      total,
        "over":       over,
        "is_billing": over > 0,
    }


# -----------------------------------------------------
# FriendLimitResponse（将来の決済リンク送信用）
# -----------------------------------------------------
class FriendLimitResponse(BaseModel):
    current_count: int
    allowed_limit: int
    upgrade_msg:   str
    stripe_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)