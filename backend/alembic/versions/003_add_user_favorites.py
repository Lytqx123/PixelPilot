"""003_add_user_favorites

添加用户收藏功能

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '003c4d5e6f7g'
down_revision: Union[str, None] = '002b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('user_favorites',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('document_id', sa.BigInteger(), sa.ForeignKey('documents.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'document_id', name='uq_user_favorite'),
    )


def downgrade() -> None:
    op.drop_table('user_favorites')