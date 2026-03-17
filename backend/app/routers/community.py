from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import func, or_
from .. import models, schemas
from ..database import get_db
from ..utils.security import get_current_user, get_optional_user

router = APIRouter(tags=["community"])

# ==========================================
# 💡 0. GUIDE カテゴリID取得
# ==========================================
@router.get("/guide")
def get_guide_category(db: Session = Depends(get_db)):
    guide_cat = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.name == "GUIDE （推し道の歩き方）"  # 全角カッコに修正
    ).first()

    if not guide_cat:
        raise HTTPException(status_code=404, detail="GUIDEカテゴリが見つかりません")

    return {"id": guide_cat.id}

# ==========================================
# 💡 1. 投稿制限チェックロジック (Helper)
# ==========================================
def validate_special_post_limit(user_id: int, db: Session):
    """2ヶ月(60日)以内に3件以上の特別投稿(MeetUp/広告)を制限する"""
    two_months_ago = datetime.now() - timedelta(days=60)
    
    count = db.query(models.HobbyPost).filter(
        models.HobbyPost.user_id == user_id,
        (models.HobbyPost.is_meetup == True) | (models.HobbyPost.is_ad == True),
        models.HobbyPost.created_at >= two_months_ago
    ).count()
    
    if count >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Meet Upと広告は、2ヶ月間に合計3件までしか投稿できません。"
        )

# ==========================================
# 💡 2. 参加・退会・管理
# ==========================================

@router.post("/join/{category_id}")
def join_community(category_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """コミュニティに参加する"""
    existing = db.query(models.UserHobbyLink).filter(
        models.UserHobbyLink.user_id == current_user.id,
        models.UserHobbyLink.hobby_category_id == category_id
    ).first()
    
    if existing:
        return {"message": "既に参加しています"}

    new_link = models.UserHobbyLink(user_id=current_user.id, hobby_category_id=category_id)
    db.add(new_link)
    db.commit()
    return {"message": "参加しました"}

# backend/app/routers/community.py

@router.post("/join/{category_id}")
def join_community(category_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """コミュニティに参加する"""
    existing = db.query(models.UserHobbyLink).filter(
        models.UserHobbyLink.user_id == current_user.id,
        models.UserHobbyLink.hobby_category_id == category_id
    ).first()
    
    if existing:
        return {"message": "既に参加しています"}

    new_link = models.UserHobbyLink(user_id=current_user.id, hobby_category_id=category_id)
    db.add(new_link)
    db.commit()

    # ==========================================
    # 💡 新機能: 地域メンバー数の通知チェック
    # ==========================================
    if current_user.prefecture and current_user.city:
        # 同じコミュニティ・同じ市区町村のメンバー数をカウント
        count = db.query(models.UserHobbyLink).join(models.User).filter(
            models.UserHobbyLink.hobby_category_id == category_id,
            models.User.prefecture == current_user.prefecture,
            models.User.city == current_user.city
        ).count()

        # 通知のしきい値判定 (5人刻み/10人刻み/100人刻み)
        should_notify = False
        if count < 30 and count % 5 == 0:
            should_notify = True
        elif 30 <= count < 100 and count % 10 == 0:
            should_notify = True
        elif count >= 100 and count % 100 == 0:
            should_notify = True

        if should_notify:
            # システムメッセージとして投稿を作成
            system_msg = models.HobbyPost(
                hobby_category_id=category_id,
                user_id=1,  # 管理者またはシステムユーザーのIDを指定
                content=f"📢 【祝】{current_user.prefecture}{current_user.city}のメンバーが{count}名に達しました！✨",
                is_system=True  # postsテーブルにこのカラムがある前提
            )
            db.add(system_msg)
            db.commit()

    return {"message": "参加しました"}

# backend/app/routers/community.py

@router.delete("/leave/{category_id}")
def leave_community(category_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """コミュニティを退会する"""
    # 参加情報をDBから探す
    link = db.query(models.UserHobbyLink).filter(
        models.UserHobbyLink.user_id == current_user.id,
        models.UserHobbyLink.hobby_category_id == category_id
    ).first()
    
    # 参加していなければエラーを返す
    if not link:
        raise HTTPException(status_code=404, detail="参加していないコミュニティです")
    
    # DBから削除（退会処理）
    db.delete(link)
    db.commit()
    
    return {"message": "退会しました"}

# community.py の修正イメージ
@router.get("/my-communities", response_model=List[schemas.HobbyCategoryResponse])
def get_my_communities(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # 1. 自分が参加しているリンクをすべて取得
    links = db.query(models.UserHobbyLink).filter(models.UserHobbyLink.user_id == current_user.id).all()
    
    unique_masters = {}
    for link in links:
        cat = link.hobby_category
        # 本尊（master_id）があればそれを、なければ自身のIDを基準にする
        master_id = cat.master_id if cat.master_id else cat.id
        
        if master_id in unique_masters:
            continue
            
        master_cat = db.query(models.HobbyCategory).filter(models.HobbyCategory.id == master_id).first()
        if master_cat:
            # 本尊＋全支部の合算人数を計算
            total = db.query(models.UserHobbyLink.user_id).distinct().join(models.HobbyCategory).filter(
                or_(
                    models.HobbyCategory.id == master_id,
                    models.HobbyCategory.master_id == master_id
                )
            ).count() # 🔥 .distinct() を入れることで、一人が複数箇所にいても「1」と数える
            
            res_obj = schemas.HobbyCategoryResponse.from_orm(master_cat)
            res_obj.member_count = total
            res_obj.children = []  # 🔥 マイページでは整理箱（フラット）に見せる
            unique_masters[master_id] = res_obj

    return list(unique_masters.values())

@router.get("/check-join/{category_id}")
def check_join_status(
    category_id: int, 
    db: Session = Depends(get_db), 
    current_user: Optional[models.User] = Depends(get_optional_user)  # ★ 変更
):
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == category_id
    ).first()

    # is_public は誰でも通過
    if category and category.is_public:
        return {"is_joined": True}

    # 未ログインはFalse
    if not current_user:
        return {"is_joined": False}
    
    check_id = category.master_id if category and category.master_id else category_id
    
    joined = db.query(models.UserHobbyLink).filter(
        models.UserHobbyLink.user_id == current_user.id,
        models.UserHobbyLink.hobby_category_id == check_id
    ).first()
    
    return {"is_joined": joined is not None}

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