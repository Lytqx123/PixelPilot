# 文档权限校验：超级管理员 > 上传者 > 部门管理员 > 部门公开 > 申请访问
from typing import List, Dict, Any
from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.core.exceptions import PermissionDeniedError
from app.core.constants import PRIVILEGED_ROLES
from app.models.user import User, UserDataScope
from app.models.document import ACCESS_MODE_DEPARTMENT_PUBLIC, ACCESS_MODE_APPLY_REQUIRED

ACCESS_LEVEL_DIRECT = "DIRECT"
ACCESS_LEVEL_APPLY_REQUIRED = "APPLY_REQUIRED"
ACCESS_LEVEL_DENIED = "DENIED"


def is_privileged_role(role_code: str) -> bool:
    """返回 True 如果角色是特权角色（超级管理员/管理员/审核员）"""
    return role_code in PRIVILEGED_ROLES


def is_super_admin(role_code: str) -> bool:
    """返回 True 如果角色是超级管理员"""
    return role_code == "SUPER_ADMIN"


def _split_tags(tag_str: str) -> List[str]:
    """将逗号分隔的标签字符串拆分为列表，去除空白和空字符串"""
    if not tag_str or not tag_str.strip():
        return []
    return [t.strip() for t in tag_str.split(",") if t.strip()]


def _has_tag_match(user_scope_tag: str, document_tags_str: str) -> bool:
    """
    检查用户的单个 scope 标签是否与文档的多标签字符串有交集。
    用户 scope 标签为空表示匹配所有（wildcard）。
    """
    if not user_scope_tag:
        return True
    doc_tags = _split_tags(document_tags_str)
    if not doc_tags:
        return True
    return user_scope_tag in doc_tags


def check_document_access(
    user_scopes: List[Dict[str, str]],
    doc_model_tag: str,
    doc_region_tag: str,
    doc_doc_type_tag: str,
    is_super_admin_user: bool = False,
) -> str:
    """
    检查用户 Scope 标签是否与文档标签匹配（保留作为历史兼容，优先使用新的部门模型）。
    返回: "DIRECT" | "APPLY_REQUIRED" | "DENIED"
    """
    if is_super_admin_user:
        return ACCESS_LEVEL_DIRECT

    if not user_scopes:
        return ACCESS_LEVEL_DENIED

    for scope in user_scopes:
        model_match = _has_tag_match(scope.get("model_tag", ""), doc_model_tag)
        region_match = _has_tag_match(scope.get("region_tag", ""), doc_region_tag)
        doc_type_match = _has_tag_match(scope.get("doc_type_tag", ""), doc_doc_type_tag)

        if model_match and region_match and doc_type_match:
            return ACCESS_LEVEL_DIRECT

    return ACCESS_LEVEL_DENIED


def role_required(*allowed_roles: str):
    """
    FastAPI 依赖工厂：检查当前用户角色是否在允许列表中。
    未匹配则抛出 403 PermissionDeniedError。
    """

    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role and current_user.role.role_code in allowed_roles:
            return current_user
        raise PermissionDeniedError(detail="权限不足：您没有访问此资源的权限")

    return checker


async def get_user_data_scopes(
    db: AsyncSession, user_id: int
) -> List[Dict[str, str]]:
    """查询用户的数据权限范围标签列表，返回字典列表"""
    result = await db.execute(
        select(UserDataScope).where(UserDataScope.user_id == user_id)
    )
    scopes = result.scalars().all()
    return [
        {
            "model_tag": s.model_tag,
            "region_tag": s.region_tag,
            "doc_type_tag": s.doc_type_tag,
        }
        for s in scopes
    ]


async def has_manual_document_permission(
    db: AsyncSession, user_id: int, document_id: int, permission_type: str = "download"
) -> bool:
    """
    检查用户是否有针对特定文档的手动授权（含有效期检查）。
    permission_type 可选: "view_only" | "download"
    """
    return await get_manual_document_permission(db, user_id, document_id, permission_type) is not None


