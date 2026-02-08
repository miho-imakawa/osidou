"""add_parent_id_to_hobby_posts

Revision ID: 60d1e0277e36
Revises: cc2f559fa232
Create Date: 2026-02-04 21:31:37.146204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60d1e0277e36'
down_revision: Union[str, Sequence[str], None] = 'cc2f559fa232'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 修正後（SQLite対応版）
def upgrade():
    with op.batch_alter_table('hobby_posts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('parent_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_hobby_posts_parent_id', 'hobby_posts', ['parent_id'], ['id'])

def downgrade():
    with op.batch_alter_table('hobby_posts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_hobby_posts_parent_id', type_='foreignkey')
        batch_op.drop_column('parent_id')