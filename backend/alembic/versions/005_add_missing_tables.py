"""005_add_missing_tables

补全对话历史、文档权限表

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '005e6f7g8h9i'
down_revision: Union[str, None] = '004d5e6f7g8h'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('user_document_permissions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('document_id', sa.BigInteger(), sa.ForeignKey('documents.id'), nullable=False),
        sa.Column('granted_by', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('permission_type', sa.String(length=16), nullable=False, server_default=sa.text("'download'")),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_user_document_permissions_user_id'), 'user_document_permissions', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_document_permissions_document_id'), 'user_document_permissions', ['document_id'], unique=False)

    op.create_table('conversations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False, server_default=sa.text("'新对话'")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_conversations_user_id'), 'conversations', ['user_id'], unique=False)

    op.create_table('conversation_messages',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('conversation_id', sa.BigInteger(), sa.ForeignKey('conversations.id'), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False, server_default=''),
        sa.Column('sources', postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_conversation_messages_conversation_id'), 'conversation_messages', ['conversation_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_conversation_messages_conversation_id'), table_name='conversation_messages')
    op.drop_table('conversation_messages')
    op.drop_index(op.f('ix_conversations_user_id'), table_name='conversations')
    op.drop_table('conversations')
    op.drop_index(op.f('ix_user_document_permissions_document_id'), table_name='user_document_permissions')
    op.drop_index(op.f('ix_user_document_permissions_user_id'), table_name='user_document_permissions')
    op.drop_table('user_document_permissions')