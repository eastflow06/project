"""Add category_id and subcategory_id to Infolink

Revision ID: 4d38c1990b92
Revises: 2ca3c32518c2
Create Date: 2024-09-28 16:42:03.116176

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d38c1990b92'
down_revision = '2ca3c32518c2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('infolink', schema=None) as batch_op:
        # 현재 필드를 유지하고 삭제하지 않음
        pass  # 아무 작업도 하지 않음

def downgrade():
    with op.batch_alter_table('infolink', schema=None) as batch_op:
        batch_op.add_column(sa.Column('subcategory', sa.VARCHAR(length=100), nullable=True))
        batch_op.add_column(sa.Column('category', sa.VARCHAR(length=100), nullable=False))
        batch_op.drop_column('subcategory_id')  # 기존 외래 키 필드를 제거
        batch_op.drop_column('category_id')  # 기존 외래 키 필드를 제거

    # ### end Alembic commands ###
