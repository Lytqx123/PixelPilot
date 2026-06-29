"""002_add_system_tags

添加系统预设标签表

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '002b3c4d5e6f'
down_revision: Union[str, None] = '001a1b2c3d4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('system_tags',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tag_type', sa.String(length=16), nullable=False),
        sa.Column('tag_value', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tag_type', 'tag_value', name='uq_tag_type_value'),
    )
    op.create_index(op.f('ix_system_tags_tag_type'), 'system_tags', ['tag_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_system_tags_tag_type'), table_name='system_tags')
    op.drop_table('system_tags')