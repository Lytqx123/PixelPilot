"""012_add_assigned_reviewer_ids_to_access_applications

修复申请表缺失审核人ID字段，解决接口500错误

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = '012l3m4n5o6p'
down_revision: Union[str, None] = '011k2l3m4n5o'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 幂等添加 assigned_reviewer_ids 列（若已存在则跳过）
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('access_applications')]
    if 'assigned_reviewer_ids' not in columns:
        op.add_column(
            'access_applications',
            sa.Column('assigned_reviewer_ids', JSONB(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column('access_applications', 'assigned_reviewer_ids')
