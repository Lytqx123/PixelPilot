"""004_add_admin_role

添加管理员角色权限

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '004d5e6f7g8h'
down_revision: Union[str, None] = '003c4d5e6f7g'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('system_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('config_key', sa.String(length=128), nullable=False),
        sa.Column('config_value', sa.Text(), nullable=False, server_default=''),
        sa.Column('description', sa.String(length=256), nullable=True, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('config_key'),
    )


def downgrade() -> None:
    op.drop_table('system_configs')