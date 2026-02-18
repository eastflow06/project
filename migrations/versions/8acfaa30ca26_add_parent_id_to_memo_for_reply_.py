"""Add parent_id to Memo for reply functionality

Revision ID: 8acfaa30ca26
Revises: d178102da929
Create Date: 2024-08-22 09:45:58.916467

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8acfaa30ca26'
down_revision = 'd178102da929'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('memo', schema=None) as batch_op:
        batch_op.add_column(sa.Column('parent_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_memo_parent_id',  # 외래 키 제약 조건의 이름을 명시적으로 지정
            'memo',  # 참조하는 테이블
            ['parent_id'],  # 외래 키 컬럼
            ['id']  # 참조하는 컬럼
        )

def downgrade():
    with op.batch_alter_table('memo', schema=None) as batch_op:
        batch_op.drop_constraint('fk_memo_parent_id', type_='foreignkey')
        batch_op.drop_column('parent_id')

    # ### end Alembic commands ###
