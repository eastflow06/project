"""Add product_id to Memo model

Revision ID: 0fb4e263cbdc
Revises: 4d38c1990b92
Create Date: 2024-10-08 09:57:07.011869

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0fb4e263cbdc'
down_revision = '4d38c1990b92'
branch_labels = None
depends_on = None


def upgrade():
    # `memo` 테이블에 product_id 추가
    with op.batch_alter_table('memo', schema=None) as batch_op:
        batch_op.add_column(sa.Column('product_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_memo_product_id'), ['product_id'], unique=False)
        batch_op.create_foreign_key('fk_memo_product_id', 'product', ['product_id'], ['id'])

def downgrade():
    # `memo` 테이블에서 product_id 제거
    with op.batch_alter_table('memo', schema=None) as batch_op:
        batch_op.drop_constraint('fk_memo_product_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_memo_product_id'))
        batch_op.drop_column('product_id')
