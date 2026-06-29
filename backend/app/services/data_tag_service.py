from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ResourceNotFoundError, BusinessError
from app.models.data_tag import DataTagCategory, DataTag
from app.schemas.tag import (
    DataTagCategoryCreate,
    DataTagCategoryUpdate,
    DataTagCategoryResponse,
    DataTagCategoryDetailResponse,
    DataTagCreate,
    DataTagUpdate,
    DataTagResponse,
)


class DataTagService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== 标签分类管理 ====================

    async def list_categories(self) -> List[DataTagCategoryResponse]:
        """获取所有标签分类（含标签数量）"""
        result = await self.db.execute(
            select(DataTagCategory)
            .options(selectinload(DataTagCategory.tags))
            .order_by(DataTagCategory.sort_order, DataTagCategory.id)
        )
        categories = result.scalars().all()
        return [
            DataTagCategoryResponse(
                id=c.id,
                name=c.name,
                code=c.code,
                description=c.description,
                color=c.color,
                sort_order=c.sort_order,
                is_system=c.is_system,
                tag_count=len(c.tags),
                created_at=c.created_at,
            )
            for c in categories
        ]

    async def get_category_detail(self, category_id: int) -> DataTagCategoryDetailResponse:
        """获取分类详情（含标签列表）"""
        result = await self.db.execute(
            select(DataTagCategory)
            .options(selectinload(DataTagCategory.tags))
            .where(DataTagCategory.id == category_id)
        )
        category = result.scalar_one_or_none()
        if not category:
            raise ResourceNotFoundError(detail="标签分类不存在")

        sorted_tags = sorted(category.tags, key=lambda t: (t.sort_order, t.id))
        return DataTagCategoryDetailResponse(
            id=category.id,
            name=category.name,
            code=category.code,
            description=category.description,
            color=category.color,
            sort_order=category.sort_order,
            is_system=category.is_system,
            tag_count=len(category.tags),
            created_at=category.created_at,
            tags=[
                DataTagResponse(
                    id=t.id,
                    category_id=t.category_id,
                    name=t.name,
                    description=t.description,
                    sort_order=t.sort_order,
                    created_at=t.created_at,
                )
                for t in sorted_tags
            ],
        )

    async def get_all_tags_grouped(self) -> dict:
        """获取所有分类和标签（供上传页面、筛选等全局使用，返回字典格式keyed by code）"""
        result = await self.db.execute(
            select(DataTagCategory)
            .options(selectinload(DataTagCategory.tags))
            .order_by(DataTagCategory.sort_order, DataTagCategory.id)
        )
        categories = result.scalars().all()
        groups = {}
        for c in categories:
            sorted_tags = sorted(c.tags, key=lambda t: (t.sort_order, t.id))
            groups[c.code] = {
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "color": c.color,
                "tags": [
                    {"id": t.id, "name": t.name}
                    for t in sorted_tags
                ],
            }
        return groups

    async def get_all_categories_with_tags(self) -> list:
        """获取所有分类和标签（返回数组格式）"""
        result = await self.db.execute(
            select(DataTagCategory)
            .options(selectinload(DataTagCategory.tags))
            .order_by(DataTagCategory.sort_order, DataTagCategory.id)
        )
        categories = result.scalars().all()
        result_list = []
        for c in categories:
            sorted_tags = sorted(c.tags, key=lambda t: (t.sort_order, t.id))
            result_list.append({
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "description": c.description,
                "color": c.color,
                "sort_order": c.sort_order,
                "tags": [
                    {"id": t.id, "name": t.name, "sort_order": t.sort_order}
                    for t in sorted_tags
                ],
            })
        return result_list

    async def create_category(self, data: DataTagCategoryCreate) -> DataTagCategoryResponse:
        """创建标签分类"""
        code = data.code.strip().lower()
        name = data.name.strip()

        existing = await self.db.execute(
            select(DataTagCategory).where(
                (DataTagCategory.code == code) | (DataTagCategory.name == name)
            )
        )
        if existing.scalar_one_or_none():
            raise BusinessError(detail="分类编码或名称已存在")

        category = DataTagCategory(
            name=name,
            code=code,
            description=data.description.strip() if data.description else None,
            color=data.color or "primary",
            sort_order=data.sort_order or 0,
            is_system=0,
        )
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)

        return DataTagCategoryResponse(
            id=category.id,
            name=category.name,
            code=category.code,
            description=category.description,
            color=category.color,
            sort_order=category.sort_order,
            is_system=category.is_system,
            tag_count=0,
            created_at=category.created_at,
        )

    async def update_category(self, category_id: int, data: DataTagCategoryUpdate) -> DataTagCategoryResponse:
        """更新标签分类"""
        result = await self.db.execute(
            select(DataTagCategory)
            .options(selectinload(DataTagCategory.tags))
            .where(DataTagCategory.id == category_id)
        )
        category = result.scalar_one_or_none()
        if not category:
            raise ResourceNotFoundError(detail="标签分类不存在")

        if data.name is not None:
            name = data.name.strip()
            existing = await self.db.execute(
                select(DataTagCategory).where(
                    DataTagCategory.name == name,
                    DataTagCategory.id != category_id,
                )
            )
            if existing.scalar_one_or_none():
                raise BusinessError(detail="分类名称已存在")
            category.name = name

        if data.description is not None:
            category.description = data.description.strip() if data.description.strip() else None

        if data.color is not None:
            category.color = data.color

        if data.sort_order is not None:
            category.sort_order = data.sort_order

        await self.db.commit()
        await self.db.refresh(category)

        return DataTagCategoryResponse(
            id=category.id,
            name=category.name,
            code=category.code,
            description=category.description,
            color=category.color,
            sort_order=category.sort_order,
            is_system=category.is_system,
            tag_count=len(category.tags),
            created_at=category.created_at,
        )

    async def delete_category(self, category_id: int) -> dict:
        """删除标签分类（系统内置分类不可删除，分类下有标签不可删除）"""
        result = await self.db.execute(
            select(DataTagCategory)
            .options(selectinload(DataTagCategory.tags))
            .where(DataTagCategory.id == category_id)
        )
        category = result.scalar_one_or_none()
        if not category:
            raise ResourceNotFoundError(detail="标签分类不存在")

        if category.is_system == 1:
            raise BusinessError(detail="系统内置分类不可删除")

        if len(category.tags) > 0:
            raise BusinessError(detail=f"分类 \"{category.name}\" 下还有 {len(category.tags)} 个标签，请先删除标签")

        await self.db.delete(category)
        await self.db.commit()
        return {"detail": "分类已删除"}

    # ==================== 标签值管理 ====================

    async def list_tags(self, category_id: Optional[int] = None) -> List[DataTagResponse]:
        """获取标签列表，可按分类筛选"""
        query = select(DataTag).order_by(DataTag.sort_order, DataTag.id)
        if category_id is not None:
            query = query.where(DataTag.category_id == category_id)

        result = await self.db.execute(query)
        tags = result.scalars().all()
        return [
            DataTagResponse(
                id=t.id,
                category_id=t.category_id,
                name=t.name,
                description=t.description,
                sort_order=t.sort_order,
                created_at=t.created_at,
            )
            for t in tags
        ]

    async def create_tag(self, data: DataTagCreate) -> DataTagResponse:
        """创建标签"""
        cat_result = await self.db.execute(
            select(DataTagCategory).where(DataTagCategory.id == data.category_id)
        )
        category = cat_result.scalar_one_or_none()
        if not category:
            raise ResourceNotFoundError(detail="所属分类不存在")

        name = data.name.strip()

        existing = await self.db.execute(
            select(DataTag).where(
                DataTag.category_id == data.category_id,
                DataTag.name == name,
            )
        )
        if existing.scalar_one_or_none():
            raise BusinessError(detail=f"标签 \"{name}\" 在分类 \"{category.name}\" 中已存在")

        tag = DataTag(
            category_id=data.category_id,
            name=name,
            description=data.description.strip() if data.description else None,
            sort_order=data.sort_order or 0,
        )
        self.db.add(tag)
        await self.db.commit()
        await self.db.refresh(tag)

        return DataTagResponse(
            id=tag.id,
            category_id=tag.category_id,
            name=tag.name,
            description=tag.description,
            sort_order=tag.sort_order,
            created_at=tag.created_at,
        )

    async def update_tag(self, tag_id: int, data: DataTagUpdate) -> DataTagResponse:
        """更新标签"""
        result = await self.db.execute(select(DataTag).where(DataTag.id == tag_id))
        tag = result.scalar_one_or_none()
        if not tag:
            raise ResourceNotFoundError(detail="标签不存在")

        if data.name is not None:
            name = data.name.strip()
            existing = await self.db.execute(
                select(DataTag).where(
                    DataTag.category_id == tag.category_id,
                    DataTag.name == name,
                    DataTag.id != tag_id,
                )
            )
            if existing.scalar_one_or_none():
                raise BusinessError(detail="同分类下已存在同名标签")
            tag.name = name

        if data.description is not None:
            tag.description = data.description.strip() if data.description.strip() else None

        if data.sort_order is not None:
            tag.sort_order = data.sort_order

        await self.db.commit()
        await self.db.refresh(tag)

        return DataTagResponse(
            id=tag.id,
            category_id=tag.category_id,
            name=tag.name,
            description=tag.description,
            sort_order=tag.sort_order,
            created_at=tag.created_at,
        )

    async def delete_tag(self, tag_id: int) -> dict:
        """删除标签"""
        result = await self.db.execute(select(DataTag).where(DataTag.id == tag_id))
        tag = result.scalar_one_or_none()
        if not tag:
            raise ResourceNotFoundError(detail="标签不存在")

        await self.db.delete(tag)
        await self.db.commit()
        return {"detail": "标签已删除", "tag_id": tag_id, "category_id": tag.category_id}
