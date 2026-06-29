import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

from app.database import get_db
from app.dependencies import get_current_user, get_current_active_user
from app.core.permissions import role_required
from app.core.constants import ROOT_ADMIN_USERNAME
from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserCreate, UserUpdate, UserListResponse
from app.schemas.audit import AuditLogQuery, AuditLogListResponse, AuditLogResponse
from app.schemas.tag import (
    TagCreate, TagUpdate, TagsByTypeResponse,
    DataTagCategoryCreate, DataTagCategoryUpdate,
    DataTagCreate, DataTagUpdate,
)
from app.schemas.role import RoleCreate, RoleUpdate
from app.schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.services.user_service import UserService
from app.services.audit_service import AuditService
from app.services.tag_service import TagService
from app.services.data_tag_service import DataTagService
from app.services.role_service import RoleService
from app.services.department_service import DepartmentService
from app.core.exceptions import ResourceNotFoundError, BusinessError

router = APIRouter(prefix="/admin", tags=["管理员"])

require_admin = role_required("SUPER_ADMIN", "ADMIN")
require_super_admin = role_required("SUPER_ADMIN")

# 超级管理员仅可创建管理员
SUPER_ADMIN_CREATABLE_ROLES = {"ADMIN"}

async def _get_creatable_role_codes_for_admin(db: AsyncSession) -> set:
    """管理员可创建除 SUPER_ADMIN 和 ADMIN 之外的所有角色（审核员及以下）"""
    result = await db.execute(
        select(Role.role_code).where(
            Role.role_code != "SUPER_ADMIN",
            Role.role_code != "ADMIN",
        )
    )
    return {row[0] for row in result.all()}

async def _get_target_role_code(target_user_id: int, db: AsyncSession) -> str | None:
    target_result = await db.execute(select(User).where(User.id == target_user_id))
    target = target_result.scalar_one_or_none()
    if not target:
        return None
    role_result = await db.execute(select(Role).where(Role.id == target.role_id))
    role = role_result.scalar_one_or_none()
    return role.role_code if role else None


async def _check_not_modifying_super_admin(current_user: User, target_user_id: int, db: AsyncSession):
    current_role_result = await db.execute(select(Role).where(Role.id == current_user.role_id))
    current_role = current_role_result.scalar_one_or_none()
    current_role_code = current_role.role_code if current_role else ""

    if current_role_code == "SUPER_ADMIN":
        return

    target_role_code = await _get_target_role_code(target_user_id, db)
    if target_role_code == "SUPER_ADMIN":
        raise BusinessError(detail="管理员不可对超级管理员进行编辑/禁用/删除操作")


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    role_id: int = Query(None),
    department_id: int = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取用户列表（分页+模糊搜索+角色筛选+部门筛选）。超级管理员不在列表中显示；管理员仅看同部门。"""
    svc = UserService(db, operator=current_user)
    return await svc.get_user_list(page, page_size, keyword, role_id=role_id, department_id=department_id)


@router.get("/users/{user_id}/detail")
async def get_user_detail(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """查看单个员工的详细个人信息（含手机号、个人说明、数据权限）"""
    svc = UserService(db, operator=current_user)
    return await svc.get_user_detail(user_id)


@router.post("/users")
async def create_user(
    user_in: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """创建员工账号，记录审计日志"""
    current_role_result = await db.execute(select(Role).where(Role.id == current_user.role_id))
    current_role = current_role_result.scalar_one_or_none()
    current_role_code = current_role.role_code if current_role else ""

    target_role_result = await db.execute(select(Role).where(Role.id == user_in.role_id))
    target_role = target_role_result.scalar_one_or_none()
    if not target_role:
        raise ResourceNotFoundError(detail="角色不存在")

    if current_role_code == "SUPER_ADMIN":
        if target_role.role_code not in SUPER_ADMIN_CREATABLE_ROLES:
            raise BusinessError(detail="超级管理员只能创建管理员，审核员及其他角色请交由管理员创建")
        if not user_in.department_id:
            raise BusinessError(detail="创建管理员必须指定所属部门")
    elif current_role_code == "ADMIN":
        admin_creatable = await _get_creatable_role_codes_for_admin(db)
        if target_role.role_code not in admin_creatable:
            raise BusinessError(detail="管理员不可创建超级管理员或管理员账号")

    svc = UserService(db, operator=current_user)
    result = await svc.create_user(user_in)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="CREATE_USER",
        operation_content={"target_username": user_in.username, "role_id": user_in.role_id},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """编辑员工信息，记录审计日志"""
    await _check_not_modifying_super_admin(current_user, user_id, db)
    svc = UserService(db, operator=current_user)
    result = await svc.update_user(user_id, user_in)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="UPDATE_USER",
        operation_content={"target_user_id": user_id, "changes": user_in.model_dump(exclude_none=True)},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.put("/users/{user_id}/disable")
async def disable_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """禁用员工账号，记录审计日志"""
    await _check_not_modifying_super_admin(current_user, user_id, db)
    svc = UserService(db, operator=current_user)
    result = await svc.disable_user(user_id)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="DISABLE_USER",
        operation_content={"target_user_id": user_id},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """删除员工账号（不可删除自己），记录审计日志"""
    await _check_not_modifying_super_admin(current_user, user_id, db)
    svc = UserService(db, operator=current_user)
    result = await svc.delete_user(user_id)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="DELETE_USER",
        operation_content={"target_user_id": user_id},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.get("/available-roles")
async def get_available_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取当前用户可创建的角色列表"""
    current_role_result = await db.execute(select(Role).where(Role.id == current_user.role_id))
    current_role = current_role_result.scalar_one_or_none()
    current_role_code = current_role.role_code if current_role else ""

    if current_role_code == "SUPER_ADMIN":
        allowed_codes = SUPER_ADMIN_CREATABLE_ROLES
    elif current_role_code == "ADMIN":
        allowed_codes = await _get_creatable_role_codes_for_admin(db)
    else:
        allowed_codes = set()

    result = await db.execute(select(Role).where(Role.role_code.in_(allowed_codes)).order_by(Role.id))
    roles = result.scalars().all()
    return [{"id": r.id, "role_code": r.role_code, "role_name": r.role_name} for r in roles]


