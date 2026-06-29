"""014_add_data_tags

新增数据标签分类管理功能

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '014n5o6p7q8r'
down_revision: Union[str, None] = '013m4n5o6p7q'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. 创建数据标签分类表 data_tag_categories
    tables = inspector.get_table_names()
    if 'data_tag_categories' not in tables:
        op.create_table(
            'data_tag_categories',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=64), nullable=False),
            sa.Column('code', sa.String(length=64), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('color', sa.String(length=16), nullable=False, server_default='primary'),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_system', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name', name='uq_data_tag_category_name'),
            sa.UniqueConstraint('code', name='uq_data_tag_category_code'),
        )
        op.create_index(op.f('ix_data_tag_categories_code'), 'data_tag_categories', ['code'], unique=True)

    # 2. 创建数据标签表 data_tags
    if 'data_tags' not in tables:
        op.create_table(
            'data_tags',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('category_id', sa.BigInteger(), nullable=False),
            sa.Column('name', sa.String(length=64), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(['category_id'], ['data_tag_categories.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('category_id', 'name', name='uq_category_tag_name'),
        )
        op.create_index(op.f('ix_data_tags_category_id'), 'data_tags', ['category_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'data_tags' in tables:
        op.drop_index(op.f('ix_data_tags_category_id'), table_name='data_tags')
        op.drop_table('data_tags')

    if 'data_tag_categories' in tables:
        op.drop_index(op.f('ix_data_tag_categories_code'), table_name='data_tag_categories')
        op.drop_table('data_tag_categories')
