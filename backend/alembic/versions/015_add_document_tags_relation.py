"""015_add_document_tags_relation

建立文档标签多对多关联，完成标签系统重构

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '015o6p7q8r9s'
down_revision: Union[str, None] = '014n5o6p7q8r'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. 创建 document_tags 多对多关联表
    if 'document_tags' not in tables:
        op.create_table(
            'document_tags',
            sa.Column('document_id', sa.BigInteger(), sa.ForeignKey('documents.id', ondelete='CASCADE'), primary_key=True, nullable=False),
            sa.Column('tag_id', sa.BigInteger(), sa.ForeignKey('data_tags.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        )
        op.create_index(op.f('ix_document_tags_document_id'), 'document_tags', ['document_id'], unique=False)
        op.create_index(op.f('ix_document_tags_tag_id'), 'document_tags', ['tag_id'], unique=False)

    meta = sa.MetaData()
    # 加载需要的表
    categories_tbl = sa.Table('data_tag_categories', meta, autoload_with=bind)
    tags_tbl = sa.Table('data_tags', meta, autoload_with=bind)
    documents_tbl = sa.Table('documents', meta, autoload_with=bind)
    doc_tags_tbl = sa.Table('document_tags', meta, autoload_with=bind)

    # 2. 确保存在三个基础分类（如果文档有数据需要迁移）
    default_categories = [
        {'name': '车型', 'code': 'model', 'description': '车型分类标签', 'color': 'primary', 'sort_order': 1, 'is_system': 0},
        {'name': '区域', 'code': 'region', 'description': '区域分类标签', 'color': 'success', 'sort_order': 2, 'is_system': 0},
        {'name': '文档类型', 'code': 'doc_type', 'description': '文档类型分类标签', 'color': 'warning', 'sort_order': 3, 'is_system': 0},
    ]

    cat_id_map = {}
    for cat in default_categories:
        existing = bind.execute(
            sa.select(categories_tbl.c.id).where(categories_tbl.c.code == cat['code'])
        ).scalar()
        if existing is None:
            result = bind.execute(categories_tbl.insert().values(**cat))
            cat_id_map[cat['code']] = result.inserted_primary_key[0]
        else:
            cat_id_map[cat['code']] = existing

    # 缓存已存在的tag，避免重复查询
    tag_cache = {}  # key: (category_id, tag_name) -> tag_id

    # 预加载所有已有tag
    existing_tags = bind.execute(
        sa.select(tags_tbl.c.id, tags_tbl.c.category_id, tags_tbl.c.name)
    ).all()
    for t in existing_tags:
        tag_cache[(t.category_id, t.name)] = t.id

    # 3. 迁移文档标签数据
    documents = bind.execute(
        sa.select(documents_tbl.c.id, documents_tbl.c.model_tag, documents_tbl.c.region_tag, documents_tbl.c.doc_type_tag)
    ).all()

    for doc_id, model_tag_str, region_tag_str, doc_type_tag_str in documents:
        # 处理三类标签
        tag_fields = [
            ('model', model_tag_str),
            ('region', region_tag_str),
            ('doc_type', doc_type_tag_str),
        ]

        for code, tag_str in tag_fields:
            if not tag_str:
                continue
            cat_id = cat_id_map[code]
            tag_values = [t.strip() for t in tag_str.split(',') if t.strip()]

            for tag_val in tag_values:
                cache_key = (cat_id, tag_val)
                if cache_key in tag_cache:
                    tag_id = tag_cache[cache_key]
                else:
                    # 创建新标签
                    result = bind.execute(
                        tags_tbl.insert().values(category_id=cat_id, name=tag_val, sort_order=0)
                    )
                    tag_id = result.inserted_primary_key[0]
                    tag_cache[cache_key] = tag_id

                # 建立关联（避免重复）
                existing_rel = bind.execute(
                    sa.select(doc_tags_tbl).where(
                        doc_tags_tbl.c.document_id == doc_id,
                        doc_tags_tbl.c.tag_id == tag_id
                    )
                ).first()
                if existing_rel is None:
                    bind.execute(
                        doc_tags_tbl.insert().values(document_id=doc_id, tag_id=tag_id)
                    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'document_tags' in tables:
        op.drop_index(op.f('ix_document_tags_tag_id'), table_name='document_tags')
        op.drop_index(op.f('ix_document_tags_document_id'), table_name='document_tags')
        op.drop_table('document_tags')
