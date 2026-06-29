import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select, func, or_, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ResourceNotFoundError, PermissionDeniedError, BusinessError
from app.core.permissions import (
    is_privileged_role, is_super_admin, resolve_document_access,
)
from app.core.config_service import get_config_int, get_config_float
from app.core.constants import (
    ALLOWED_EXTENSIONS as ALLOWED_EXTENSIONS_MAP,
    get_allowed_max_size,
    get_mime_type,
)
from app.models.user import User
from app.models.role import Role
from app.models.document import (
    Document, ACCESS_MODE_DEPARTMENT_PUBLIC, ACCESS_MODE_APPLY_REQUIRED
)
from app.models.data_tag import DataTag
from app.models.access_application import AccessApplication
from app.models.temp_token import TempAccessToken
from app.models.user_favorite import UserFavorite
from app.models.user_document_permission import UserDocumentPermission
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = set(ALLOWED_EXTENSIONS_MAP.keys())
CAD_EXTENSIONS = {".dwg", ".dxf"}

STATUS_TEXT_MAP = {0: "待审核", 1: "已通过", 2: "已拒绝"}
ACCESS_MODE_TEXT_MAP = {
    ACCESS_MODE_DEPARTMENT_PUBLIC: "部门内公开",
    ACCESS_MODE_APPLY_REQUIRED: "需申请访问",
}