async def get_manual_document_permission(
    db: AsyncSession, user_id: int, document_id: int, permission_type: str = "download"
):
    """
    获取用户针对特定文档的手动授权记录（含有效期检查），返回模型对象或 None。
    permission_type 可选: "view_only" | "download"
    """
    from app.models.user_document_permission import UserDocumentPermission

    conditions = [
        UserDocumentPermission.user_id == user_id,
        UserDocumentPermission.document_id == document_id,
        or_(
            UserDocumentPermission.expires_at.is_(None),
            UserDocumentPermission.expires_at > datetime.now(timezone.utc),
        ),
    ]
    if permission_type == "download":
        conditions.append(UserDocumentPermission.permission_type == "download")
    elif permission_type == "view_only":
        conditions.append(UserDocumentPermission.permission_type.in_(["view_only", "download"]))

    result = await db.execute(
        select(UserDocumentPermission).where(and_(*conditions))
    )
    return result.scalar_one_or_none()


async def has_temp_token_access(
    db: AsyncSession, user_id: int, document_id: int, permission_type: str = "download"
) -> bool:
    """检查用户是否有有效的临时访问令牌"""
    from app.models.temp_token import TempAccessToken

    conditions = [
        TempAccessToken.user_id == user_id,
        TempAccessToken.document_id == document_id,
        or_(
            TempAccessToken.expires_at.is_(None),
            TempAccessToken.expires_at > datetime.now(timezone.utc),
        ),
    ]
    if permission_type == "download":
        conditions.append(TempAccessToken.permission_type == "download")
    elif permission_type == "view_only":
        conditions.append(TempAccessToken.permission_type.in_(["view_only", "download"]))

    result = await db.execute(
        select(TempAccessToken).where(and_(*conditions))
    )
    return result.scalar_one_or_none() is not None


async def check_full_document_access(
    db: AsyncSession,
    user_id: int,
    user_role_code: str,
    user_department_id: int,
    is_uploader: bool,
    document_department_id: int,
    document_access_mode: str,
    model_tag: str,
    region_tag: str,
    doc_type_tag: str,
    document_id: int,
) -> str:
    """
    统一文档权限检查入口（新模型：部门归属 + 访问模式）。
    返回: "DIRECT" | "APPLY_REQUIRED" | "DENIED"
    """
    # 1. 超级管理员 → 直接访问所有部门的所有文档
    if is_super_admin(user_role_code):
        return ACCESS_LEVEL_DIRECT

    # 2. 上传者本人 → 直接访问
    if is_uploader:
        return ACCESS_LEVEL_DIRECT

    # 3. 同部门的管理员/审核员 → 直接访问本部门所有文档
    is_same_department = (
        user_department_id is not None
        and document_department_id is not None
        and user_department_id == document_department_id
    )
    if is_same_department and is_privileged_role(user_role_code):
        return ACCESS_LEVEL_DIRECT

    # 4. 先检查手动授权/临时令牌（作为补充机制，仍然有效）
    if await has_manual_document_permission(db, user_id, document_id, permission_type="view_only"):
        return ACCESS_LEVEL_DIRECT
    if await has_temp_token_access(db, user_id, document_id, permission_type="view_only"):
        return ACCESS_LEVEL_DIRECT

    # 5. 同部门普通员工 → 根据 access_mode 决定
    if is_same_department:
        if document_access_mode == ACCESS_MODE_DEPARTMENT_PUBLIC:
            return ACCESS_LEVEL_DIRECT
        elif document_access_mode == ACCESS_MODE_APPLY_REQUIRED:
            return ACCESS_LEVEL_APPLY_REQUIRED
        else:
            return ACCESS_LEVEL_APPLY_REQUIRED

    # 6. 其他部门用户 → 需申请
    return ACCESS_LEVEL_APPLY_REQUIRED


