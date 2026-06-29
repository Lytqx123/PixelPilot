import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select, func, text, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import JSONB

from app.config import settings
from app.core.exceptions import ResourceNotFoundError, BusinessError
from app.core.config_service import get_config_int
from app.core.permissions import is_super_admin, is_privileged_role
from app.models.user import User
from app.models.document import (
    Document, DocumentChunk,
    ACCESS_MODE_DEPARTMENT_PUBLIC, ACCESS_MODE_APPLY_REQUIRED,
)
from app.models.access_application import AccessApplication
from app.models.temp_token import TempAccessToken
from app.services.audit_service import AuditService
from app.services.vector_service import VectorService


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_svc = AuditService(db)

    async def _check_reviewer_access(self, reviewer_id: int, document_department_id: int) -> User:
        """验证审核员身份和部门权限（公共方法）"""
        result = await self.db.execute(select(User).where(User.id == reviewer_id))
        reviewer = result.scalar_one_or_none()
        if not reviewer:
            raise ResourceNotFoundError(detail="审核员不存在")

        role_code = reviewer.role.role_code if reviewer.role else ""
        if is_super_admin(role_code):
            return reviewer
        if (
            is_privileged_role(role_code)
            and reviewer.department_id is not None
            and document_department_id == reviewer.department_id
        ):
            return reviewer
        raise BusinessError(detail="无权限操作此文档（需为超级管理员或文档所属部门的管理员/审核员）")

    async def get_pending_documents(self, user: User, page: int, page_size: int, keyword: str = None) -> dict:
        """
        获取待审核文档列表（新模型：基于部门归属 + 分配的审核员）
        - 超级管理员：所有待审核文档
        - 其他角色：自己所在部门的待审核文档 + 被显式分配给 review_id=自己 的文档
        """
        user_role_code = user.role.role_code if user.role else ""
        user_dept_id = user.department_id

        base_query = select(Document).where(Document.status == 0)
        count_query = select(func.count(Document.id)).where(Document.status == 0)

        # 过滤：同部门 或 reviewer_id == 当前用户
        if not is_super_admin(user_role_code):
            if user_dept_id is not None:
                dept_filter = or_(
                    Document.department_id == user_dept_id,
                    Document.reviewer_id == user.id,
                )
                base_query = base_query.where(dept_filter)
                count_query = count_query.where(dept_filter)
            else:
                # 没有部门但有 reviewer_id == 用户 id 的文档也可见
                base_query = base_query.where(Document.reviewer_id == user.id)
                count_query = count_query.where(Document.reviewer_id == user.id)

        # 关键词搜索：文档名 / 上传人姓名
        if keyword:
            pattern = f"%{keyword}%"
            kw_filter = or_(
                Document.name.ilike(pattern),
                select(User.real_name).where(User.id == Document.uploader_id).correlate(Document).scalar_subquery().ilike(pattern),
            )
            base_query = base_query.where(kw_filter)
            count_query = count_query.where(kw_filter)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size
        result = await self.db.execute(
            base_query.order_by(Document.created_at.asc()).offset(offset).limit(page_size)
        )
        docs: List[Document] = list(result.scalars().all())
        items = []
        for doc in docs:
            import os as _os
            _, file_ext = _os.path.splitext(doc.name.lower()) if doc.name else ("", "")
            file_format = file_ext.lstrip(".").upper() if file_ext else "-"
            dept_name = doc.department.name if doc.department else "未分配"
            reviewer_name = doc.reviewer.real_name if doc.reviewer else ""
            items.append({
                "id": doc.id, "name": doc.name,
                "uploader_name": doc.uploader.real_name if doc.uploader else "",
                "uploader_id": doc.uploader_id,
                "model_tag": doc.model_tag, "region_tag": doc.region_tag, "doc_type_tag": doc.doc_type_tag,
                "format": file_format,
                "file_size": doc.file_size, "created_at": doc.created_at,
                "department_id": doc.department_id,
                "department_name": dept_name,
                "reviewer_id": doc.reviewer_id,
                "reviewer_name": reviewer_name,
            })
        return {"total": total, "items": items}

    async def approve_document(self, document_id: int, reviewer_id: int,
                                comment: Optional[str] = None,
                                access_mode: Optional[str] = None) -> dict:
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if not document: raise ResourceNotFoundError(detail="文档不存在")
        if document.status != 0: raise BusinessError(detail="文档状态不允许审核")

        await self._check_reviewer_access(reviewer_id, document.department_id)

        # 设置访问模式（如提供），默认为部门内公开
        if access_mode is not None:
            valid_modes = {ACCESS_MODE_DEPARTMENT_PUBLIC, ACCESS_MODE_APPLY_REQUIRED}
            if access_mode not in valid_modes:
                raise BusinessError(detail=f"无效的访问模式，支持: {', '.join(valid_modes)}")
            document.access_mode = access_mode
        else:
            # 默认：部门内公开
            if not document.access_mode:
                document.access_mode = ACCESS_MODE_DEPARTMENT_PUBLIC

        document.status = 1
        document.reviewer_id = reviewer_id
        document.review_time = datetime.now(timezone.utc)
        await self.db.flush()
        await VectorService.update_vector_review_status(document_id, True)
        await self.audit_svc.create_audit_log(
            user_id=reviewer_id, operation_type="REVIEW",
            operation_content={
                "action": "approve", "doc_id": document_id,
                "doc_name": document.name, "comment": comment or "",
                "access_mode": document.access_mode,
            },
        )
        await self.db.commit()
        return {"message": "文档审核通过", "access_mode": document.access_mode}

    async def reject_document(self, document_id: int, reviewer_id: int, comment: Optional[str] = None) -> dict:
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if not document: raise ResourceNotFoundError(detail="文档不存在")
        if document.status != 0: raise BusinessError(detail="文档状态不允许审核")

        await self._check_reviewer_access(reviewer_id, document.department_id)

        document.status = 2
        document.reviewer_id = reviewer_id
        document.review_time = datetime.now(timezone.utc)
        await self.audit_svc.create_audit_log(
            user_id=reviewer_id, operation_type="REVIEW",
            operation_content={"action": "reject", "doc_id": document_id, "doc_name": document.name, "comment": comment or ""},
        )
        await self.db.commit()
        return {"message": "文档已拒绝"}

    async def get_pending_applications(self, user: User, page: int, page_size: int, keyword: str = None) -> dict:
        """
        获取待审核的访问申请列表（新模型：基于部门归属）
        - 超级管理员：所有待审核申请
        - 其他角色：只显示被指定给自己的、本部门文档的待审核申请
        """
        reviewer_id = user.id
        user_role_code = user.role.role_code if user.role else ""
        user_dept_id = user.department_id

        is_super = is_super_admin(user_role_code)

        if is_super:
            # 超级管理员：所有待审核申请（不过滤 assigned_reviewer_ids，也不按部门过滤）
            base_query = select(AccessApplication).where(
                AccessApplication.status == 0,
            )
            count_query = select(func.count(AccessApplication.id)).where(
                AccessApplication.status == 0,
            )
        elif user_dept_id is not None:
            # 非超级管理员：只显示分配给自己的、本部门文档的待审核申请
            visibility_filter = AccessApplication.assigned_reviewer_ids.cast(JSONB).contains([reviewer_id])
            base_query = select(AccessApplication).where(
                visibility_filter,
                AccessApplication.status == 0,
                AccessApplication.document_id.in_(
                    select(Document.id).where(Document.department_id == user_dept_id)
                ),
            )
            count_query = select(func.count(AccessApplication.id)).where(
                visibility_filter,
                AccessApplication.status == 0,
                AccessApplication.document_id.in_(
                    select(Document.id).where(Document.department_id == user_dept_id)
                ),
            )
        else:
            return {"total": 0, "items": []}

        # 关键词搜索：申请人姓名 / 文档名
        if keyword:
            pattern = f"%{keyword}%"
            kw_filter = or_(
                AccessApplication.reason.ilike(pattern),
                AccessApplication.document_id.in_(
                    select(Document.id).where(Document.name.ilike(pattern))
                ),
                AccessApplication.applicant_id.in_(
                    select(User.id).where(
                        or_(User.real_name.ilike(pattern), User.username.ilike(pattern))
                    )
                ),
            )
            base_query = base_query.where(kw_filter)
            count_query = count_query.where(kw_filter)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size
        result = await self.db.execute(
            base_query.order_by(AccessApplication.created_at.asc()).offset(offset).limit(page_size)
        )
        apps: List[AccessApplication] = list(result.scalars().all())
        items = []
        for app in apps:
            status_text = {0: "待审核", 1: "已通过", 2: "已拒绝"}.get(app.status, "未知")
            reviewer_name = app.reviewer.real_name if app.reviewer else ""
            import os as _os2
            doc_name = app.document.name if app.document else ""
            _, file_ext2 = _os2.path.splitext(doc_name.lower()) if doc_name else ("", "")
            file_format2 = file_ext2.lstrip(".").upper() if file_ext2 else "-"
            items.append({
                "id": app.id, "applicant_id": app.applicant_id, "applicant_name": app.applicant.real_name if app.applicant else "",
                "document_id": app.document_id, "document_name": doc_name, "format": file_format2, "reason": app.reason,
                "status": app.status, "assigned_reviewer_ids": app.assigned_reviewer_ids,
                "expected_hours": app.expected_hours,
                "reviewer_id": app.reviewer_id, "reviewer_name": reviewer_name,
                "created_at": app.created_at, "review_time": app.review_time,
            })
        return {"total": total, "items": items}

    async def approve_application(self, application_id: int, reviewer_id: int, permission_type: str = "download", expires_in_hours: Optional[int] = None) -> dict:
        result = await self.db.execute(select(AccessApplication).where(AccessApplication.id == application_id))
        application = result.scalar_one_or_none()
        if not application: raise ResourceNotFoundError(detail="申请不存在")
        if application.status != 0: raise BusinessError(detail="申请状态不允许审核")
        if permission_type not in ("view_only", "download"): raise BusinessError(detail="无效的授权类型，支持: view_only / download")

        doc_result = await self.db.execute(
            select(Document).where(Document.id == application.document_id)
        )
        document = doc_result.scalar_one_or_none()
        if not document: raise ResourceNotFoundError(detail="关联文档不存在")
        await self._check_reviewer_access(reviewer_id, document.department_id)

        application.status = 1
        application.reviewer_id = reviewer_id
        application.review_time = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(48)
        # 永久授权：expires_in_hours=0 → expires_at=None；None → 系统默认；>0 → 指定时长
        if expires_in_hours == 0:
            expires_at = None
            hours = 0
        else:
            hours = expires_in_hours if expires_in_hours is not None else await get_config_int(self.db, "temp_token_expire_hours", settings.TEMP_TOKEN_EXPIRE_HOURS)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
        temp_token = TempAccessToken(token=token, user_id=application.applicant_id, document_id=application.document_id, permission_type=permission_type, expires_at=expires_at)
        self.db.add(temp_token)
        if permission_type == "download":
            from app.models.user_document_permission import UserDocumentPermission
            existing_perm = await self.db.execute(
                select(UserDocumentPermission).where(UserDocumentPermission.user_id == application.applicant_id, UserDocumentPermission.document_id == application.document_id)
            )
            if not existing_perm.scalar_one_or_none():
                perm = UserDocumentPermission(user_id=application.applicant_id, document_id=application.document_id, granted_by=reviewer_id, permission_type="download", expires_at=expires_at)
                self.db.add(perm)
        await self.audit_svc.create_audit_log(
            user_id=reviewer_id, operation_type="REVIEW",
            operation_content={"action": "approve_application", "application_id": application_id, "document_id": application.document_id, "permission_type": permission_type, "expires_in_hours": hours, "permanent": expires_in_hours == 0},
        )
        await self.db.commit()
        return {"message": "申请已通过", "token": token, "expires_at": expires_at.isoformat() if expires_at else None, "permission_type": permission_type}

    async def reject_application(self, application_id: int, reviewer_id: int) -> dict:
        result = await self.db.execute(select(AccessApplication).where(AccessApplication.id == application_id))
        application = result.scalar_one_or_none()
        if not application: raise ResourceNotFoundError(detail="申请不存在")
        if application.status != 0: raise BusinessError(detail="申请状态不允许审核")

        doc_result = await self.db.execute(
            select(Document).where(Document.id == application.document_id)
        )
        document = doc_result.scalar_one_or_none()
        if not document: raise ResourceNotFoundError(detail="关联文档不存在")
        await self._check_reviewer_access(reviewer_id, document.department_id)

        application.status = 2
        application.reviewer_id = reviewer_id
        application.review_time = datetime.now(timezone.utc)
        cooldown_days = await get_config_int(self.db, "application_cooldown_days", settings.APPLICATION_COOLDOWN_DAYS)
        cooldown_date = datetime.now(timezone.utc) - timedelta(days=cooldown_days)
        previous_rejection = await self.db.execute(
            select(AccessApplication).where(
                AccessApplication.applicant_id == application.applicant_id,
                AccessApplication.document_id == application.document_id,
                AccessApplication.status == 2,
                AccessApplication.id != application_id,
                AccessApplication.created_at >= cooldown_date,
            )
        )
        cooldown_warning = None
        if previous_rejection.scalar_one_or_none():
            cooldown_warning = f"注意：该申请人对本文档在{cooldown_days}天内已有被拒绝记录，仍需等待冷却期满后方可重新申请"
        await self.audit_svc.create_audit_log(
            user_id=reviewer_id, operation_type="REVIEW",
            operation_content={"action": "reject_application", "application_id": application_id, "document_id": application.document_id, "cooldown_warning": cooldown_warning},
        )
        await self.db.commit()
        result_msg = {"message": "申请已拒绝"}
        if cooldown_warning: result_msg["cooldown_warning"] = cooldown_warning
        return result_msg

    async def get_review_history(self, current_user: User, page: int, page_size: int, department_id: int = None, keyword: str = None) -> dict:
        """获取审核历史记录，按角色和部门过滤：
        - 普通管理员/审核员：只看本部门的审核记录
        - 超级管理员：支持按部门筛选（传 department_id 则筛选该部门，不传则全部）
        """
        from app.core.permissions import is_super_admin as check_is_super
        user_role_code = current_user.role.role_code if current_user.role else ""
        user_dept_id = current_user.department_id
        offset = (page - 1) * page_size

        dept_filter_active = False
        filter_dept_id: Optional[int] = None
        params = {"limit": page_size, "offset": offset}

        if check_is_super(user_role_code):
            if department_id is not None:
                dept_filter_active = True
                filter_dept_id = department_id
        elif user_role_code in ("ADMIN", "REVIEWER"):
            if user_dept_id is not None:
                dept_filter_active = True
                filter_dept_id = user_dept_id
            else:
                return {"total": 0, "items": []}

        if dept_filter_active:
            params["dept_id"] = filter_dept_id
            dept_filter = " AND department_id = :dept_id"
        else:
            dept_filter = ""

        # 关键词过滤：按文档/申请目标名称模糊匹配
        kw_filter = ""
        if keyword:
            params["kw"] = f"%{keyword}%"
            kw_filter = " AND target_name ILIKE :kw"

        union_sql = text(f"""SELECT * FROM (
            SELECT id, 'document' AS type, name AS target_name, reviewer_id,
                   CASE WHEN status = 1 THEN 'approved' ELSE 'rejected' END AS action, review_time,
                   department_id
            FROM documents WHERE review_time IS NOT NULL{dept_filter}
            UNION ALL
            SELECT a.id, 'application' AS type, COALESCE(d.name, '') AS target_name, a.reviewer_id,
                   CASE WHEN a.status = 1 THEN 'approved' ELSE 'rejected' END AS action, a.review_time,
                   d.department_id
            FROM access_applications a LEFT JOIN documents d ON a.document_id = d.id
            WHERE a.review_time IS NOT NULL{dept_filter}
        ) combined WHERE 1=1{kw_filter} ORDER BY review_time DESC LIMIT :limit OFFSET :offset""")
        count_sql = text(f"""SELECT COUNT(*) FROM (
            SELECT id, name AS target_name FROM documents WHERE review_time IS NOT NULL{dept_filter}
            UNION ALL
            SELECT a.id, COALESCE(d.name, '') AS target_name FROM access_applications a LEFT JOIN documents d ON a.document_id = d.id
            WHERE a.review_time IS NOT NULL{dept_filter}
        ) combined WHERE 1=1{kw_filter}""")
        total_result = await self.db.execute(count_sql, params)
        total = total_result.scalar() or 0
        result = await self.db.execute(union_sql, params)
        rows = result.all()
        items = [{"id": row.id, "type": row.type, "target_name": row.target_name or "", "action": row.action, "reviewer_name": "", "review_time": row.review_time} for row in rows]
        return {"total": total, "items": items}