class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_svc = AuditService(db)

    async def upload_document(
        self, user: User, file: UploadFile, tag_ids: list[int],
        upload_type: str = "regular",
        reviewer_id: Optional[int] = None,
    ) -> dict:
        _, ext = os.path.splitext(file.filename or "document")
        ext = ext.lower()
        is_cad = ext in CAD_EXTENSIONS
        all_allowed = ALLOWED_EXTENSIONS | CAD_EXTENSIONS
        if ext not in all_allowed:
            raise BusinessError(detail=f"不支持的文件类型: {ext}，支持: {', '.join(sorted(all_allowed))}")

        content = await file.read()
        max_size = get_allowed_max_size(file.filename or "")
        max_size_mb = int(max_size / (1024 * 1024))
        if len(content) > max_size:
            raise BusinessError(detail=f"文件大小超过限制 (最大 {max_size_mb}MB)")

        # 文档去重检测：在事务开始前执行，避免 rollback 清空后续 flush 的 document.id
        # 仅做只读查询，不修改数据库状态，无需事务保护
        dedup_threshold = settings.DEDUP_SIMILARITY_THRESHOLD
        try:
            from app.services.vector_service import VectorService
            try:
                dedup_threshold = await get_config_float(self.db, "dedup_similarity_threshold", settings.DEDUP_SIMILARITY_THRESHOLD)
            except Exception:
                pass  # 配置读取失败使用默认值，不影响主流程

            is_dup, dup_doc_name, dup_score = await asyncio.wait_for(
                VectorService.check_duplicate(content, file.filename or "", threshold=dedup_threshold),
                timeout=30.0,
            )
            if is_dup:
                raise BusinessError(
                    detail=f"文件内容与知识库中已有文档「{dup_doc_name}」高度相似（相似度 {dup_score * 100:.1f}%，阈值{dedup_threshold * 100:.0f}%），请勿重复上传。"
                )
        except (asyncio.TimeoutError, TimeoutError):
            logger.warning("文档去重检测超时（30s），跳过重复检查继续上传")
        except BusinessError:
            raise
        except Exception as e:
            logger.warning(f"文档去重检测失败（非致命），跳过重复检查继续上传: {e}")

        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        filename = f"{uuid.uuid4()}_{file.filename}"
        saved_path = os.path.join(settings.UPLOAD_DIR, filename)
        with open(saved_path, "wb") as f:
            f.write(content)

        is_privileged = (user.role and is_privileged_role(user.role.role_code))
        # 仅超级管理员上传的文档标记为全员可见（跨部门公开）；
        # ADMIN/REVIEWER 上传的文档仍按部门归属控制可见性
        user_is_super_admin = (user.role and is_super_admin(user.role.role_code))

        # 确定审核员：优先使用用户指定的 reviewer_id
        assigned_reviewer_id = reviewer_id
        
        # 如果没有指定审核员
        if assigned_reviewer_id is None:
            if user_is_super_admin:
                # 超级管理员上传：自动通过，无需审核员，reviewer_id 置空避免"自审"语义混乱
                assigned_reviewer_id = None
            elif is_privileged:
                # 部门管理员/审核员上传：自己审核
                assigned_reviewer_id = user.id
            elif user.department_id is not None:
                # 普通员工上传：自动查找同部门的审核员/管理员
                from app.models.role import Role as _DocReviewRole
                from app.models.user import User as _DocReviewUser
                reviewer_result = await self.db.execute(
                    select(_DocReviewUser).join(_DocReviewRole).where(
                        _DocReviewRole.role_code.in_(["ADMIN", "REVIEWER"]),
                        _DocReviewUser.status == 1,
                        _DocReviewUser.department_id == user.department_id,
                    )
                )
                dept_reviewers = list(reviewer_result.scalars().all())
                if dept_reviewers:
                    # 优先分配 ADMIN，其次 REVIEWER
                    admin_first = sorted(
                        dept_reviewers,
                        key=lambda u: 0 if (u.role and u.role.role_code == "ADMIN") else 1
                    )
                    assigned_reviewer_id = admin_first[0].id

        # 确定文档归属部门：
        # - 超级管理员上传 → 归属"公司总部"（HEADQUARTERS）部门
        # - 其他用户上传   → 归属上传者所在部门
        if user_is_super_admin:
            from app.models.department import Department as _HQDept
            hq_result = await self.db.execute(
                select(_HQDept.id).where(_HQDept.code == "HEADQUARTERS")
            )
            doc_department_id = hq_result.scalar_one_or_none() or user.department_id
        else:
            doc_department_id = user.department_id

        # 验证标签ID有效性，查询标签对象
        tags = []
        if tag_ids:
            unique_tag_ids = list(set(tag_ids))
            tags_result = await self.db.execute(
                select(DataTag).where(DataTag.id.in_(unique_tag_ids))
            )
            tags = list(tags_result.scalars().all())
            if len(tags) != len(unique_tag_ids):
                valid_ids = {t.id for t in tags}
                invalid_ids = [tid for tid in unique_tag_ids if tid not in valid_ids]
                raise BusinessError(detail=f"无效的标签ID: {invalid_ids}")

        # 从上传者获取部门信息
        document = Document(
            name=file.filename or "未命名文档",
            uploader_id=user.id,
            department_id=doc_department_id,
            file_path=saved_path,
            file_size=len(content),
            upload_type=upload_type,
            access_mode=ACCESS_MODE_DEPARTMENT_PUBLIC,
            is_public_to_all=1 if user_is_super_admin else 0,
            status=1 if is_privileged else 0,
            reviewer_id=assigned_reviewer_id,
            review_time=datetime.now(timezone.utc) if is_privileged else None,
            tags=tags,
        )
        self.db.add(document)
        await self.db.flush()

        # 构建标签信息传给解析任务
        tags_for_worker = []
        for t in tags:
            cat = t.category
            tags_for_worker.append({
                "id": t.id,
                "name": t.name,
                "category_id": t.category_id,
                "category_name": cat.name if cat else "",
                "category_code": cat.code if cat else "",
                "color": cat.color if cat else "primary",
            })

        try:
            import redis.asyncio as aioredis
            redis_client = aioredis.from_url(settings.REDIS_URL)
            task_data = json.dumps({
                "document_id": document.id,
                "file_path": saved_path,
                "file_type": ext,
                "tags": tags_for_worker,
                "department_id": document.department_id,
            })
            await redis_client.lpush("doc_parse_queue", task_data)
            await redis_client.close()
        except Exception as e:
            logger.warning(f"Redis 任务投递失败（非致命）: {e}")

        await self.audit_svc.create_audit_log(
            user_id=user.id,
            operation_type="UPLOAD",
            operation_content={
                "document_id": document.id,
                "filename": file.filename,
                "file_size": len(content),
                "tag_ids": tag_ids,
                "tags": tags_for_worker,
                "department_id": user.department_id,
            },
        )

        await self.db.commit()
        await self.db.refresh(document)

        return {
            "document_id": document.id,
            "name": document.name,
            "status": document.status,
            "message": "上传成功" if is_privileged else "文档上传成功，等待审核",
        }

    async def get_document_list(
        self, user: User, page: int, page_size: int, keyword: Optional[str] = None,
        department_id: Optional[int] = None,
        tag_ids: Optional[list[int]] = None,
    ) -> dict:
        """
        获取文档列表（新模型：基于部门归属）
        - 超级管理员：可查看所有部门文档，支持 department_id / tag_ids 过滤
        - 其他角色：只显示所在部门的文档
        """
        user_role_code = user.role.role_code if user.role else ""
        user_dept_id = user.department_id

        base_query = select(Document)
        count_query = select(func.count(Document.id))

        base_query = base_query.where(Document.status == 1)
        count_query = count_query.where(Document.status == 1)

        # 标签过滤
        if tag_ids and len(tag_ids) > 0:
            from app.models.data_tag import document_tags
            unique_tag_ids = list(set(tag_ids))
            tag_filter = Document.id.in_(
                select(document_tags.c.document_id)
                .where(document_tags.c.tag_id.in_(unique_tag_ids))
                .group_by(document_tags.c.document_id)
                .having(func.count(func.distinct(document_tags.c.tag_id)) == len(unique_tag_ids))
            )
            base_query = base_query.where(tag_filter)
            count_query = count_query.where(tag_filter)

        # 部门过滤
        if is_super_admin(user_role_code):
            # 超级管理员：如果传了 department_id，按部门过滤；否则显示全部
            if department_id is not None:
                base_query = base_query.where(Document.department_id == department_id)
                count_query = count_query.where(Document.department_id == department_id)
        else:
            # 其他角色可见的文档（最小权限原则，避免跨部门受限文档元信息泄露）：
            #   1. 自己所在部门的文档（部门内按 access_mode 控制访问，apply_required 可在本部门内申请）
            #   2. 自己上传的文档
            #   3. 全员可见文档（is_public_to_all=1，即超级管理员上传的文档）
            #   4. 已被显式授权的文档（通过 user_document_permissions 表）
            #   5. 已提交过访问申请的文档（避免重复申请，同时让用户能跟踪申请状态）
            authorized_doc_ids_subq = select(UserDocumentPermission.document_id).where(
                UserDocumentPermission.user_id == user.id
            )
            applied_doc_ids_subq = select(AccessApplication.document_id).where(
                AccessApplication.applicant_id == user.id
            )

            if user_dept_id is not None:
                dept_filter = or_(
                    Document.department_id == user_dept_id,
                    Document.uploader_id == user.id,
                    Document.is_public_to_all == 1,
                    Document.id.in_(authorized_doc_ids_subq),
                    Document.id.in_(applied_doc_ids_subq),
                )
                base_query = base_query.where(dept_filter)
                count_query = count_query.where(dept_filter)
            else:
                # 用户没有部门：自己上传的 + 全员可见 + 已授权 + 已申请的文档
                no_dept_filter = or_(
                    Document.uploader_id == user.id,
                    Document.is_public_to_all == 1,
                    Document.id.in_(authorized_doc_ids_subq),
                    Document.id.in_(applied_doc_ids_subq),
                )
                base_query = base_query.where(no_dept_filter)
                count_query = count_query.where(no_dept_filter)

        if keyword:
            pattern = f"%{keyword}%"
            base_query = base_query.where(Document.name.ilike(pattern))
            count_query = count_query.where(Document.name.ilike(pattern))

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        docs_result = await self.db.execute(
            base_query.order_by(Document.created_at.desc()).offset(offset).limit(page_size)
        )
        docs = list(docs_result.scalars().all())

        # 批量查询当前用户待审核申请的文档ID集合，避免 N+1 查询
        pending_doc_ids = set()
        if docs:
            doc_id_list = [d.id for d in docs]
            pending_result = await self.db.execute(
                select(AccessApplication.document_id).where(
                    AccessApplication.applicant_id == user.id,
                    AccessApplication.status == 0,
                    AccessApplication.document_id.in_(doc_id_list),
                )
            )
            pending_doc_ids = set(pending_result.scalars().all())

        items = []
        for doc in docs:
            doc_is_public_to_all = bool(getattr(doc, "is_public_to_all", 0)) == 1
            # 调用新的 resolve_document_access（带部门信息和全员可见信息）
            perm = await resolve_document_access(
                self.db,
                user.id,
                user_role_code,
                user_dept_id,
                doc.uploader_id == user.id,
                doc.department_id,
                doc.access_mode,
                doc.id,
                is_public_to_all=doc_is_public_to_all,
            )
            doc_access = perm["access_type"]
            can_download = perm["can_download"]
            can_view = perm["can_view"]
            permission_expires_at = perm.get("permission_expires_at")

            if is_super_admin(user_role_code):
                source_type = "PRIVILEGED"
            elif doc_is_public_to_all:
                source_type = "PUBLIC_TO_ALL"
            elif doc.uploader_id == user.id:
                source_type = "UPLOADER"
            elif is_privileged_role(user_role_code) and doc.department_id == user_dept_id:
                source_type = "DEPT_ADMIN"
            elif doc_access == "DIRECT":
                source_type = "AUTHORIZED"
            else:
                source_type = "APPLY_REQUIRED"

            _, file_ext = os.path.splitext(doc.name.lower()) if doc.name else ("", "")
            file_format = file_ext.lstrip(".").upper() if file_ext else "-"

            dept_name = doc.department.name if doc.department else "未分配"

            # 构建标签列表
            tags_data = []
            for t in doc.tags:
                cat = t.category
                tags_data.append({
                    "id": t.id,
                    "name": t.name,
                    "category_id": t.category_id,
                    "category_name": cat.name if cat else "",
                    "category_code": cat.code if cat else "",
                    "color": cat.color if cat else "primary",
                })

            items.append({
                "id": doc.id,
                "name": doc.name,
                "file_size": doc.file_size,
                "tags": tags_data,
                "department_id": doc.department_id,
                "department_name": dept_name,
                "access_mode": doc.access_mode,
                "access_mode_text": ACCESS_MODE_TEXT_MAP.get(doc.access_mode, "未知"),
                "format": file_format,
                "is_public_to_all": doc_is_public_to_all,
                "status": doc.status,
                "status_text": STATUS_TEXT_MAP.get(doc.status, "未知"),
                "uploader_name": (doc.uploader.real_name or doc.uploader.username) if doc.uploader else "",
                "created_at": doc.created_at,
                "access_type": doc_access,
                "source_type": source_type,
                "can_download": can_download,
                "can_view": can_view,
                "permission_expires_at": permission_expires_at,
                "has_pending_application": doc.id in pending_doc_ids,
                "is_parsed": getattr(doc, "is_parsed", 0),
                "chunk_count": getattr(doc, "chunk_count", 0),
            })

        return {"total": total, "items": items}

    async def get_departments_for_filter(self, user: User) -> list:
        """
        获取当前用户可用于过滤的部门列表：
        - 超级管理员：所有部门
        - 其他角色：只返回自己所在部门（或空列表）
        """
        from app.models.department import Department

        user_role_code = user.role.role_code if user.role else ""

        if is_super_admin(user_role_code):
            result = await self.db.execute(select(Department).order_by(Department.id))
            depts = list(result.scalars().all())
            return [{"id": d.id, "name": d.name, "code": d.code} for d in depts]

        # 其他角色：只返回自己所在部门
        if user.department_id:
            result = await self.db.execute(
                select(Department).where(Department.id == user.department_id)
            )
            dept = result.scalar_one_or_none()
            if dept:
                return [{"id": dept.id, "name": dept.name, "code": dept.code}]

        return []

    async def set_document_access_mode(
        self, user: User, document_id: int, access_mode: str
    ) -> dict:
        """
        设置文档的访问模式（仅同部门的管理员/审核员或超级管理员可操作）。
        access_mode: "department_public" | "apply_required"
        """
        from app.core.permissions import is_super_admin as check_is_super

        document = await self._get_document(document_id)

        user_role_code = user.role.role_code if user.role else ""
        user_dept_id = user.department_id

        # 权限检查：超级管理员 或 同部门的管理员/审核员
        can_set = False
        if check_is_super(user_role_code):
            can_set = True
        elif (
            is_privileged_role(user_role_code)
            and user_dept_id is not None
            and document.department_id == user_dept_id
        ):
            can_set = True

        if not can_set:
            raise PermissionDeniedError(detail="无权限设置此文档的访问模式（需部门管理员/审核员或超级管理员）")

        # 验证 access_mode 值
        valid_modes = {ACCESS_MODE_DEPARTMENT_PUBLIC, ACCESS_MODE_APPLY_REQUIRED}
        if access_mode not in valid_modes:
            raise BusinessError(detail=f"无效的访问模式，支持: {', '.join(valid_modes)}")

        old_mode = document.access_mode
        old_is_public = document.is_public_to_all
        document.access_mode = access_mode

        # 设置为需申请访问时，自动取消全员可见标记，确保 access_mode 生效
        if access_mode == ACCESS_MODE_APPLY_REQUIRED:
            document.is_public_to_all = 0
        elif access_mode == ACCESS_MODE_DEPARTMENT_PUBLIC:
            # 恢复全员可见：仅当上传者是超级管理员时（超管上传的文档本应全员可见）
            # 这样可修复之前被误改为 apply_required 而丢失全员可见标记的文档
            uploader_result = await self.db.execute(
                select(User).join(Role, User.role_id == Role.id).where(User.id == document.uploader_id)
            )
            uploader = uploader_result.scalar_one_or_none()
            if uploader and is_super_admin(uploader.role.role_code if uploader.role else ""):
                document.is_public_to_all = 1

        await self.audit_svc.create_audit_log(
            user_id=user.id,
            operation_type="UPDATE_ACCESS_MODE",
            operation_content={
                "document_id": document_id,
                "document_name": document.name,
                "old_mode": old_mode,
                "new_mode": access_mode,
                "old_is_public_to_all": old_is_public,
                "new_is_public_to_all": document.is_public_to_all,
            },
        )

        await self.db.commit()
        await self.db.refresh(document)

        return {
            "document_id": document_id,
            "name": document.name,
            "access_mode": document.access_mode,
            "access_mode_text": ACCESS_MODE_TEXT_MAP.get(document.access_mode, "未知"),
            "message": "访问模式已更新",
        }

    async def apply_document_access(self, user: User, document_id: int, reason: str, reviewer_ids: list = None, expected_hours: int = 24) -> dict:
        """申请文档访问权限：权限检查 → 冷却期检查 → 待审检查 → 创建申请（支持指定审核员）"""
        document = await self._get_document(document_id)
        doc_is_public_to_all = bool(getattr(document, "is_public_to_all", 0)) == 1

        user_role_code = user.role.role_code if user.role else ""
        user_dept_id = user.department_id

        # 先检查是否已有访问权限（不需要申请）
        perm = await resolve_document_access(
            self.db, user.id, user_role_code, user_dept_id,
            document.uploader_id == user.id,
            document.department_id, document.access_mode, document.id,
            is_public_to_all=doc_is_public_to_all,
        )
        if perm["can_download"]:
            raise BusinessError(detail="您已有该文档的完整访问权限，无需申请")

        # 确定审核员：优先使用用户指定的 reviewer_ids
        from app.models.role import Role
        valid_reviewer_ids = []
        
        if reviewer_ids and isinstance(reviewer_ids, list) and len(reviewer_ids) > 0:
            # 用户指定了审核员，验证这些审核员是否有效
            reviewer_result = await self.db.execute(
                select(User).join(Role).where(
                    Role.role_code.in_(["ADMIN", "REVIEWER"]),
                    User.status == 1,
                    User.id.in_(reviewer_ids),
                )
            )
            valid_reviewer_ids = [r.id for r in reviewer_result.scalars().all()]
            if not valid_reviewer_ids:
                raise BusinessError(detail="指定的审核员无效")
        else:
            # 自动查找文档所属部门的管理员和审核员
            # 确定审核范围：优先使用文档所属部门，没有则使用申请人部门
            review_dept_id = document.department_id or user_dept_id

            # 查询该部门下的所有 ADMIN 和 REVIEWER 角色用户
            reviewer_result = await self.db.execute(
                select(User).join(Role).where(
                    Role.role_code.in_(["ADMIN", "REVIEWER"]),
                    User.status == 1,
                    User.department_id == review_dept_id,
                )
            )
            dept_reviewers = list(reviewer_result.scalars().all())

            # 如果文档部门没有审核员，查询申请人部门的
            if not dept_reviewers and user_dept_id and user_dept_id != review_dept_id:
                reviewer_result2 = await self.db.execute(
                    select(User).join(Role).where(
                        Role.role_code.in_(["ADMIN", "REVIEWER"]),
                        User.status == 1,
                        User.department_id == user_dept_id,
                    )
                )
                dept_reviewers = list(reviewer_result2.scalars().all())

            valid_reviewer_ids = [r.id for r in dept_reviewers]

        if not valid_reviewer_ids:
            raise BusinessError(detail="您所在部门暂未设置管理员或审核员，请联系超级管理员处理")

        cooldown_days = await get_config_int(self.db, "application_cooldown_days", settings.APPLICATION_COOLDOWN_DAYS)
        cooldown_date = datetime.now(timezone.utc) - timedelta(days=cooldown_days)
        recent_rejection = await self.db.execute(
            select(AccessApplication).where(
                AccessApplication.applicant_id == user.id,
                AccessApplication.document_id == document_id,
                AccessApplication.status == 2,
                AccessApplication.created_at >= cooldown_date,
            )
        )
        if recent_rejection.scalar_one_or_none():
            raise BusinessError(detail=f"申请冷却中，请{cooldown_days}天后重试")

        existing_pending = await self.db.execute(
            select(AccessApplication).where(
                AccessApplication.applicant_id == user.id,
                AccessApplication.document_id == document_id,
                AccessApplication.status == 0,
            )
        )
        if existing_pending.scalar_one_or_none():
            raise BusinessError(detail="您已有该文档的待审核申请，请勿重复提交")

        application = AccessApplication(
            applicant_id=user.id,
            document_id=document_id,
            reason=reason,
            status=0,
            assigned_reviewer_ids=valid_reviewer_ids if valid_reviewer_ids else None,
            expected_hours=expected_hours,
        )
        self.db.add(application)

        await self.audit_svc.create_audit_log(
            user_id=user.id,
            operation_type="APPLY_ACCESS",
            operation_content={
                "document_id": document_id,
                "document_name": document.name,
                "reason": reason,
                "assigned_reviewer_ids": valid_reviewer_ids if valid_reviewer_ids else [],
            },
        )

        await self.db.commit()
        await self.db.refresh(application)
        return {"message": "申请已提交", "application_id": application.id, "assigned_reviewer_ids": valid_reviewer_ids}

    async def download_document(self, user: User, document_id: int) -> FileResponse:
        document = await self._get_document(document_id)
        doc_is_public_to_all = bool(getattr(document, "is_public_to_all", 0)) == 1

        user_role_code = user.role.role_code if user.role else ""
        user_dept_id = user.department_id

        perm = await resolve_document_access(
            self.db, user.id, user_role_code, user_dept_id,
            document.uploader_id == user.id,
            document.department_id, document.access_mode, document.id,
            is_public_to_all=doc_is_public_to_all,
        )
        can_download = perm["can_download"]

        if not can_download:
            raise PermissionDeniedError(
                detail="无权下载此文档，请先申请访问权限后再下载",
                extra={"document_id": document_id, "action": "apply", "document_name": document.name},
            )

        if not os.path.exists(document.file_path):
            raise ResourceNotFoundError(detail="文档文件不存在")

        await self.audit_svc.create_audit_log(
            user_id=user.id,
            operation_type="DOWNLOAD",
            operation_content={
                "document_id": document_id,
                "document_name": document.name,
            },
        )
        await self.db.commit()

        media_type = get_mime_type(document.name)
        return FileResponse(
            document.file_path, filename=document.name, media_type=media_type,
            content_disposition_type="attachment",
        )

    async def view_document(self, user: User, document_id: int) -> FileResponse:
        """在线查看文档（PDF加水印）"""
        document = await self._get_document(document_id)
        doc_is_public_to_all = bool(getattr(document, "is_public_to_all", 0)) == 1

        user_role_code = user.role.role_code if user.role else ""
        user_dept_id = user.department_id

        perm = await resolve_document_access(
            self.db, user.id, user_role_code, user_dept_id,
            document.uploader_id == user.id,
            document.department_id, document.access_mode, document.id,
            is_public_to_all=doc_is_public_to_all,
        )
        can_view = perm["can_view"]

        if not can_view:
            raise PermissionDeniedError(
                detail="无权查看此文档，请先申请访问权限",
                extra={"document_id": document_id, "action": "apply", "document_name": document.name},
            )

        if not os.path.exists(document.file_path):
            raise ResourceNotFoundError(detail="文档文件不存在")

        await self.audit_svc.create_audit_log(
            user_id=user.id,
            operation_type="VIEW",
            operation_content={
                "document_id": document_id,
                "document_name": document.name,
            },
        )
        await self.db.commit()

        media_type = get_mime_type(document.name)
        return FileResponse(
            document.file_path, filename=document.name, media_type=media_type,
            content_disposition_type="inline",
        )

    async def download_by_token(self, token: str) -> FileResponse:
        result = await self.db.execute(
            select(TempAccessToken).where(TempAccessToken.token == token)
        )
        token_record = result.scalar_one_or_none()
        if not token_record:
            raise ResourceNotFoundError(detail="令牌无效")
        # 永久令牌 expires_at 为 None，不做过期检查；否则统一 aware 比较
        if token_record.expires_at is not None and datetime.now(timezone.utc) > token_record.expires_at:
            raise PermissionDeniedError(detail="令牌已过期")
        if token_record.permission_type == "view_only":
            raise PermissionDeniedError(
                detail="此令牌仅限查看，不可下载",
                extra={"document_id": token_record.document_id, "action": "apply", "document_name": ""},
            )

        document = await self._get_document(token_record.document_id)
        token_record.used_at = datetime.now(timezone.utc)

        if not os.path.exists(document.file_path):
            raise ResourceNotFoundError(detail="文档文件不存在")

        await self.audit_svc.create_audit_log(
            user_id=token_record.user_id,
            operation_type="DOWNLOAD_BY_TOKEN",
            operation_content={
                "document_id": token_record.document_id,
                "document_name": document.name,
                "token": token,
            },
        )
        await self.db.commit()

        media_type = get_mime_type(document.name)
        return FileResponse(
            document.file_path, filename=document.name, media_type=media_type,
            content_disposition_type="attachment",
        )

    async def _get_document(self, document_id: int) -> Document:
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        if not document:
            raise ResourceNotFoundError(detail="文档不存在")
        return document

    async def update_document_tags(
        self, user: User, document_id: int, tag_ids: list[int]
    ) -> dict:
        from app.core.permissions import is_super_admin as check_is_super

        user_role_code = user.role.role_code if user.role else ""
        user_dept_id = user.department_id

        document = await self._get_document(document_id)

        # 权限检查：超级管理员 或 同部门的管理员/审核员
        can_update = False
        if check_is_super(user_role_code):
            can_update = True
        elif (
            is_privileged_role(user_role_code)
            and user_dept_id is not None
            and document.department_id == user_dept_id
        ):
            can_update = True

        if not can_update:
            raise PermissionDeniedError(detail="无权限编辑此文档的标签（需部门管理员/审核员或超级管理员）")

        # 验证标签ID有效性
        tags = []
        if tag_ids:
            unique_tag_ids = list(set(tag_ids))
            tags_result = await self.db.execute(
                select(DataTag).where(DataTag.id.in_(unique_tag_ids))
            )
            tags = list(tags_result.scalars().all())
            if len(tags) != len(unique_tag_ids):
                valid_ids = {t.id for t in tags}
                invalid_ids = [tid for tid in unique_tag_ids if tid not in valid_ids]
                raise BusinessError(detail=f"无效的标签ID: {invalid_ids}")

        old_tags_info = [{"id": t.id, "name": t.name, "category_id": t.category_id} for t in document.tags]
        document.tags = tags

        new_tags_info = [{"id": t.id, "name": t.name, "category_id": t.category_id} for t in tags]

        await self.audit_svc.create_audit_log(
            user_id=user.id,
            operation_type="UPDATE_DOCUMENT_TAGS",
            operation_content={
                "document_id": document_id,
                "document_name": document.name,
                "old_tag_ids": [t["id"] for t in old_tags_info],
                "new_tag_ids": tag_ids,
                "old_tags": old_tags_info,
                "new_tags": new_tags_info,
            },
        )

        await self.db.commit()
        await self.db.refresh(document)

        # 更新向量索引中的标签
        try:
            await self._reindex_document_tags(document_id, tags)
        except Exception as e:
            logger.warning(f"向量索引更新失败（非致命）: {e}")

        return {
            "document_id": document_id,
            "name": document.name,
            "tags": new_tags_info,
            "message": "标签更新成功",
        }

    async def delete_document(self, user: User, document_id: int) -> dict:
        """删除文档（仅超级管理员或文档所属部门的管理员可操作）"""
        from app.core.permissions import is_super_admin as check_is_super

        document = await self._get_document(document_id)

        user_role_code = user.role.role_code if user.role else ""
        user_dept_id = user.department_id

        can_delete = False
        if check_is_super(user_role_code):
            can_delete = True
        elif (
            user_role_code == "ADMIN"
            and user_dept_id is not None
            and document.department_id == user_dept_id
        ):
            can_delete = True

        if not can_delete:
            raise PermissionDeniedError(detail="无权限删除此文档（需部门管理员或超级管理员）")

        # 删除本地文件
        try:
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
        except Exception as e:
            logger.warning(f"删除文档文件失败: {e}")

        await self.audit_svc.create_audit_log(
            user_id=user.id,
            operation_type="DELETE_DOCUMENT",
            operation_content={
                "document_id": document_id,
                "document_name": document.name,
                "department_id": document.department_id,
            },
        )

        # 清理引用该文档的关联记录，避免外键约束违反导致删除失败
        # （这些表未配置 ON DELETE CASCADE，必须显式删除）
        await self.db.execute(
            delete(UserFavorite).where(UserFavorite.document_id == document_id)
        )
        await self.db.execute(
            delete(UserDocumentPermission).where(UserDocumentPermission.document_id == document_id)
        )
        await self.db.execute(
            delete(AccessApplication).where(AccessApplication.document_id == document_id)
        )
        await self.db.execute(
            delete(TempAccessToken).where(TempAccessToken.document_id == document_id)
        )

        # 先清理 Qdrant 向量数据，再提交数据库删除，保证 DB 与向量库的一致性
        # 若 Qdrant 清理失败则抛出异常，触发数据库事务回滚，避免产生孤儿向量
        try:
            from app.services.vector_service import VectorService
            await VectorService.delete_vectors(document_id)
        except Exception as e:
            logger.error(f"Qdrant 向量清理失败，中止删除以保持数据一致性: {e}")
            raise RuntimeError(f"向量清理失败，文档未删除: {e}")

        await self.db.delete(document)
        await self.db.commit()

        return {"message": "文档已删除", "document_id": document_id}

    async def _reindex_document_tags(
        self, document_id: int, tags: list[DataTag]
    ) -> None:
        try:
            from app.services.vector_service import VectorService
            from app.models.document import DocumentChunk

            chunk_result = await self.db.execute(
                select(DocumentChunk.vector_id).where(DocumentChunk.document_id == document_id)
            )
            vector_ids = [row[0] for row in chunk_result.all()]
            if not vector_ids:
                logger.warning(f"文档 {document_id} 没有找到任何向量点，跳过索引更新")
                return

            # 构建按分类分组的标签字典，用于向量payload
            tags_by_category = {}
            for t in tags:
                cat = t.category
                if cat:
                    code = cat.code
                    if code not in tags_by_category:
                        tags_by_category[code] = []
                    tags_by_category[code].append(t.name)

            # 同时保留通用tags列表供过滤使用
            tag_names = [t.name for t in tags]

            await VectorService.update_document_payload(
                document_id=document_id,
                vector_ids=vector_ids,
                tags=tag_names,
                tags_by_category=tags_by_category,
            )

            logger.info(f"已更新文档 {document_id} 的向量索引标签，共 {len(vector_ids)} 个点，{len(tags)} 个标签")
        except Exception as e:
            logger.warning(f"向量索引更新失败（非致命）: {e}")
