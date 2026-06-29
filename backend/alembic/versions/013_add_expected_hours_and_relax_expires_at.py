"""013_add_expected_hours_and_relax_expires_at

添加期望授权时长，支持永久授权

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '013m4n5o6p7q'
down_revision: Union[str, None] = '012l3m4n5o6p'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. access_applications 添加 expected_hours 列
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    app_cols = [c['name'] for c in inspector.get_columns('access_applications')]
    if 'expected_hours' not in app_cols:
        op.add_column(
            'access_applications',
            sa.Column('expected_hours', sa.SmallInteger(), nullable=True),
        )

    # 2. temp_access_tokens.expires_at 改为可空（支持永久授权）
    token_cols = {c['name']: c for c in inspector.get_columns('temp_access_tokens')}
    if 'expires_at' in token_cols and not token_cols['expires_at']['nullable']:
        op.alter_column(
            'temp_access_tokens',
            'expires_at',
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )


def downgrade() -> None:
    # 回滚 expires_at 为非空（注意：已有 NULL 数据需先处理）
    op.alter_column(
        'temp_access_tokens',
        'expires_at',
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.drop_column('access_applications', 'expected_hours')
