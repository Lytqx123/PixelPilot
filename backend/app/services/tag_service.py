from typing import Optional, List

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError, BusinessError
from app.models.system_tag import SystemTag

VALID_TAG_TYPES = {"model", "region", "doc_type"}


class TagService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_tags_by_type(self) -> dict:
        """获取按类型分组的标签列表（供上传页面和全局使用）"""
        result = await self.db.execute(
            select(SystemTag).order_by(SystemTag.tag_type, SystemTag.tag_value)
        )
        tags: List[SystemTag] = list(result.scalars().all())

        model_tags = sorted(set(t.tag_value for t in tags if t.tag_type == "model"))
        region_tags = sorted(set(t.tag_value for t in tags if t.tag_type == "region"))
        doc_type_tags = sorted(set(t.tag_value for t in tags if t.tag_type == "doc_type"))

        return {
            "model_tags": model_tags,
            "region_tags": region_tags,
            "doc_type_tags": doc_type_tags,
        }

    async def get_tag_list(self, tag_type: Optional[str] = None) -> list:
        """获取标签列表，可按类型筛选"""
        query = select(SystemTag).order_by(SystemTag.tag_type, SystemTag.tag_value)
        if tag_type:
            if tag_type not in VALID_TAG_TYPES:
                raise BusinessError(detail=f"无效的标签类型: {tag_type}，支持: {', '.join(sorted(VALID_TAG_TYPES))}")
            query = query.where(SystemTag.tag_type == tag_type)

        result = await self.db.execute(query)
        tags: List[SystemTag] = list(result.scalars().all())
        return [
            {"id": t.id, "tag_type": t.tag_type, "tag_value": t.tag_value, "created_at": t.created_at}
            for t in tags
        ]

    async def create_tag(self, tag_type: str, tag_value: str) -> dict:
        """创建标签（检查唯一性，类型校验）"""
        if tag_type not in VALID_TAG_TYPES:
            raise BusinessError(detail=f"无效的标签类型: {tag_type}，支持: {', '.join(sorted(VALID_TAG_TYPES))}")

        tag_value = tag_value.strip()
        if not tag_value:
            raise BusinessError(detail="标签值不能为空")

        # 检查重复
        existing = await self.db.execute(
            select(SystemTag).where(
                SystemTag.tag_type == tag_type,
                SystemTag.tag_value == tag_value,
            )
        )
        if existing.scalar_one_or_none():
            raise BusinessError(detail=f"标签 '{tag_value}' 已存在（类型: {tag_type}）")

        tag = SystemTag(tag_type=tag_type, tag_value=tag_value)
        self.db.add(tag)
        await self.db.commit()
        await self.db.refresh(tag)

        return {"id": tag.id, "tag_type": tag.tag_type, "tag_value": tag.tag_value, "created_at": tag.created_at}

    async def update_tag(self, tag_id: int, tag_value: str) -> dict:
        """更新标签值（检查唯一性）"""
        result = await self.db.execute(select(SystemTag).where(SystemTag.id == tag_id))
        tag = result.scalar_one_or_none()
        if not tag:
            raise ResourceNotFoundError(detail="标签不存在")

        tag_value = tag_value.strip()
        if not tag_value:
            raise BusinessError(detail="标签值不能为空")

        # 检查重复（排除自身）
        existing = await self.db.execute(
            select(SystemTag).where(
                SystemTag.tag_type == tag.tag_type,
                SystemTag.tag_value == tag_value,
                SystemTag.id != tag_id,
            )
        )
        if existing.scalar_one_or_none():
            raise BusinessError(detail=f"标签 '{tag_value}' 已存在（类型: {tag.tag_type}）")

        old_value = tag.tag_value
        tag.tag_value = tag_value
        await self.db.commit()
        await self.db.refresh(tag)

        return {"id": tag.id, "tag_type": tag.tag_type, "old_value": old_value, "new_value": tag_value}

    async def delete_tag(self, tag_id: int) -> dict:
        """删除标签"""
        result = await self.db.execute(select(SystemTag).where(SystemTag.id == tag_id))
        tag = result.scalar_one_or_none()
        if not tag:
            raise ResourceNotFoundError(detail="标签不存在")

        tag_value = tag.tag_value
        tag_type = tag.tag_type
        await self.db.execute(delete(SystemTag).where(SystemTag.id == tag_id))
        await self.db.commit()

        return {"deleted": True, "tag_type": tag_type, "tag_value": tag_value}