async def resolve_document_access(
    db: AsyncSession,
    user_id: int,
    user_role_code: str,
    user_department_id: int,
    is_uploader: bool,
    document_department_id: int,
    document_access_mode: str,
    document_id: int,
    is_public_to_all: bool = False,
) -> dict:
    """
    统一解析文档的查看/下载权限，返回 {access_type, can_download, can_view, permission_expires_at}

    权限覆盖链（优先级从高到低）：
    1. 超级管理员（SUPER_ADMIN）→ 所有部门所有文档，DIRECT
    2. 全员可见文档（is_public_to_all=1，通常是超级管理员上传的）→ 所有人 DIRECT，无需申请
    3. 上传者本人 → DIRECT
    4. 同部门管理员/审核员（ADMIN/REVIEWER）→ 同部门所有文档，DIRECT
    5. 手动授权 download → DIRECT
    6. 手动授权 view_only → DIRECT 但不可下载
    7. 临时令牌 download → DIRECT
    8. 临时令牌 view_only → DIRECT 但不可下载
    9. 同部门普通员工 + access_mode=department_public → DIRECT
    10. 同部门普通员工 + access_mode=apply_required → APPLY_REQUIRED
    11. 其他部门用户 → APPLY_REQUIRED

    permission_expires_at：当权限来源于手动授权或临时令牌时，返回到期时间（无到期则为 None）
    """
    from datetime import datetime, timezone
    from app.models.temp_token import TempAccessToken

    # 1. 超级管理员
    if is_super_admin(user_role_code):
        return {"access_type": ACCESS_LEVEL_DIRECT, "can_download": True, "can_view": True, "permission_expires_at": None}

    # 2. 全员可见文档 → 所有人都可直接访问和下载（无需申请）
    if is_public_to_all:
        return {"access_type": ACCESS_LEVEL_DIRECT, "can_download": True, "can_view": True, "permission_expires_at": None}

    # 3. 上传者本人
    if is_uploader:
        return {"access_type": ACCESS_LEVEL_DIRECT, "can_download": True, "can_view": True, "permission_expires_at": None}

    # 4. 同部门管理员/审核员
    is_same_department = (
        user_department_id is not None
        and document_department_id is not None
        and user_department_id == document_department_id
    )
    if is_same_department and is_privileged_role(user_role_code):
        return {"access_type": ACCESS_LEVEL_DIRECT, "can_download": True, "can_view": True, "permission_expires_at": None}

    # 5-6. 手动文档授权（区分 view_only / download）
    manual_download = await get_manual_document_permission(db, user_id, document_id, permission_type="download")
    if manual_download:
        return {"access_type": ACCESS_LEVEL_DIRECT, "can_download": True, "can_view": True, "permission_expires_at": manual_download.expires_at}

    manual_view_only = await get_manual_document_permission(db, user_id, document_id, permission_type="view_only")
    if manual_view_only:
        return {"access_type": ACCESS_LEVEL_DIRECT, "can_download": False, "can_view": True, "permission_expires_at": manual_view_only.expires_at}

    # 7-8. 临时访问令牌
    result = await db.execute(
        select(TempAccessToken).where(
            TempAccessToken.user_id == user_id,
            TempAccessToken.document_id == document_id,
            or_(
                TempAccessToken.expires_at.is_(None),
                TempAccessToken.expires_at > datetime.now(timezone.utc),
            ),
        )
    )
    token_record = result.scalar_one_or_none()
    if token_record:
        if token_record.permission_type == "download":
            return {"access_type": ACCESS_LEVEL_DIRECT, "can_download": True, "can_view": True, "permission_expires_at": token_record.expires_at}
        else:
            return {"access_type": ACCESS_LEVEL_DIRECT, "can_download": False, "can_view": True, "permission_expires_at": token_record.expires_at}

    # 9-10. 同部门普通员工 → 根据 access_mode 决定
    if is_same_department:
        if document_access_mode == ACCESS_MODE_DEPARTMENT_PUBLIC:
            return {"access_type": ACCESS_LEVEL_DIRECT, "can_download": True, "can_view": True, "permission_expires_at": None}
        else:
            return {"access_type": ACCESS_LEVEL_APPLY_REQUIRED, "can_download": False, "can_view": False, "permission_expires_at": None}

    # 11. 其他部门用户 → 需申请
    return {"access_type": ACCESS_LEVEL_APPLY_REQUIRED, "can_download": False, "can_view": False, "permission_expires_at": None}


async def get_visible_documents_filter(
    db: AsyncSession,
    user_id: int,
    user_role_code: str,
    user_department_id: int,
) -> dict:
    """
    返回文档列表查询的过滤条件。

    规则：
    - 超级管理员 → 无部门过滤（可查看所有部门的文档），可选传 department_id 过滤
    - 其他角色 → 只显示用户所在部门的文档
    """
    # 超级管理员：无部门限制，返回空条件
    if is_super_admin(user_role_code):
        return {"department_filter": None, "is_super_admin": True}

    # 其他角色：只显示所在部门的文档
    if user_department_id is not None:
        return {"department_filter": user_department_id, "is_super_admin": False}

    # 用户没有部门（极端情况）：只显示自己上传的
    return {"department_filter": -1, "is_super_admin": False, "user_id_only": user_id}
