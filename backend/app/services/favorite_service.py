from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, desc, delete, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError, BusinessError
from app.models.user import User
from app.models.document import Document
from app.models.user_favorite import UserFavorite
from app.models.audit_log import AuditLog


class FavoriteService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_favorite(self, user: User, document_id: int) -> dict:
        doc = await self.db.get(Document, document_id)
        if not doc:
            raise ResourceNotFoundError(detail="文档不存在")

        existing = await self.db.execute(
            select(UserFavorite).where(
                and_(
                    UserFavorite.user_id == user.id,
                    UserFavorite.document_id == document_id,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise BusinessError(detail="该文档已在收藏列表中")

        fav = UserFavorite(user_id=user.id, document_id=document_id)
        self.db.add(fav)
        await self.db.commit()
        await self.db.refresh(fav)

        return {
            "id": fav.id,
            "document_id": document_id,
            "message": "收藏成功",
        }

    async def remove_favorite(self, user: User, document_id: int) -> dict:
        result = await self.db.execute(
            select(UserFavorite).where(
                and_(
                    UserFavorite.user_id == user.id,
                    UserFavorite.document_id == document_id,
                )
            )
        )
        fav = result.scalar_one_or_none()
        if not fav:
            raise ResourceNotFoundError(detail="收藏记录不存在")

        await self.db.execute(
            delete(UserFavorite).where(UserFavorite.id == fav.id)
        )
        await self.db.commit()
        return {"message": "已取消收藏"}

    async def get_user_favorites(self, user: User, page: int, page_size: int) -> dict:
        """获取用户的收藏列表，关联文档信息（含来源类型判断）"""
        from sqlalchemy import func

        count_query = select(func.count(UserFavorite.id)).where(UserFavorite.user_id == user.id)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(UserFavorite)
            .where(UserFavorite.user_id == user.id)
            .order_by(desc(UserFavorite.created_at))
            .offset(offset)
            .limit(page_size)
        )
        favs: List[UserFavorite] = list(result.scalars().all())

        items = []
        for f in favs:
            doc = f.document
            if not doc:
                continue

            # 判断来源类型
            is_privileged = (user.role and user.role.role_code in ("SUPER_ADMIN", "ADMIN", "REVIEWER"))
            if is_privileged:
                source_type = "PRIVILEGED"
            elif doc.uploader_id == user.id:
                source_type = "UPLOADER"
            else:
                # 检查是否还有有效授权
                from app.models.user_document_permission import UserDocumentPermission
                from datetime import datetime
                auth_result = await self.db.execute(
                    select(UserDocumentPermission).where(
                        UserDocumentPermission.user_id == user.id,
                        UserDocumentPermission.document_id == doc.id,
                        or_(
                            UserDocumentPermission.expires_at.is_(None),
                            UserDocumentPermission.expires_at > datetime.now(timezone.utc),
                        ),
                    )
                )
                if auth_result.scalar_one_or_none():
                    source_type = "AUTHORIZED"
                else:
                    # 检查scope匹配
                    from app.core.permissions import get_user_data_scopes, check_document_access
                    user_scopes = await get_user_data_scopes(self.db, user.id)
                    scope_access = check_document_access(
                        user_scopes, doc.model_tag, doc.region_tag, doc.doc_type_tag,
                        is_super_admin=False,
                    )
                    if scope_access == "DIRECT":
                        source_type = "SCOPE_MATCH"
                    else:
                        source_type = "AUTHORIZED_EXPIRED"  # 授权已过期/已撤销

            # 提取文件格式
            _, file_ext = __import__("os").path.splitext(doc.name.lower()) if doc and doc.name else ("", "")
            file_format = file_ext.lstrip(".").upper() if file_ext else "-"

            item = {
                "id": f.id,
                "document_id": f.document_id,
                "document_name": doc.name if doc else "",
                "file_size": doc.file_size if doc else 0,
                "format": file_format,
                "model_tag": doc.model_tag if doc else "",
                "region_tag": doc.region_tag if doc else "",
                "doc_type_tag": doc.doc_type_tag if doc else "",
                "status": doc.status if doc else 0,
                "created_at": f.created_at,
                "source_type": source_type,
            }
            items.append(item)

        return {"total": total, "items": items}

    async def get_download_history(self, user: User, page: int, page_size: int) -> dict:
        """从审计日志获取用户的下载记录（DOWNLOAD + DOWNLOAD_BY_TOKEN）"""
        from sqlalchemy import func

        count_query = select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.user_id == user.id,
                AuditLog.operation_type.in_(["DOWNLOAD", "DOWNLOAD_BY_TOKEN"]),
            )
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(AuditLog)
            .where(
                and_(
                    AuditLog.user_id == user.id,
                    AuditLog.operation_type.in_(["DOWNLOAD", "DOWNLOAD_BY_TOKEN"]),
                )
            )
            .order_by(desc(AuditLog.created_at))
            .offset(offset)
            .limit(page_size)
        )
        logs: List[AuditLog] = list(result.scalars().all())

        items = []
        for log in logs:
            content = log.operation_content or {}
            document_id = content.get("document_id", 0)
            document_name = content.get("document_name", "")
            items.append({
                "id": log.id,
                "document_id": document_id,
                "document_name": document_name,
                "operation_type": log.operation_type,
                "created_at": log.created_at,
            })

        return {"total": total, "items": items}