from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user
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
    """汎用的なメッセージ応答"""
    message: str = Field(description="応答メッセージ")
    posted_count: Optional[int] = None

# ==========================================
# 💡 趣味グループへの投稿（完全版）
# ==========================================

@router.post("/posts", response_model=HobbyPostResponse)
def create_hobby_post(
    post: HobbyPostCreate, # ← ここ(schemas)にも parent_id が必要です
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """趣味グループに投稿する（地域タグ自動付与・通知処理付き）"""
    
    # 1. ユーザー制限チェック
    if current_user.is_restricted:
        raise HTTPException(status_code=403, detail="Account restricted.")

    # 2か月に3回投稿のしばり。削除
    # 変数の定義は、下の投稿作成処理で使うので消さないでください
    is_ad_val = getattr(post, 'is_ad', False)
    is_meetup_val = post.is_meetup
 
    # 3. カテゴリ存在チェック
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == post.hobby_category_id
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail="カテゴリが見つかりません")
    
    # 4. 投稿作成（地域タグ自動付与）
    db_post = models.HobbyPost(
        content=post.content,
        hobby_category_id=post.hobby_category_id,
        user_id=current_user.id,
        parent_id=post.parent_id,  # 💡 これを追加！
        region_tag_pref=current_user.prefecture,
        region_tag_city=current_user.city,
        is_meetup=is_meetup_val,
        is_ad=is_ad_val,
        meetup_date=post.meetup_date if is_meetup_val else None,
        meetup_location=getattr(post, 'meetup_location', None) if is_meetup_val else None,
        meetup_capacity=getattr(post, 'meetup_capacity', None) if is_meetup_val else None,
        ad_end_date=getattr(post, 'ad_end_date', None) if is_ad_val else None,
    )
    
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    
    # 5. 通知処理（バックグラウンド実行）
    # a) [ALL]タグがある場合、祖先カテゴリに通知
    if "[ALL]" in db_post.content.upper():
        background_tasks.add_task(
            notify_ancestors, db_post.id, db_post.user_id, db, 
            current_user.nickname, db_post.content
        )
    
    # b) Meetup投稿の場合、地域通知
    if db_post.is_meetup:
        background_tasks.add_task(
            create_region_notifications_for_post, db, db_post
        )
    
    # 6. レスポンス用にニックネームを追加
    db_post.author_nickname = current_user.nickname
    db_post.public_code = current_user.public_code
    return db_post

# ==========================================
# 💡 安全機能: 通報エンドポイント
# ==========================================

@router.post("/posts/{post_id}/report", tags=["safety"])
def report_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """投稿を通報し、5件で投稿主を制限"""
    target_post = db.query(models.HobbyPost).filter(
        models.HobbyPost.id == post_id
    ).first()
    if not target_post:
        raise HTTPException(status_code=404, detail="対象の投稿が見つかりません")

    # 重複通報チェック
    already_reported = db.query(models.PostReport).filter(
        models.PostReport.reporter_id == current_user.id,
        models.PostReport.post_id == post_id
    ).first()
    if already_reported:
        raise HTTPException(status_code=400, detail="この投稿はすでに通報済みです")

    # 通報作成
    new_report = models.PostReport(
        reporter_id=current_user.id,
        post_id=post_id
    )
    db.add(new_report)

    # 投稿主の通報カウント更新
    author = db.query(models.User).filter(
        models.User.id == target_post.user_id
    ).first()
    if author:
        author.report_count += 1
        if author.report_count >= 5:
            author.is_restricted = True

    db.commit()
    return {"message": "通報を受理しました。ご協力ありがとうございます。"}

# ==========================================
# 💡 ALL投稿エンドポイント
# ==========================================

