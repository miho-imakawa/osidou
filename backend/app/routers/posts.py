from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user
# 💡 修正点: create_region_notifications_for_post をインポート
from ..logics.notifications import notify_ancestors, check_town_member_limit, create_region_notifications_for_post 

# スキーマを直接インポート
from ..schemas.posts import (
    HobbyPostResponse,
    HobbyPostCreate,
    PostResponseResponse,
    PostResponseCreate,
    AllPostCreate
)

router = APIRouter(
    # prefix="/posts" をもし書いていたら、消すか確認してください。
    # main.py側で app.include_router(posts.router) と呼んでいる場合
    tags=["posts"]
)

# ==========================================
# 💡 共通スキーマ
# ==========================================

class MessageResponse(BaseModel):
    """汎用的なメッセージ応答"""
    message: str = Field(description="応答メッセージ")
    posted_count: Optional[int] = None # ALL投稿用のフィールド

# ==========================================
# 💡 趣味グループへの投稿（地域タグ自動付与と通知ロジック呼び出し）
# ==========================================

@router.post("/posts", response_model=HobbyPostResponse, tags=["posts"])
def create_hobby_post(
    post: HobbyPostCreate,
    background_tasks: BackgroundTasks, # BackgroundTasksの追加
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    趣味グループに投稿する（投稿者の地域情報をDBに自動付与）
    [ALL]タグを含む場合、上層カテゴリにも通知を広げる。
    Meetup投稿の場合は地域通知ロジックを起動。
    """
    # 1. カテゴリ存在チェック (HobbyCategoryを使用)
    category = db.query(models.HobbyCategory).filter(
        models.HobbyCategory.id == post.hobby_category_id
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail="カテゴリが見つかりません")
    
    # 2. ユーザーの地域情報を自動タグ付け
    db_post = models.HobbyPost(
        content=post.content,
        hobby_category_id=post.hobby_category_id,
        user_id=current_user.id,
        region_tag_pref=current_user.prefecture,
        region_tag_city=current_user.city,
        is_meetup=post.is_meetup,
        meetup_date=post.meetup_date,
        meetup_location=post.meetup_location,
        meetup_capacity=post.meetup_capacity
    )
    
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    
    # 3. 【通知ロジックの呼び出し】 (BackgroundTasksで非同期実行)
    
    # a) 💡 階層通知ロジック (上層への連絡の「業」)
    # 投稿内容に '[ALL]' が含まれている場合のみ、祖先カテゴリのフォロワーにも通知
    if "[ALL]" in db_post.content.upper():
        background_tasks.add_task(
            notify_ancestors, db_post.id, db_post.user_id, db, current_user.nickname, db_post.content
        )
    
    # b) 地域通知ロジック (Meetup投稿の場合のみ実行)
    if db_post.is_meetup:
        background_tasks.add_task(
            create_region_notifications_for_post, db, db_post
        )
    
    # 4. 投稿者のニックネームを追加 (レスポンス用)
    db_post.author_nickname = current_user.nickname
    return db_post

# ==========================================
# 💡 ALL投稿エンドポイントの復元
# ==========================================

@router.post("/posts/all", response_model=MessageResponse, tags=["posts"])
def create_all_post(
    post_data: AllPostCreate,
    background_tasks: BackgroundTasks, # BackgroundTasksの追加
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    ALLカテゴリに一括投稿する（参加カテゴリ全てに投稿）
    """
    
    # 1. ユーザーが参加している Town を取得
    # Town 参加テーブル (UserTown) から、ユーザーが参加している Town ID を取得し、
    # その Town ID に紐づくカテゴリ ID を全て取得
    # 💡 Town/UserTown モデルが models.py にあることを前提とします
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
        raise HTTPException(status_code=500, detail="Town関連テーブルの参照に失敗しました。モデル定義を確認してください。")
    
    if not user_town_categories:
        raise HTTPException(status_code=404, detail="参加中のTownカテゴリが見つかりません。")
    
    posted_count = 0
    
    for category_tuple in user_town_categories:
        category_id = category_tuple[0]
        
        db_post = models.HobbyPost(
            content=post_data.content,
            hobby_category_id=category_id,
            user_id=current_user.id,
            region_tag_pref=current_user.prefecture,
            region_tag_city=current_user.city,
            is_meetup=False, # ALL投稿はMeetupを想定しない
        )
        
        db.add(db_post)
        db.flush() # 投稿IDを確定させる
        
        # ALL投稿では、投稿先のカテゴリと、その祖先すべてに通知を飛ばす
        background_tasks.add_task(
            notify_ancestors, db_post.id, db_post.user_id, db, current_user.nickname, db_post.content
        )
        
        posted_count += 1
        
    db.commit()
    
    # 2. 【Town人数チェックロジックの呼び出し】 (BackgroundTasksで非同期実行)
    background_tasks.add_task(
        check_town_member_limit, [cat[0] for cat in user_town_categories], db
    )
    
    # 💡 修正: 警告を兼ねたメッセージに変更
    message = f"✅ 参加中の {posted_count} 個のカテゴリに一括投稿を完了しました。この投稿は、関連するすべての Town フォロワーに通知されます。"
    
    return MessageResponse(
        message=message,
        posted_count=posted_count
    )

# ==========================================
# 💡 投稿一覧・詳細の取得
# ==========================================

@router.get("/posts", response_model=List[HobbyPostResponse], tags=["posts"])
def get_hobby_posts(
    hobby_category_id: Optional[int] = None,
    is_meetup_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    趣味グループの投稿一覧（タイムライン）
    """
    query = db.query(models.HobbyPost)
    
    # フィルタリング
    if hobby_category_id:
        query = query.filter(models.HobbyPost.hobby_category_id == hobby_category_id)
    if is_meetup_only:
        query = query.filter(models.HobbyPost.is_meetup == True)
    
    posts = query.order_by(models.HobbyPost.created_at.desc()).offset(offset).limit(limit).all()
    
    # 各投稿に返信数・参加表明数を追加
    for post in posts:
        # 投稿者のニックネーム
        user = db.query(models.User).filter(models.User.id == post.user_id).first()
        post.author_nickname = user.nickname if user else "Unknown"
        
        # 返信数
        response_count = db.query(func.count(models.PostResponse.id)).filter(
            models.PostResponse.post_id == post.id
        ).scalar()
        post.response_count = response_count or 0
        
        # 参加表明数
        participation_count = db.query(func.count(models.PostResponse.id)).filter(
            models.PostResponse.post_id == post.id,
            models.PostResponse.is_participation == True
        ).scalar()
        post.participation_count = participation_count or 0
    
    return posts

# backend/app/routers/posts.py 内の追加した関数
@router.get("/posts/category/{category_id}", response_model=List[schemas.HobbyPostResponse])
def get_posts_by_category(category_id: int, db: Session = Depends(get_db)):
    posts = db.query(models.HobbyPost).filter(
        models.HobbyPost.hobby_category_id == category_id
    ).order_by(models.HobbyPost.created_at.desc()).all()
    
    for post in posts:
        user = db.query(models.User).filter(models.User.id == post.user_id).first()
        post.author_nickname = user.nickname if user else "Unknown"
        post.public_code = user.public_code if user else "-------" # ✅ これで表示される
    return posts

@router.get("/posts/{post_id}", response_model=HobbyPostResponse, tags=["posts"])
def get_hobby_post_detail(post_id: int, db: Session = Depends(get_db)):
    """投稿の詳細"""
    post = db.query(models.HobbyPost).filter(models.HobbyPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")
    
    # 投稿者情報
    user = db.query(models.User).filter(models.User.id == post.user_id).first()
    post.author_nickname = user.nickname if user else "Unknown"
    
    # 返信数・参加表明数
    post.response_count = db.query(func.count(models.PostResponse.id)).filter(
        models.PostResponse.post_id == post_id
    ).scalar() or 0
    
    post.participation_count = db.query(func.count(models.PostResponse.id)).filter(
        models.PostResponse.post_id == post_id,
        models.PostResponse.is_participation == True
    ).scalar() or 0
    
    return post

# ==========================================
# 💡 投稿への返信（コメント・参加表明）
# ==========================================

@router.post("/posts/{post_id}/responses", response_model=PostResponseResponse, tags=["responses"])
def create_post_response(
    post_id: int,
    response: PostResponseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user), 
):
    """投稿への返信/参加表明を作成"""
    # 1. 投稿存在チェック
    post = db.query(models.HobbyPost).filter(models.HobbyPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")

    # 2. 【Meetup定員チェック】ロジックの復元
    if response.is_participation and post.is_meetup and post.meetup_capacity:
        current_participants = db.query(func.count(models.PostResponse.id)).filter(
            models.PostResponse.post_id == post_id,
            models.PostResponse.is_participation == True
        ).scalar() or 0

        # すでに参加表明済みかチェック
        is_already_participated = db.query(models.PostResponse).filter(
            models.PostResponse.post_id == post_id,
            models.PostResponse.user_id == current_user.id,
            models.PostResponse.is_participation == True
        ).first()
        
        # 参加表明の場合、定員超過をチェック (すでに参加済みの場合はカウントしない)
        if not is_already_participated and current_participants >= post.meetup_capacity:
            raise HTTPException(
                status_code=400,
                detail=f"Meetupの定員({post.meetup_capacity}名)を超過しています。"
            )
        
    # 3. 返信作成
    db_response = models.PostResponse(
        content=response.content,
        is_participation=response.is_participation,
        user_id=current_user.id,
        post_id=post_id
    )
    
    db.add(db_response)
    db.commit()
    db.refresh(db_response)
    
    # 4. 返信者のニックネームを追加 (レスポンス用)
    db_response.author_nickname = current_user.nickname
    return db_response

@router.get("/posts/{post_id}/responses", response_model=List[PostResponseResponse], tags=["responses"])
def get_post_responses(post_id: int, db: Session = Depends(get_db)):
    """投稿への返信一覧を取得"""
    # 1. 投稿存在チェック (冗長でなければ省略可)
    post = db.query(models.HobbyPost).filter(models.HobbyPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")
        
    responses = db.query(models.PostResponse).filter(
        models.PostResponse.post_id == post_id
    ).order_by(models.PostResponse.created_at).all()
    
    # 2. 返信者のニックネームを追加
    for res in responses:
        user = db.query(models.User).filter(models.User.id == res.user_id).first()
        res.author_nickname = user.nickname if user else "Unknown"
        
    return responses

