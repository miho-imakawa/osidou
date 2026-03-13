from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.models import PostReport, HobbyPost, User # モデル名が HobbyPost であることを確認
from app.utils.security import get_current_user # 認証用関数名を確認
from .. import models, schemas
from ..database import get_db
from ..logics.notifications import notify_ancestors, check_town_member_limit, create_region_notifications_for_post 
from .community import validate_special_post_limit
from datetime import datetime, timedelta
from ..schemas.posts import (
    HobbyPostResponse,
    HobbyPostCreate,
    PostResponseResponse,
    PostResponseCreate,
    AllPostCreate
)

router = APIRouter(tags=["posts"])

# ==========================================
# 💡 共通スキーマ
# ==========================================

class MessageResponse(BaseModel):
    message: str = Field(description="応答メッセージ")
    posted_count: Optional[int] = None

# ==========================================
# 💡 投稿・一覧取得機能
# ==========================================

@router.post("/posts", response_model=HobbyPostResponse)
def create_hobby_post(
    post: HobbyPostCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    if current_user.is_restricted:
        raise HTTPException(status_code=403, detail="Account restricted.")

    is_ad_val = getattr(post, 'is_ad', False)
    is_meetup_val = post.is_meetup
 
    category = db.query(models.HobbyCategory).filter(models.HobbyCategory.id == post.hobby_category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="カテゴリが見つかりません")
    
    db_post = models.HobbyPost(
        content=post.content,
        hobby_category_id=post.hobby_category_id,
        user_id=current_user.id,
        parent_id=post.parent_id,
        region_tag_pref=current_user.prefecture,
        region_tag_city=current_user.city,
        is_meetup=is_meetup_val,
        is_ad=is_ad_val,
        ad_color=getattr(post, 'ad_color', 'green'), 
        # --- ここから下が漏れていました！ ---
        meetup_date=post.meetup_date if is_meetup_val else None,
        meetup_location=post.meetup_location if is_meetup_val else None, # ★getattrを使わず直接参照
        meetup_capacity=post.meetup_capacity if is_meetup_val else None, # ★ここも
        meetup_fee_info=post.meetup_fee_info if is_meetup_val else None, # ★これが必要！
        ad_end_date=post.ad_end_date if is_ad_val else None,
    )
    
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    
    if "[ALL]" in db_post.content.upper():
        background_tasks.add_task(notify_ancestors, db_post.id, db_post.user_id, db, current_user.nickname, db_post.content)
    
    if db_post.is_meetup:
        background_tasks.add_task(create_region_notifications_for_post, db, db_post)
    
    db_post.author_nickname = current_user.nickname
    db_post.public_code = current_user.public_code
    return db_post

@router.get("/posts/category/{category_id}", response_model=List[schemas.HobbyPostResponse])
def get_posts_by_category(category_id: int, db: Session = Depends(get_db)):
    """カテゴリの投稿一覧（💡参加者名・作者名をフォールバック付きで紐付け）"""
    posts = db.query(models.HobbyPost).filter(
        models.HobbyPost.hobby_category_id == category_id,
        models.HobbyPost.is_hidden == False  # ★ 追加
    ).order_by(models.HobbyPost.created_at.desc()).all()
    
    for post in posts:
        # --- 1. 投稿主（Author）の情報を紐付け ---
        user = db.query(models.User).filter(models.User.id == post.user_id).first()
        if user:
            # 💡 修正：ニックネーム未設定なら「User[ID]@[ドメイン]」を表示
            domain = user.email.split('@')[-1] if user.email else "unknown"
            post.author_nickname = user.nickname or f"User{user.id}"
            post.public_code = user.public_code or "-------"
        else:
            post.author_nickname = "Unknown"
            post.public_code = "-------"
        
        # --- 2. 参加者リスト（Responses）の情報を紐付け ---
        for res in post.responses:
            res_user = db.query(models.User).filter(models.User.id == res.user_id).first()
            if res_user:
                # 💡 修正：ここも同様にフォールバック処理を追加
                res_domain = res_user.email.split('@')[-1] if res_user.email else "unknown"
                res.author_nickname = res_user.nickname or f"User{res_user.id}"
            else:
                res.author_nickname = "Unknown"
            
        post.response_count = len(post.responses)
        post.participation_count = sum(1 for r in post.responses if r.is_participation)
        
    return posts


@router.get("/posts/my-hosted-meetups", response_model=List[schemas.HobbyPostResponse])
def get_my_hosted_meetups(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """自分が主催（投稿）したミートアップ一覧"""
    meetups = db.query(models.HobbyPost).filter(
        models.HobbyPost.user_id == current_user.id,
        models.HobbyPost.is_meetup == True
    ).order_by(models.HobbyPost.created_at.desc()).all()
    
    for post in meetups:
        post.author_nickname = current_user.nickname
        for res in post.responses:
            res_user = db.query(models.User).filter(models.User.id == res.user_id).first()
            res.author_nickname = res_user.nickname if res_user else f"User{res.user_id}"
    
    return meetups

# ==========================================
# 💡 参加表明（JOIN）ロジックの修正
# ==========================================

@router.post("/posts/{post_id}/responses", response_model=PostResponseResponse)
def create_post_response(
    post_id: int,
    response: PostResponseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user), 
):
    post = db.query(models.HobbyPost).filter(models.HobbyPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")

    # 重複参加チェック
    already_joined = db.query(models.PostResponse).filter(
        models.PostResponse.post_id == post_id,
        models.PostResponse.user_id == current_user.id,
        models.PostResponse.is_participation == True
    ).first()
    if already_joined:
        raise HTTPException(status_code=400, detail="既にこのミートアップに参加（または待機）しています")

    # 定員チェックの修正
# --- posts.py の create_post_response 内、定員チェック部分を書き換え ---

    # 💡 修正：定員チェック（キャンセル待ちは除外してカウント）
    if response.is_participation and post.is_meetup and post.meetup_capacity:
        # "Waitlist" 以外の確定参加者数をカウント
        current_count = db.query(func.count(models.PostResponse.id)).filter(
            models.PostResponse.post_id == post_id,
            models.PostResponse.is_participation == True,
            models.PostResponse.content != "Waitlist" # 💡 ここを追加
        ).scalar() or 0
        
        # 「キャンセル待ち」ではない通常の参加申し込みで、かつ満員の場合のみエラー
        if response.content != "Waitlist" and current_count >= post.meetup_capacity:
            raise HTTPException(status_code=400, detail="定員に達しています。キャンセル待ちを選択してください。")
        
    # 保存処理
    db_response = models.PostResponse(
        content=response.content or "参加希望！",
        is_participation=response.is_participation,
        is_attended=False,
        user_id=current_user.id,
        post_id=post_id
    )
    
    db.add(db_response)
    db.commit()
    db.refresh(db_response)
    
    db_response.author_nickname = current_user.nickname
    return db_response

# ==========================================
# 💡 出席管理
# ==========================================

@router.put("/responses/{response_id}/attendance")
def toggle_attendance(
    response_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    res = db.query(models.PostResponse).filter(models.PostResponse.id == response_id).first()
    if not res:
        raise HTTPException(status_code=404, detail="データが見つかりません")
    
    if res.post.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="主催者のみ操作可能です")
    
    res.is_attended = not res.is_attended
    db.commit()
    return {"is_attended": res.is_attended}

# ==========================================
# 💡 参加情報の更新（キャンセル待ち → 参加確定への切り替え）
# ==========================================

class ResponseUpdate(BaseModel):
    content: str

@router.patch("/responses/{response_id}")
def update_response_content(
    response_id: int,
    data: ResponseUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    res = db.query(models.PostResponse).filter(models.PostResponse.id == response_id).first()
    if not res:
        raise HTTPException(status_code=404, detail="データが見つかりません")
    
    if res.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="ご本人のみ更新可能です")

    # 「Join!」に切り替える場合、その瞬間に空きがあるか再確認
    if data.content == "Join!":
        post = res.post
        current_count = db.query(func.count(models.PostResponse.id)).filter(
            models.PostResponse.post_id == post.id,
            models.PostResponse.is_participation == True,
            models.PostResponse.content != "Waitlist"
        ).scalar() or 0
        
        if current_count >= (post.meetup_capacity or 0):
            raise HTTPException(status_code=400, detail="申し訳ありません、まだ空きがありません。")

    res.content = data.content
    db.commit()
    return {"status": "updated", "content": res.content}

# ==========================================
# 💡 参加MEETUP一覧取得
# ==========================================

@router.get("/posts/my-meetups", response_model=List[schemas.HobbyPostResponse])
def get_my_meetups(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # 自分がPostResponse（is_participation=True）を紐付けている親投稿を取得
    meetups = db.query(models.HobbyPost).join(models.PostResponse).filter(
        models.PostResponse.user_id == current_user.id,
        models.PostResponse.is_participation == True
    ).all()
    
    # 既存の一覧取得と同様に author_nickname などの紐付け処理をループで回す（既存ロジックを流用）
    return meetups

# ==========================================
# 💡 追加：キャンセル（参加情報の削除）
# ==========================================

@router.delete("/responses/cancel/{post_id}")
def cancel_meetup_participation(
    post_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    res = db.query(models.PostResponse).filter(
        models.PostResponse.post_id == post_id,
        models.PostResponse.user_id == current_user.id,
        models.PostResponse.is_participation == True
    ).first()
    
    if not res:
        raise HTTPException(status_code=404, detail="参加情報が見つかりません")
    
    db.delete(res)
    db.commit()
    return {"message": "canceled"}

# ==========================================
# 💡 MY PAGE用：参加中のミートアップ取得とキャンセル
# ==========================================

@router.get("/posts/my-meetups", response_model=List[schemas.HobbyPostResponse])
def get_my_meetups(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """自分が参加（またはキャンセル待ち）している投稿一覧を取得"""
    meetups = db.query(models.HobbyPost).join(models.PostResponse).filter(
        models.PostResponse.user_id == current_user.id,
        models.PostResponse.is_participation == True
    ).all()
    
    # フロントで表示するために必要なニックネーム等を紐付け
    for post in meetups:
        user = db.query(models.User).filter(models.User.id == post.user_id).first()
        post.author_nickname = user.nickname if user else f"User{post.user_id}"
        
        for res in post.responses:
            res_user = db.query(models.User).filter(models.User.id == res.user_id).first()
            res.author_nickname = res_user.nickname if res_user else f"User{res.user_id}"
            
    return meetups

@router.delete("/responses/cancel/{post_id}")
def cancel_meetup_participation(
    post_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """参加をキャンセル（レコード削除）"""
    res = db.query(models.PostResponse).filter(
        models.PostResponse.post_id == post_id,
        models.PostResponse.user_id == current_user.id,
        models.PostResponse.is_participation == True
    ).first()
    
    if not res:
        raise HTTPException(status_code=404, detail="参加情報が見つかりません")
    
    db.delete(res)
    db.commit()
    return {"message": "canceled"}

# ==========================================
# 💡 広告インタラクション（いいね・PIN・閉じる）
# ==========================================

class AdInteractionRequest(BaseModel):
    action: str  # "like", "pin", "close"

@router.post("/posts/{post_id}/ad-interaction")
def ad_interaction(
    post_id: int,
    request: AdInteractionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    interaction = db.query(models.UserAdInteraction).filter(
        models.UserAdInteraction.user_id == current_user.id,
        models.UserAdInteraction.post_id == post_id
    ).first()
    
    if not interaction:
        interaction = models.UserAdInteraction(
            user_id=current_user.id,
            post_id=post_id
        )
        db.add(interaction)
    
    if request.action == "like":
        interaction.is_liked = not interaction.is_liked
    elif request.action == "pin":
        interaction.is_pinned = not interaction.is_pinned
    elif request.action == "close":
        interaction.is_closed = True
    
    db.commit()
    return {
        "is_liked": interaction.is_liked,
        "is_pinned": interaction.is_pinned,
        "is_closed": interaction.is_closed
    }

@router.get("/posts/my-ad-interactions")
def get_my_ad_interactions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    interactions = db.query(models.UserAdInteraction).filter(
        models.UserAdInteraction.user_id == current_user.id
    ).all()
    return {i.post_id: {
        "is_liked": i.is_liked,
        "is_pinned": i.is_pinned,
        "is_closed": i.is_closed
    } for i in interactions}


# いいね、PINの数
@router.get("/posts/my-ads-stats")
def get_my_ads_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    from datetime import datetime, timedelta
    
    # 自分のAD投稿を取得（終了後1週間以内のものも含む）
    one_week_ago = datetime.now() - timedelta(days=7)
    
    my_ads = db.query(models.HobbyPost).filter(
        models.HobbyPost.user_id == current_user.id,
        models.HobbyPost.is_ad == True,
        # 掲載終了後1週間以内 または まだ終了していない
        (models.HobbyPost.ad_end_date == None) | 
        (models.HobbyPost.ad_end_date >= one_week_ago)
    ).all()
    
    result = []
    for ad in my_ads:
        like_count = db.query(models.UserAdInteraction).filter(
            models.UserAdInteraction.post_id == ad.id,
            models.UserAdInteraction.is_liked == True
        ).count()
        
        pin_count = db.query(models.UserAdInteraction).filter(
            models.UserAdInteraction.post_id == ad.id,
            models.UserAdInteraction.is_pinned == True
        ).count()
        
        result.append({
            "id": ad.id,
            "title": ad.content.split('\n')[0],
            "ad_end_date": ad.ad_end_date.isoformat() if ad.ad_end_date else None,
            "like_count": like_count,
            "pin_count": pin_count,
        })
    
    return result

# ============================================================
# レポート機能
# ============================================================

@router.post("/posts/{post_id}/report")
async def report_post(
    post_id: int, 
    reason: str = None, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    target_post = db.query(HobbyPost).filter(HobbyPost.id == post_id).first()
    if not target_post:
        raise HTTPException(status_code=404, detail="報告対象の投稿が見つかりません。")

    existing_report = db.query(PostReport).filter(
        PostReport.post_id == post_id,
        PostReport.reporter_id == current_user.id
    ).first()
    
    if existing_report:
        raise HTTPException(status_code=400, detail="この投稿は既に報告済みです。")

    new_report = PostReport(
        post_id=post_id,
        reporter_id=current_user.id,
        reason=reason[:200] if reason else None
    )
    db.add(new_report)
    db.commit()

    report_count = db.query(PostReport).filter(PostReport.post_id == post_id).count()
    
    # ★ 自動非表示ロジック
    if report_count >= 5:
        target_post.is_hidden = True
        db.commit()
        print(f"⚠️ [AUTO-HIDDEN] Post ID {post_id} is now hidden. (Reports: {report_count})")
    elif report_count >= 3:
        print(f"📢 [ADMIN-NOTIFY] Post ID {post_id} received {report_count} reports.")

    return {
        "status": "success",
        "detail": "通報を受け付けました。ご協力ありがとうございます。",
        "report_count": report_count,
        "is_hidden": target_post.is_hidden
    }