@router.post("/posts/all", response_model=MessageResponse, tags=["posts"])
def create_all_post(
    post_data: AllPostCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """参加中の全Townカテゴリに一括投稿"""
    
    try:
        user_town_categories = db.query(
            models.HobbyCategory.id
        ).join(
            models.Town, models.Town.hobby_category_id == models.HobbyCategory.id
        ).join(
            models.UserTown, models.UserTown.town_id == models.Town.id
        ).filter(
            models.UserTown.user_id == current_user.id
        ).distinct().all()
    except Exception as e:
        print(f"Town関連テーブルの結合エラー: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Town関連テーブルの参照に失敗しました。"
        )
    
    if not user_town_categories:
        raise HTTPException(
            status_code=404, 
            detail="参加中のTownカテゴリが見つかりません。"
        )
    
    posted_count = 0
    
    for category_tuple in user_town_categories:
        category_id = category_tuple[0]
        
        db_post = models.HobbyPost(
            content=post_data.content,
            hobby_category_id=category_id,
            user_id=current_user.id,
            region_tag_pref=current_user.prefecture,
            region_tag_city=current_user.city,
            is_meetup=False,
        )
        
        db.add(db_post)
        db.flush()
        
        # 祖先カテゴリに通知
        background_tasks.add_task(
            notify_ancestors, db_post.id, db_post.user_id, db, 
            current_user.nickname, db_post.content
        )
        
        posted_count += 1
        
    db.commit()
    
    # Town人数チェック
    background_tasks.add_task(
        check_town_member_limit, 
        [cat[0] for cat in user_town_categories], 
        db
    )
    
    message = f"✅ 参加中の {posted_count} 個のカテゴリに一括投稿を完了しました。"
    
    return MessageResponse(
        message=message,
        posted_count=posted_count
    )

# ==========================================
# 💡 投稿一覧取得
# ==========================================

@router.get("/posts", response_model=List[HobbyPostResponse], tags=["posts"])
def get_hobby_posts(
    hobby_category_id: Optional[int] = None,
    is_meetup_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """投稿一覧（タイムライン）"""
    query = db.query(models.HobbyPost)
    
    if hobby_category_id:
        query = query.filter(
            models.HobbyPost.hobby_category_id == hobby_category_id
        )
    if is_meetup_only:
        query = query.filter(models.HobbyPost.is_meetup == True)
    
    posts = query.order_by(
        models.HobbyPost.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    for post in posts:
        user = db.query(models.User).filter(
            models.User.id == post.user_id
        ).first()
        post.author_nickname = user.nickname if user else "Unknown"
        
        # 返信数
        post.response_count = db.query(
            func.count(models.PostResponse.id)
        ).filter(
            models.PostResponse.post_id == post.id
        ).scalar() or 0
        
        # 参加表明数
        post.participation_count = db.query(
            func.count(models.PostResponse.id)
        ).filter(
            models.PostResponse.post_id == post.id,
            models.PostResponse.is_participation == True
        ).scalar() or 0
    
    return posts

# ==========================================
# 💡 カテゴリ別投稿取得（非表示・制限ユーザー除外）
# ==========================================

# posts.py の get_posts_by_category を一時的にこれに置き換え（デバッグ用）

@router.get("/posts/category/{category_id}", response_model=List[schemas.HobbyPostResponse])
def get_posts_by_category(
    category_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """カテゴリの投稿一覧（デバッグ版 - フィルタなし）"""
    
    print(f"🔍 Debug: category_id={category_id}, user_id={current_user.id}")
    
    # 💡 一時的にフィルタを無効化して全投稿を取得
    posts = db.query(models.HobbyPost).filter(
        models.HobbyPost.hobby_category_id == category_id
    ).order_by(
        models.HobbyPost.created_at.desc()
    ).all()
    
    print(f"📊 Debug: 取得した件数={len(posts)}")
    
    for post in posts:
        user = db.query(models.User).filter(
            models.User.id == post.user_id
        ).first()

        print(f"📝 Debug: post_id={post.id}, user_id={post.user_id}, is_restricted={user.is_restricted if user else 'N/A'}")

        post.author_nickname = user.nickname if user else "Unknown"
        post.public_code = user.public_code if user else "-------"

        # 返信数・参加数
        post.response_count = db.query(
            func.count(models.PostResponse.id)
        ).filter(
            models.PostResponse.post_id == post.id
        ).scalar() or 0

        post.participation_count = db.query(
            func.count(models.PostResponse.id)
        ).filter(
            models.PostResponse.post_id == post.id,
            models.PostResponse.is_participation == True
        ).scalar() or 0

    return posts

# ==========================================
# 💡 ユーザーの特別投稿取得
# ==========================================

@router.get("/posts/user/{user_id}/specials", response_model=List[HobbyPostResponse])
def get_user_special_posts(user_id: int, db: Session = Depends(get_db)):
    """期限内の特別投稿を取得（マイページ・チャット用）"""
    now = datetime.now()
    posts = db.query(models.HobbyPost).filter(
        models.HobbyPost.user_id == user_id,
        (
            (models.HobbyPost.is_meetup == True) & 
            (models.HobbyPost.meetup_date >= now)
        ) | (
            (models.HobbyPost.is_ad == True) & 
            (models.HobbyPost.ad_end_date >= now)
        )
    ).order_by(models.HobbyPost.created_at.desc()).all()

    for post in posts:
        user = db.query(models.User).filter(
            models.User.id == post.user_id
        ).first()
        post.author_nickname = user.nickname if user else "Unknown"
        post.public_code = user.public_code if user else "-------"
    
    return posts

# ==========================================
# 💡 投稿詳細取得
# ==========================================

@router.get("/posts/{post_id}", response_model=HobbyPostResponse)
def get_hobby_post_detail(post_id: int, db: Session = Depends(get_db)):
    """投稿の詳細"""
    post = db.query(models.HobbyPost).filter(
        models.HobbyPost.id == post_id
    ).first()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")
    
    user = db.query(models.User).filter(
        models.User.id == post.user_id
    ).first()
    post.author_nickname = user.nickname if user else "Unknown"
    
    # 返信数・参加表明数
    post.response_count = db.query(
        func.count(models.PostResponse.id)
    ).filter(
        models.PostResponse.post_id == post_id
    ).scalar() or 0
    
    post.participation_count = db.query(
        func.count(models.PostResponse.id)
    ).filter(
        models.PostResponse.post_id == post_id,
        models.PostResponse.is_participation == True
    ).scalar() or 0
    
    return post

# ==========================================
# 💡 投稿への返信
# ==========================================

@router.post("/posts/{post_id}/responses", response_model=PostResponseResponse)
def create_post_response(
    post_id: int,
    response: PostResponseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user), 
):
    """投稿への返信/参加表明"""
    post = db.query(models.HobbyPost).filter(
        models.HobbyPost.id == post_id
    ).first()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")

    # Meetup定員チェック
    if response.is_participation and post.is_meetup and post.meetup_capacity:
        current_participants = db.query(
            func.count(models.PostResponse.id)
        ).filter(
            models.PostResponse.post_id == post_id,
            models.PostResponse.is_participation == True
        ).scalar() or 0

        # すでに参加済みかチェック
        is_already_participated = db.query(models.PostResponse).filter(
            models.PostResponse.post_id == post_id,
            models.PostResponse.user_id == current_user.id,
            models.PostResponse.is_participation == True
        ).first()
        
        if not is_already_participated and current_participants >= post.meetup_capacity:
            raise HTTPException(
                status_code=400,
                detail=f"Meetupの定員({post.meetup_capacity}名)を超過しています。"
            )
        
    # 返信作成
    db_response = models.PostResponse(
        content=response.content,
        is_participation=response.is_participation,
        user_id=current_user.id,
        post_id=post_id
    )
    
    db.add(db_response)
    db.commit()
    db.refresh(db_response)
    
    db_response.author_nickname = current_user.nickname
    return db_response

# ==========================================
# 💡 返信一覧取得
# ==========================================

@router.get("/posts/{post_id}/responses", response_model=List[PostResponseResponse])
def get_post_responses(post_id: int, db: Session = Depends(get_db)):
    """投稿への返信一覧"""
    post = db.query(models.HobbyPost).filter(
        models.HobbyPost.id == post_id
    ).first()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")
        
    responses = db.query(models.PostResponse).filter(
        models.PostResponse.post_id == post_id
    ).order_by(models.PostResponse.created_at).all()
    
    for res in responses:
        user = db.query(models.User).filter(
            models.User.id == res.user_id
        ).first()
        res.author_nickname = user.nickname if user else "Unknown"
        
    return responses