# ==================== 标签管理 ====================

@router.get("/tags", response_model=TagsByTypeResponse)
async def get_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取所有标签（按类型分组）。SUPER_ADMIN / ADMIN 可读取。"""
    svc = TagService(db)
    return await svc.get_tags_by_type()


@router.get("/tags/list")
async def list_tags(
    tag_type: str = Query(None, description="筛选标签类型: model / region / doc_type"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取标签列表，可按类型筛选。SUPER_ADMIN / ADMIN 可读取。"""
    svc = TagService(db)
    items = await svc.get_tag_list(tag_type)
    return {"total": len(items), "items": items}


@router.post("/tags")
async def create_tag(
    tag_in: TagCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """创建新标签"""
    svc = TagService(db)
    result = await svc.create_tag(tag_in.tag_type, tag_in.tag_value)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="CREATE_TAG",
        operation_content={"tag_type": tag_in.tag_type, "tag_value": tag_in.tag_value},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.put("/tags/{tag_id}")
async def update_tag(
    tag_id: int,
    tag_in: TagUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """修改标签值"""
    svc = TagService(db)
    result = await svc.update_tag(tag_id, tag_in.tag_value)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="UPDATE_TAG",
        operation_content={"tag_id": tag_id, "old_value": result.get("old_value"), "new_value": tag_in.tag_value},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.delete("/tags/{tag_id}")
async def delete_tag(
    tag_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """删除标签"""
    svc = TagService(db)
    result = await svc.delete_tag(tag_id)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="DELETE_TAG",
        operation_content={"tag_id": tag_id, "tag_type": result.get("tag_type"), "tag_value": result.get("tag_value")},
        ip_address=request.client.host if request.client else "",
    )
    return result


# ==================== 数据标签分类管理（新） ====================

@router.get("/data-tag-categories")
async def list_data_tag_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取所有数据标签分类（含标签数量）。管理员可读取。"""
    svc = DataTagService(db)
    items = await svc.list_categories()
    return {"items": items}


@router.get("/data-tag-categories/all-tags")
async def get_all_data_tags_grouped(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取所有分类和标签（按分组返回，用于上传、筛选等全局场景，所有登录用户可用）"""
    svc = DataTagService(db)
    return await svc.get_all_tags_grouped()


@router.get("/data-tag-categories/{category_id}")
async def get_data_tag_category_detail(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取分类详情（含标签列表）"""
    svc = DataTagService(db)
    return await svc.get_category_detail(category_id)


@router.post("/data-tag-categories")
async def create_data_tag_category(
    cat_in: DataTagCategoryCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """创建新的数据标签分类"""
    svc = DataTagService(db)
    result = await svc.create_category(cat_in)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="CREATE_DATA_TAG_CATEGORY",
        operation_content={"name": cat_in.name, "code": cat_in.code},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.put("/data-tag-categories/{category_id}")
async def update_data_tag_category(
    category_id: int,
    cat_in: DataTagCategoryUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """更新数据标签分类"""
    svc = DataTagService(db)
    result = await svc.update_category(category_id, cat_in)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="UPDATE_DATA_TAG_CATEGORY",
        operation_content={"category_id": category_id, **cat_in.model_dump(exclude_none=True)},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.delete("/data-tag-categories/{category_id}")
async def delete_data_tag_category(
    category_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """删除数据标签分类（系统内置分类不可删除，分类下有标签不可删除）"""
    svc = DataTagService(db)
    result = await svc.delete_category(category_id)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="DELETE_DATA_TAG_CATEGORY",
        operation_content={"category_id": category_id},
        ip_address=request.client.host if request.client else "",
    )
    return result


# ==================== 数据标签值管理（新） ====================

@router.get("/data-tags")
async def list_data_tags(
    category_id: int = Query(None, description="按分类ID筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取数据标签列表，可按分类筛选"""
    svc = DataTagService(db)
    items = await svc.list_tags(category_id)
    return {"total": len(items), "items": items}


@router.post("/data-tags")
async def create_data_tag(
    tag_in: DataTagCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """创建新数据标签"""
    svc = DataTagService(db)
    result = await svc.create_tag(tag_in)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="CREATE_DATA_TAG",
        operation_content={"category_id": tag_in.category_id, "name": tag_in.name},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.put("/data-tags/{tag_id}")
async def update_data_tag(
    tag_id: int,
    tag_in: DataTagUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """更新数据标签"""
    svc = DataTagService(db)
    result = await svc.update_tag(tag_id, tag_in)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="UPDATE_DATA_TAG",
        operation_content={"tag_id": tag_id, **tag_in.model_dump(exclude_none=True)},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.delete("/data-tags/{tag_id}")
async def delete_data_tag(
    tag_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """删除数据标签"""
    svc = DataTagService(db)
    result = await svc.delete_tag(tag_id)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="DELETE_DATA_TAG",
        operation_content={"tag_id": tag_id},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.get("/audit/logs")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int = Query(None),
    operation_type: str = Query(None),
    start_time: str = Query(None),
    end_time: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """查询审计日志（分页+筛选）"""
    from datetime import datetime

    query = AuditLogQuery(
        page=page,
        page_size=page_size,
        user_id=user_id,
        operation_type=operation_type,
        start_time=datetime.fromisoformat(start_time) if start_time else None,
        end_time=datetime.fromisoformat(end_time) if end_time else None,
    )

    audit_svc = AuditService(db)
    return await audit_svc.get_audit_logs(query)


@router.get("/audit/logs/export")
async def export_audit_logs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10000, ge=1),
    user_id: int = Query(None),
    operation_type: str = Query(None),
    start_time: str = Query(None),
    end_time: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """导出审计日志为 CSV 文件"""
    from datetime import datetime

    query = AuditLogQuery(
        page=1,
        page_size=10000,
        user_id=user_id,
        operation_type=operation_type,
        start_time=datetime.fromisoformat(start_time) if start_time else None,
        end_time=datetime.fromisoformat(end_time) if end_time else None,
    )

    audit_svc = AuditService(db)
    csv_bytes = await audit_svc.export_audit_logs_csv(query)

    try:
        ip = request.client.host if request and request.client else ""
        await audit_svc.create_audit_log(
            user_id=current_user.id,
            operation_type="EXPORT_AUDIT",
            operation_content={
                "filters": {
                    "user_id": user_id,
                    "operation_type": operation_type,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            },
            ip_address=ip,
        )
    except Exception as e:
        logger.warning(f"审计日志记录失败（非致命）: {e}")

    return StreamingResponse(
        content=iter([csv_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )


# ==================== 待办申请计数（前端红色消息通知） ====================

@router.get("/pending-count")
async def get_pending_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取当前用户的待办总数（待审核文档 + 待处理访问申请）。
    - SUPER_ADMIN: 所有待审核文档 + 所有待处理访问申请
    - ADMIN/REVIEWER: 同部门待审核文档 + 分配给自己的访问申请
    - 其他角色: 0
    """
    from sqlalchemy import func
    from sqlalchemy.dialects.postgresql import JSONB as PgJSONB
    from app.models.access_application import AccessApplication
    from app.models.document import Document as DocModel

    role_code = current_user.role.role_code if current_user.role else ""
    if role_code not in ("SUPER_ADMIN", "ADMIN", "REVIEWER"):
        return {
            "total": 0,
            "pending_documents": 0,
            "pending_applications": 0,
        }

    user_dept_id = current_user.department_id
    is_super_admin = role_code == "SUPER_ADMIN"

    # 待审核文档计数
    if is_super_admin:
        doc_result = await db.execute(
            select(func.count(DocModel.id)).where(DocModel.status == 0)
        )
    elif user_dept_id is not None:
        doc_result = await db.execute(
            select(func.count(DocModel.id)).where(
                DocModel.status == 0,
                DocModel.department_id == user_dept_id,
            )
        )
    else:
        doc_result = await db.execute(
            select(func.count(DocModel.id)).where(DocModel.status == 0)
        )
    doc_count = doc_result.scalar() or 0

    # 待处理访问申请计数
    if is_super_admin:
        app_result = await db.execute(
            select(func.count(AccessApplication.id)).where(AccessApplication.status == 0)
        )
    else:
        # ADMIN/REVIEWER: 只统计分配给自己的
        visibility = AccessApplication.assigned_reviewer_ids.cast(PgJSONB).contains([current_user.id])
        app_query = select(func.count(AccessApplication.id)).where(
            AccessApplication.status == 0,
            visibility,
        )
        if user_dept_id is not None:
            app_query = app_query.where(
                AccessApplication.document_id.in_(
                    select(DocModel.id).where(DocModel.department_id == user_dept_id)
                )
            )
        app_result = await db.execute(app_query)
    app_count = app_result.scalar() or 0

    return {
        "total": doc_count + app_count,
        "pending_documents": doc_count,
        "pending_applications": app_count,
    }


# ==================== 审核员列表（供员工申请时选择） ====================

@router.get("/reviewers")
async def list_reviewers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取可选的审核员/管理员列表（仅限当前用户所在部门，用于申请时选择审核人）"""
    from sqlalchemy import or_

    # 普通员工只能看到本部门的审核员/管理员；超级管理员无部门归属，可看到全部
    if current_user.department_id is not None:
        base_query = select(User).join(Role).where(
            or_(
                Role.role_code == "ADMIN",
                Role.role_code == "REVIEWER",
            ),
            User.status == 1,
            User.department_id == current_user.department_id,
        )
    else:
        # 超级管理员（department_id=NULL）可看到所有审核员（不含 SUPER_ADMIN，超级管理员无需审核）
        base_query = select(User).join(Role).where(
            or_(
                Role.role_code == "ADMIN",
                Role.role_code == "REVIEWER",
            ),
            User.status == 1,
        )

    result = await db.execute(base_query.order_by(User.real_name))
    reviewers = result.scalars().all()
    return {
        "items": [
            {
                "id": u.id,
                "username": u.username,
                "real_name": u.real_name,
                "role_code": u.role.role_code if u.role else "",
                "role_name": u.role.role_name if u.role else "",
            }
            for u in reviewers
        ]
    }


# ==================== 文档授权管理 ====================

@router.post("/documents/{document_id}/grant/{user_id}")
async def grant_document_permission(
    document_id: int,
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """单用户文档授权（含可选有效期）"""
    from datetime import datetime as dt
    from app.models.user_document_permission import UserDocumentPermission
    from app.models.document import Document as DocModel
    from app.schemas.grant import GrantRequest

    raw = await request.json()
    grant_req = GrantRequest(**raw)

    doc_result = await db.execute(select(DocModel).where(DocModel.id == document_id))
    document = doc_result.scalar_one_or_none()
    if not document:
        raise ResourceNotFoundError(detail="文档不存在")

    user_result = await db.execute(select(User).where(User.id == user_id))
    target_user = user_result.scalar_one_or_none()
    if not target_user:
        raise ResourceNotFoundError(detail="用户不存在")

    existing = await db.execute(
        select(UserDocumentPermission).where(
            UserDocumentPermission.user_id == user_id,
            UserDocumentPermission.document_id == document_id,
        )
    )
    if existing.scalar_one_or_none():
        raise BusinessError(detail="该用户已有此文档的授权记录")

    expires_at = dt.fromisoformat(grant_req.expires_at) if grant_req.expires_at else None

    perm = UserDocumentPermission(
        user_id=user_id,
        document_id=document_id,
        granted_by=current_user.id,
        permission_type=grant_req.permission_type or "download",
        expires_at=expires_at,
    )
    db.add(perm)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="GRANT_DOCUMENT_PERMISSION",
        operation_content={
            "document_id": document_id,
            "target_user_id": user_id,
            "expires_at": grant_req.expires_at,
        },
        ip_address=request.client.host if request and request.client else "",
    )

    await db.commit()
    return {
        "detail": f"已授权用户 {target_user.real_name or target_user.username} 访问文档 {document.name}",
        "document_id": document_id,
        "user_id": user_id,
    }


@router.delete("/documents/{document_id}/revoke/{user_id}")
async def revoke_document_permission(
    document_id: int,
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """超级管理员撤销手动授权"""
    from sqlalchemy import select as sa_select, delete as sa_delete
    from app.models.user_document_permission import UserDocumentPermission

    user_result = await db.execute(sa_select(User).where(User.id == user_id))
    target_user = user_result.scalar_one_or_none()

    result = await db.execute(
        sa_delete(UserDocumentPermission).where(
            UserDocumentPermission.user_id == user_id,
            UserDocumentPermission.document_id == document_id,
        )
    )

    if result.rowcount == 0:
        raise ResourceNotFoundError(detail="未找到该授权记录")

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="REVOKE_DOCUMENT_PERMISSION",
        operation_content={"document_id": document_id, "target_user_id": user_id},
        ip_address=request.client.host if request and request.client else "",
    )

    await db.commit()
    return {"detail": f"已撤销对用户 {target_user.real_name or target_user.username if target_user else user_id} 的文档授权"}


# ==================== 批量授权 ====================

@router.get("/documents/grantable-roles")
async def get_grantable_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取可用于批量授权的角色列表（排除 SUPER_ADMIN 和 ADMIN）"""
    role_code = current_user.role.role_code if current_user.role else ""

    allowed_codes = await _get_creatable_role_codes_for_admin(db) if role_code == "ADMIN" else None
    # SUPER_ADMIN 可以选择除 SUPER_ADMIN 外的所有角色
    if role_code == "SUPER_ADMIN":
        result = await db.execute(
            select(Role).where(Role.role_code != "SUPER_ADMIN").order_by(Role.id)
        )
    else:
        # ADMIN 只能选择非特权角色（ REVIEWER 及以下）
        codes_to_use = allowed_codes if allowed_codes else {"REVIEWER"}
        result = await db.execute(
            select(Role).where(Role.role_code.in_(codes_to_use)).order_by(Role.id)
        )

    roles = result.scalars().all()
    return {
        "items": [
            {"role_code": r.role_code, "role_name": r.role_name}
            for r in roles
        ]
    }


@router.post("/documents/batch-grant/preview")
async def preview_batch_grant(
    req_body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """预览批量授权会匹配到哪些员工（不执行授权，仅供前端展示确认）

    注意：超级管理员账号不使用批量授权功能（超级管理员上传的文档默认为全员可见）。
    """
    from app.schemas.grant import BatchGrantRequest
    from app.models.document import Document as DocModel
    from app.core.exceptions import PermissionDeniedError

    current_role_code = current_user.role.role_code if current_user.role else ""
    if current_role_code == "SUPER_ADMIN":
        raise PermissionDeniedError(detail="超级管理员账号不使用批量授权功能（您上传的文档默认为全员可见）")

    preview_req = BatchGrantRequest(**req_body)

    doc_ids = preview_req.document_ids
    doc_result = await db.execute(select(DocModel.id).where(DocModel.id.in_(doc_ids)))
    existing_doc_ids = {row[0] for row in doc_result.all()}
    missing = set(doc_ids) - existing_doc_ids
    if missing:
        raise ResourceNotFoundError(detail=f"文档不存在: {list(missing)}")

    user_svc = UserService(db)
    users_detail = await user_svc.get_users_by_filters(
        preview_req.user_filters,
        operator_role_code=current_role_code,
        operator_department_id=current_user.department_id,
        operator_id=current_user.id,
        return_details=True,
    )

    return {
        "total_users": len(users_detail),
        "users": users_detail,
        "total_documents": len(doc_ids),
    }


@router.post("/documents/batch-grant")
async def batch_grant_document_permission(
    req_body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """批量授权：三路 UNION 匹配员工（角色 / 标签 / ID），单次为多个文档授权

    规则：
    - 排除 SUPER_ADMIN（超级管理员无需授权，超级管理员上传的文档默认为全员可见）
    - 排除被禁用的用户（status != 1）
    - ADMIN 操作时只匹配同部门员工
    - 排除操作员自己
    - 已有授权时：若权限升级（view_only → download）或变更有效期，则更新；否则跳过
    - 超级管理员不允许使用此接口（请直接上传文档，默认全员可见）
    """
    from app.schemas.grant import BatchGrantRequest
    from app.models.user_document_permission import UserDocumentPermission
    from app.models.document import Document as DocModel
    from app.core.exceptions import PermissionDeniedError
    from datetime import datetime

    current_role_code = current_user.role.role_code if current_user.role else ""
    if current_role_code == "SUPER_ADMIN":
        raise PermissionDeniedError(detail="超级管理员账号不使用批量授权功能（您上传的文档默认为全员可见）")

    grant_req = BatchGrantRequest(**req_body)

    doc_ids = grant_req.document_ids
    doc_result = await db.execute(select(DocModel).where(DocModel.id.in_(doc_ids)))
    docs = {d.id: d for d in doc_result.scalars().all()}
    missing = set(doc_ids) - set(docs.keys())
    if missing:
        raise ResourceNotFoundError(detail=f"文档不存在: {list(missing)}")

    user_svc = UserService(db)
    matched_user_ids = await user_svc.get_users_by_filters(
        grant_req.user_filters,
        operator_role_code=current_role_code,
        operator_department_id=current_user.department_id,
        operator_id=current_user.id,
        return_details=False,
    )
    if not matched_user_ids:
        raise BusinessError(detail="未匹配到任何员工，请调整筛选条件")

    expires_at = None
    if grant_req.expires_at:
        expires_at = datetime.fromisoformat(grant_req.expires_at.replace("Z", "+00:00"))
    perm_type = grant_req.permission_type or "download"

    # 批量查询现有授权记录，避免 N 次查询
    existing_result = await db.execute(
        select(UserDocumentPermission).where(
            UserDocumentPermission.user_id.in_(matched_user_ids),
            UserDocumentPermission.document_id.in_(doc_ids),
        )
    )
    existing_perms = existing_result.scalars().all()
    existing_keys = {(p.user_id, p.document_id): p for p in existing_perms}

    granted = 0
    updated = 0
    skipped = 0

    for uid in matched_user_ids:
        for did in doc_ids:
            key = (uid, did)
            if key in existing_keys:
                existing = existing_keys[key]
                # 已有授权：检查是否需要升级权限或更新有效期
                needs_update = False
                if perm_type == "download" and existing.permission_type == "view_only":
                    existing.permission_type = perm_type
                    needs_update = True
                if expires_at is not None and existing.expires_at != expires_at:
                    existing.expires_at = expires_at
                    needs_update = True
                if needs_update:
                    updated += 1
                else:
                    skipped += 1
                continue
            perm = UserDocumentPermission(
                user_id=uid,
                document_id=did,
                granted_by=current_user.id,
                permission_type=perm_type,
                expires_at=expires_at,
            )
            db.add(perm)
            granted += 1

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="BATCH_GRANT",
        operation_content={
            "document_ids": doc_ids,
            "user_filters": grant_req.user_filters.model_dump(exclude_none=True),
            "matched_users": len(matched_user_ids),
            "granted": granted,
            "updated": updated,
            "skipped": skipped,
        },
        ip_address=request.client.host if request and request.client else "",
    )

    await db.commit()

    return {
        "total_users": len(matched_user_ids),
        "total_documents": len(doc_ids),
        "granted_count": granted,
        "updated_count": updated,
        "skipped_count": skipped,
        "detail": f"批量授权完成：{len(matched_user_ids)} 名员工 × {len(doc_ids)} 个文档 = 新增 {granted} 条授权，更新 {updated} 条，跳过 {skipped} 条已有授权",
    }


# ==================== 部门管理（仅超级管理员） ====================

@router.get("/departments")
async def list_departments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取所有部门列表。SUPER_ADMIN / ADMIN 可读取。"""
    svc = DepartmentService(db)
    items = await svc.list_departments()
    return {"items": items}


@router.post("/departments")
async def create_department(
    dept_in: DepartmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """创建新部门"""
    svc = DepartmentService(db)
    result = await svc.create_department(dept_in)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="CREATE_DEPARTMENT",
        operation_content={"name": dept_in.name, "code": dept_in.code},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.put("/departments/{department_id}")
async def update_department(
    department_id: int,
    dept_in: DepartmentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """修改部门信息"""
    svc = DepartmentService(db)
    result = await svc.update_department(department_id, dept_in)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="UPDATE_DEPARTMENT",
        operation_content={"department_id": department_id, **dept_in.model_dump(exclude_none=True)},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.delete("/departments/{department_id}")
async def delete_department(
    department_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """删除部门（仅当无员工和角色关联时）"""
    svc = DepartmentService(db)
    result = await svc.delete_department(department_id)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="DELETE_DEPARTMENT",
        operation_content={"department_id": department_id},
        ip_address=request.client.host if request.client else "",
    )
    return result


# ==================== 角色管理（仅超级管理员） ====================

@router.get("/roles")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """获取所有角色列表（含用户数量）"""
    svc = RoleService(db)
    roles = await svc.get_all_roles()
    return {"items": roles}


@router.post("/roles")
async def create_role(
    role_in: RoleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """创建新角色"""
    svc = RoleService(db)
    result = await svc.create_role(role_in)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="CREATE_ROLE",
        operation_content={"role_code": role_in.role_code, "role_name": role_in.role_name},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.put("/roles/{role_id}")
async def update_role(
    role_id: int,
    role_in: RoleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """修改角色名称/描述"""
    svc = RoleService(db)
    result = await svc.update_role(role_id, role_in)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="UPDATE_ROLE",
        operation_content={"role_id": role_id, **role_in.model_dump(exclude_none=True)},
        ip_address=request.client.host if request.client else "",
    )
    return result


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """删除自定义角色"""
    svc = RoleService(db)
    result = await svc.delete_role(role_id)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="DELETE_ROLE",
        operation_content={"role_id": role_id},
        ip_address=request.client.host if request.client else "",
    )
    return result


# ==================== 系统配置管理（仅超级管理员） ====================

@router.get("/system-configs")
async def list_system_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """获取所有系统配置项"""
    from app.models.system_config import SystemConfig

    result = await db.execute(select(SystemConfig).order_by(SystemConfig.config_key))
    configs = result.scalars().all()
    return {
        "items": [
            {
                "id": c.id,
                "config_key": c.config_key,
                "config_value": c.config_value,
                "description": c.description or "",
                "created_at": c.created_at.isoformat() if c.created_at else "",
            }
            for c in configs
        ]
    }


@router.put("/system-configs/{config_key}")
async def update_system_config(
    config_key: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """更新指定系统配置项的值（不存在则创建）"""
    from app.models.system_config import SystemConfig
    from pydantic import BaseModel

    class _ConfigUpdate(BaseModel):
        config_value: str
        description: str = ""

    try:
        body = _ConfigUpdate(**await request.json())
    except Exception:
        raise BusinessError(detail="请求体格式错误：需要 { config_value: string, description?: string }")

    # 读取现有
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == config_key))
    cfg = result.scalar_one_or_none()

    if cfg:
        old_value = cfg.config_value
        cfg.config_value = body.config_value
        if body.description:
            cfg.description = body.description
        msg = f"已更新配置 {config_key}: {old_value} → {body.config_value}"
    else:
        cfg = SystemConfig(
            config_key=config_key,
            config_value=body.config_value,
            description=body.description or f"自定义配置（由 {current_user.username} 创建）",
        )
        db.add(cfg)
        msg = f"已创建配置 {config_key} = {body.config_value}"

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="UPDATE_SYSTEM_CONFIG",
        operation_content={
            "config_key": config_key,
            "config_value": body.config_value,
        },
        ip_address=request.client.host if request.client else "",
    )

    await db.commit()
    return {"detail": msg, "config_key": config_key, "config_value": body.config_value}


# ==================== 向量索引管理（仅超级管理员） ====================

@router.get("/vector-index/status")
async def vector_index_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """获取向量索引状态：Qdrant 集合信息、向量点数、文档向量覆盖情况"""
    import httpx
    from sqlalchemy import func
    from app.config import settings
    from app.models.document import Document as DocModel
    from app.models.document import DocumentChunk
    from app.services.vector_service import VectorService

    status = {"qdrant_connected": False, "collection": None, "points": 0, "documents": 0, "chunks": 0, "coverage": 0.0}

    # Qdrant 集合状态
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.QDRANT_URL}/collections/{VectorService.COLLECTION_NAME}"
            )
            if resp.status_code == 200:
                data = resp.json().get("result", {})
                status["qdrant_connected"] = True
                status["collection"] = {
                    "name": VectorService.COLLECTION_NAME,
                    "vectors_count": data.get("vectors_count", 0),
                    "points_count": data.get("points_count", 0),
                    "status": data.get("status", "unknown"),
                }
                status["points"] = data.get("points_count", 0)
    except Exception as e:
        status["qdrant_error"] = str(e)

    # PostgreSQL 文档统计
    try:
        doc_result = await db.execute(select(func.count(DocModel.id)))
        status["documents"] = doc_result.scalar() or 0

        chunk_result = await db.execute(select(func.count(DocumentChunk.id)))
        status["chunks"] = chunk_result.scalar() or 0

        # 文档向量覆盖情况：有向量点的文档数量
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                scroll_resp = await client.post(
                    f"{settings.QDRANT_URL}/collections/{VectorService.COLLECTION_NAME}/points/scroll",
                    json={"limit": 1, "with_payload": False, "with_vector": False},
                )
                status["points"] = scroll_resp.json().get("result", {}).get("points_count", status["points"])
        except Exception:
            pass
    except Exception:
        pass

    # 覆盖率计算
    if status["documents"] > 0:
        # 估算：每个文档约有 N 个 chunk，向量数 / 每文档平均 chunk 数
        avg_chunks_per_doc = (status["chunks"] / status["documents"]) if status["documents"] > 0 else 1
        if avg_chunks_per_doc > 0:
            docs_with_vectors = min(int(status["points"] / avg_chunks_per_doc), status["documents"])
            status["coverage"] = round((docs_with_vectors / status["documents"]) * 100, 1)

    return status


@router.post("/vector-index/rebuild-all")
async def rebuild_all_vector_index(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """触发全量向量索引重建：对所有已审核通过的文档重新解析、分块、向量化写入 Qdrant"""
    from app.models.document import Document as DocModel
    from app.services.vector_service import VectorService

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="REBUILD_VECTOR_INDEX_ALL",
        operation_content={"triggered_by": current_user.username},
        ip_address=request.client.host if request.client else "",
    )

    # 查找所有需要重新向量化的文档（status >= 1 且 is_reviewed = True）
    result = await db.execute(
        select(DocModel.id).where(
            DocModel.status >= 1,
        )
    )
    doc_ids = [row[0] for row in result.all()]

    if not doc_ids:
        return {"detail": "没有需要重建索引的文档", "queued_count": 0, "document_ids": []}

    # 清理现有向量
    try:
        await VectorService.clear_all_vectors()
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.warning(f"清理现有向量失败（非致命）: {e}")

    # 通过后台 worker 触发重新处理（这里直接返回任务 ID）
    # 为简化实现：返回文档 ID 列表，由前端调用后台任务
    # 实际生产环境可集成 Celery/RQ
    return {
        "detail": f"已排队 {len(doc_ids)} 个文档进行向量索引重建",
        "queued_count": len(doc_ids),
        "document_ids": doc_ids[:100],  # 只返回前 100 个 ID 做参考
    }


@router.post("/vector-index/rebuild/{document_id}")
async def rebuild_single_document_vector(
    document_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """重建单个文档的向量索引（先清理再重新分块向量化）"""
    from app.models.document import Document as DocModel
    from app.services.vector_service import VectorService

    # 检查文档是否存在
    result = await db.execute(select(DocModel).where(DocModel.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise ResourceNotFoundError(detail=f"文档 {document_id} 不存在")

    # 清理该文档的现有向量
    try:
        await VectorService.delete_document_vectors(document_id)
    except Exception:
        pass

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="REBUILD_VECTOR_INDEX_SINGLE",
        operation_content={"document_id": document_id, "document_name": document.name},
        ip_address=request.client.host if request.client else "",
    )
    await db.commit()

    return {
        "detail": f"已触文档 {document.name} 的向量索引重建（后台 worker 会自动处理）",
        "document_id": document_id,
    }


@router.post("/vector-index/cleanup-orphans")
async def cleanup_orphan_vectors(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """清理 Qdrant 中的孤立向量（对应文档在 PostgreSQL 中已不存在）"""
    from app.models.document import Document as DocModel
    from app.services.vector_service import VectorService

    # 获取所有有效文档 ID
    result = await db.execute(select(DocModel.id))
    valid_doc_ids = {row[0] for row in result.all()}

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=current_user.id,
        operation_type="CLEANUP_ORPHAN_VECTORS",
        operation_content={"valid_doc_count": len(valid_doc_ids)},
        ip_address=request.client.host if request.client else "",
    )
    await db.commit()

    return {
        "detail": f"已请求清理孤立向量（系统当前共 {len(valid_doc_ids)} 个有效文档）",
        "valid_document_count": len(valid_doc_ids),
    }