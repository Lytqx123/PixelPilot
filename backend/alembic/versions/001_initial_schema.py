"""001_initial_schema

初始化全部核心表结构

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001a1b2c3d4e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('departments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index(op.f('ix_departments_code'), 'departments', ['code'], unique=True)

    op.create_table('roles',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('role_code', sa.String(length=64), nullable=False),
        sa.Column('role_name', sa.String(length=64), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('department_id', sa.BigInteger(), sa.ForeignKey('departments.id'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_code'),
    )
    op.create_index(op.f('ix_roles_role_code'), 'roles', ['role_code'], unique=True)

    op.create_table('users',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('real_name', sa.String(length=64), nullable=False),
        sa.Column('gender', sa.String(length=8), nullable=False, server_default=''),
        sa.Column('phone', sa.String(length=32), nullable=False, server_default=''),
        sa.Column('personal_description', sa.String(length=512), nullable=False, server_default=''),
        sa.Column('role_id', sa.BigInteger(), sa.ForeignKey('roles.id'), nullable=False),
        sa.Column('department_id', sa.BigInteger(), sa.ForeignKey('departments.id'), nullable=True),
        sa.Column('status', sa.SmallInteger(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    op.create_table('documents',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('uploader_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('department_id', sa.BigInteger(), sa.ForeignKey('departments.id'), nullable=True),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=True, server_default=sa.text('0')),
        sa.Column('model_tag', sa.String(length=512), nullable=True, server_default=''),
        sa.Column('region_tag', sa.String(length=512), nullable=True, server_default=''),
        sa.Column('doc_type_tag', sa.String(length=512), nullable=True, server_default=''),
        sa.Column('upload_type', sa.String(length=16), nullable=False, server_default=sa.text("'regular'")),
        sa.Column('access_mode', sa.String(length=32), nullable=False, server_default=sa.text("'department_public'")),
        sa.Column('is_public_to_all', sa.SmallInteger(), nullable=False, server_default=sa.text('0')),
        sa.Column('status', sa.SmallInteger(), nullable=False, server_default=sa.text('0')),
        sa.Column('reviewer_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('review_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('document_chunks',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.BigInteger(), sa.ForeignKey('documents.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True, server_default=sa.text('0')),
        sa.Column('paragraph', sa.String(length=64), nullable=True, server_default=''),
        sa.Column('vector_id', sa.String(length=64), nullable=True, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('access_applications',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('applicant_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('document_id', sa.BigInteger(), sa.ForeignKey('documents.id'), nullable=False),
        sa.Column('reason', sa.String(length=512), nullable=True, server_default=''),
        sa.Column('status', sa.SmallInteger(), nullable=False, server_default=sa.text('0')),
        sa.Column('reviewer_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('review_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('temp_access_tokens',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('document_id', sa.BigInteger(), sa.ForeignKey('documents.id'), nullable=False),
        sa.Column('permission_type', sa.String(length=16), nullable=False, server_default=sa.text("'download'")),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index(op.f('ix_temp_access_tokens_token'), 'temp_access_tokens', ['token'], unique=True)

    op.create_table('audit_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('operation_type', sa.String(length=64), nullable=False),
        sa.Column('operation_content', postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'")),
        sa.Column('ip_address', sa.String(length=64), nullable=True, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('user_data_scopes',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('model_tag', sa.String(length=64), nullable=False),
        sa.Column('region_tag', sa.String(length=64), nullable=False),
        sa.Column('doc_type_tag', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'model_tag', 'region_tag', 'doc_type_tag', name='uq_user_scope'),
    )


def downgrade() -> None:
    op.drop_table('user_data_scopes')
    op.drop_table('audit_logs')
    op.drop_index(op.f('ix_temp_access_tokens_token'), table_name='temp_access_tokens')
    op.drop_table('temp_access_tokens')
    op.drop_table('access_applications')
    op.drop_table('document_chunks')
    op.drop_table('documents')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_roles_role_code'), table_name='roles')
    op.drop_table('roles')
    op.drop_index(op.f('ix_departments_code'), table_name='departments')
    op.drop_table('departments')