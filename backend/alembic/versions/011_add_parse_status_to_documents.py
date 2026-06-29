"""011_add_parse_status_to_documents

记录文档解析状态，修复状态更新空函数问题

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '011k2l3m4n5o'
down_revision: Union[str, None] = '010j1k2l3m4n'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加文档解析状态字段
    # chunk_count: 解析后的分块数量,0=未解析
    op.add_column('documents', sa.Column('chunk_count', sa.Integer(), nullable=False, server_default=sa.text('0')))
    # is_parsed: 0=未解析, 1=已解析
    op.add_column('documents', sa.Column('is_parsed', sa.SmallInteger(), nullable=False, server_default=sa.text('0')))
    # parsed_at: 解析完成时间
    op.add_column('documents', sa.Column('parsed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'parsed_at')
    op.drop_column('documents', 'is_parsed')
    op.drop_column('documents', 'chunk_count')
