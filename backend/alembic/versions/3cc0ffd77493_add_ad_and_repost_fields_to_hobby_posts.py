"""add ad and repost fields to hobby_posts

Revision ID: 3cc0ffd77493
Revises: ef8fc2847f66
Create Date: 2026-01-03 15:21:39.432387

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3cc0ffd77493'
down_revision: Union[str, Sequence[str], None] = 'ef8fc2847f66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. まずカラムだけを追加（制約なし）
    with op.batch_alter_table('hobby_posts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_ad', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('ad_end_date', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('original_post_id', sa.Integer(), nullable=True))

    # 2. カラムが存在する状態で、改めて外部キー制約だけを付与する
    with op.batch_alter_table('hobby_posts', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_hobby_posts_original_post', 'hobby_posts', ['original_post_id'], ['id'])

def downgrade() -> None:
    with op.batch_alter_table('hobby_posts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_hobby_posts_original_post', type_='foreignkey')
        batch_op.drop_column('original_post_id')
        batch_op.drop_column('ad_end_date')
        batch_op.drop_column('is_ad')