from typing import List, Optional
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.core.exceptions import ResourceNotFoundError, BusinessError
from app.core.constants import ROOT_ADMIN_USERNAME
from app.models.user import User, UserDataScope
from app.models.document import Document
from app.schemas.user import UserCreate, UserUpdate, DataScopeResponse


def _build_user_response(user: User) -> dict:
    """将 User ORM 对象转为字典"""
    role_code = user.role.role_code if user.role else ""
    role_name = user.role.role_name if user.role else ""
    department_id = user.department_id
    department_name = user.department.name if user.department else ""
    scopes = [
        DataScopeResponse(
            id=s.id,
            model_tag=s.model_tag,
            region_tag=s.region_tag,
            doc_type_tag=s.doc_type_tag,
        )
        for s in (user.data_scopes or [])
    ]
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "gender": user.gender or "",
        "phone": user.phone or "",
        "personal_description": user.personal_description or "",
        "role_id": user.role_id,
        "role_code": role_code,
        "role_name": role_name,
        "department_id": department_id,
        "department_name": department_name,
        "status": user.status,
        "data_scopes": scopes,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _is_admin_role(role_code: str) -> bool:
    """SUPER_ADMIN 或 ADMIN 都属于广义的管理员角色"""
    return role_code in ("SUPER_ADMIN", "ADMIN")


def _is_root_admin(username: str, role_code: str) -> bool:
    """判断是否为系统根管理员（仅 SUPER_ADMIN 角色的 758441925）"""
    return username == ROOT_ADMIN_USERNAME and role_code == "SUPER_ADMIN"


def _check_admin_department_permission(operator: User, target_department_id: Optional[int]) -> None:
    """
    管理员只能操作同部门员工。
    超级管理员无限制。
    """
    if not operator.role:
        return
    if operator.role.role_code == "SUPER_ADMIN":
        return  # 超级管理员无限制
    if operator.role.role_code == "ADMIN":
        if target_department_id is None:
            raise BusinessError(detail="管理员创建/编辑员工时必须指定所属部门")
        if operator.department_id != target_department_id:
            raise BusinessError(detail="管理员只能操作自己所在部门的员工")


class UserService:
    def __init__(self, db: AsyncSession, operator: Optional[User] = None):
        self.db = db
        self.operator = operator

    async def create_user(self, user_data: UserCreate) -> dict:
        """创建用户：部门权限校验、检查用户名唯一性，哈希密码，创建记录和数据权限"""
        # 管理员只能创建同部门员工
        if self.operator:
            _check_admin_department_permission(self.operator, user_data.department_id)

        existing = await self.db.execute(
            select(User).where(User.username == user_data.username)
        )
        if existing.scalar_one_or_none():
            raise BusinessError(detail="账号已存在")

        user = User(
            username=user_data.username,
            password_hash=hash_password(user_data.password),
            real_name=user_data.real_name,
            gender=user_data.gender or "",
            phone=user_data.phone or "",
            personal_description=user_data.personal_description or "",
            role_id=user_data.role_id,
            department_id=user_data.department_id,
        )
        self.db.add(user)
        await self.db.flush()

        for scope in user_data.data_scopes:
            ds = UserDataScope(
                user_id=user.id,
                model_tag=scope.model_tag,
                region_tag=scope.region_tag,
                doc_type_tag=scope.doc_type_tag,
            )
            self.db.add(ds)

        await self.db.commit()
        await self.db.refresh(user)
        return _build_user_response(user)

    async def update_user(self, user_id: int, user_data: UserUpdate) -> dict:
        """更新用户信息；系统根管理员不可被编辑；管理员只能编辑同部门员工"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ResourceNotFoundError(detail="用户不存在")

        # 管理员只能编辑同部门员工
        if self.operator:
            target_dept = user.department_id
            if user_data.department_id is not None:
                target_dept = user_data.department_id
            _check_admin_department_permission(self.operator, target_dept)

        if user_data.real_name is not None:
            user.real_name = user_data.real_name
        if user_data.gender is not None:
            user.gender = user_data.gender
        if user_data.role_id is not None:
            user.role_id = user_data.role_id
        if user_data.department_id is not None:
            user.department_id = user_data.department_id
        if user_data.status is not None:
            user.status = user_data.status
        if user_data.phone is not None:
            user.phone = user_data.phone

        if user_data.data_scopes is not None:
            await self.db.execute(
                delete(UserDataScope).where(UserDataScope.user_id == user_id)
            )
            for scope in user_data.data_scopes:
                ds = UserDataScope(
                    user_id=user_id,
                    model_tag=scope.model_tag,
                    region_tag=scope.region_tag,
                    doc_type_tag=scope.doc_type_tag,
                )
                self.db.add(ds)

        await self.db.commit()
        await self.db.refresh(user)
        return _build_user_response(user)

    async def disable_user(self, user_id: int) -> dict:
        """切换用户状态（启用↔禁用）；系统根管理员不可禁用"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ResourceNotFoundError(detail="用户不存在")

        from app.models.role import Role
        role_result = await self.db.execute(select(Role).where(Role.id == user.role_id))
        role = role_result.scalar_one_or_none()
        target_role_code = role.role_code if role else ""

        # 系统根管理员不可被禁用
        if _is_root_admin(user.username, target_role_code):
            raise BusinessError(detail="系统根管理员不可被禁用")

        if user.status == 0:
            user.status = 1
            await self.db.commit()
            return {"detail": "用户已启用"}
        else:
            user.status = 0
            await self.db.commit()
            return {"detail": "用户已禁用"}

    async def delete_user(self, user_id: int) -> dict:
        """删除用户；系统根管理员不可删除；级联清理所有关联数据"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ResourceNotFoundError(detail="用户不存在")

        from app.models.role import Role
        from app.models.access_application import AccessApplication
        from app.models.temp_token import TempAccessToken
        from app.models.user_favorite import UserFavorite
        from app.models.user_document_permission import UserDocumentPermission
        from app.models.conversation import Conversation, ConversationMessage
        from app.models.audit_log import AuditLog
        from app.models.user import UserDataScope
        from app.models.document import Document, DocumentChunk
        role_result = await self.db.execute(select(Role).where(Role.id == user.role_id))
        role = role_result.scalar_one_or_none()
        target_role_code = role.role_code if role else ""

        # 系统根管理员不可被删除
        if _is_root_admin(user.username, target_role_code):
            raise BusinessError(detail="系统根管理员不可被删除")

        # 级联清理所有关联数据（按外键依赖顺序）
        # 1. 收藏记录
        await self.db.execute(delete(UserFavorite).where(UserFavorite.user_id == user_id))
        # 2. 手动文档授权
        await self.db.execute(delete(UserDocumentPermission).where(UserDocumentPermission.user_id == user_id))
        # 3. 访问申请记录
        await self.db.execute(delete(AccessApplication).where(AccessApplication.applicant_id == user_id))
        # 4. 临时访问令牌
        await self.db.execute(delete(TempAccessToken).where(TempAccessToken.user_id == user_id))
        # 5. 审计日志（保留历史：物理删除）
        await self.db.execute(delete(AuditLog).where(AuditLog.user_id == user_id))
        # 6. 用户上传的文档（级联删除分块和文档，解决 uploader_id NOT NULL 约束）

        docs_result = await self.db.execute(
            select(Document.id).where(Document.uploader_id == user_id)
        )
        doc_ids = [row[0] for row in docs_result.all()]
        if doc_ids:
            await self.db.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids)))
            await self.db.execute(delete(AccessApplication).where(AccessApplication.document_id.in_(doc_ids)))
            await self.db.execute(delete(UserFavorite).where(UserFavorite.document_id.in_(doc_ids)))
            await self.db.execute(delete(Document).where(Document.id.in_(doc_ids)))

            # 清理 Qdrant 中的向量数据（非致命，失败不影响删除结果）
            try:
                from app.services.vector_service import VectorService
                for doc_id in doc_ids:
                    await VectorService.delete_vectors(doc_id)
            except Exception:
                pass
        # 7. 对话消息 + 对话会话
        conv_result = await self.db.execute(
            select(Conversation.id).where(Conversation.user_id == user_id)
        )
        conv_ids = [row[0] for row in conv_result.all()]
        if conv_ids:
            await self.db.execute(
                delete(ConversationMessage).where(ConversationMessage.conversation_id.in_(conv_ids))
            )
            await self.db.execute(
                delete(Conversation).where(Conversation.user_id == user_id)
            )
        # 8. 数据权限范围
        await self.db.execute(
            delete(UserDataScope).where(UserDataScope.user_id == user_id)
        )
        # 8b. 删除该用户授予他人的手动授权记录（granted_by 悬空处理）
        await self.db.execute(
            delete(UserDocumentPermission).where(UserDocumentPermission.granted_by == user_id)
        )
        # 9. 删除用户本身
        await self.db.delete(user)
        await self.db.commit()
        return {"detail": "用户已删除"}

    async def get_user_list(
        self, page: int, page_size: int, keyword: Optional[str] = None,
        role_id: Optional[int] = None,
        department_id: Optional[int] = None,
    ) -> dict:
        """分页查询用户列表，支持按部门/角色/关键词筛选。默认不显示超级管理员；管理员只能看到同部门员工。"""
        from app.models.role import Role

        base_query = select(User)
        count_query = select(func.count(User.id))

        # 排除超级管理员（system根管理员不可见）
        super_admin_subq = select(Role.id).where(Role.role_code == "SUPER_ADMIN").scalar_subquery()
        base_query = base_query.where(User.role_id != super_admin_subq)
        count_query = count_query.where(User.role_id != super_admin_subq)

        # 管理员只能看到同部门员工
        if self.operator and self.operator.role:
            if self.operator.role.role_code == "ADMIN":
                operator_dept = self.operator.department_id
                if operator_dept is not None:
                    base_query = base_query.where(User.department_id == operator_dept)
                    count_query = count_query.where(User.department_id == operator_dept)

        # 按部门筛选
        if department_id is not None:
            base_query = base_query.where(User.department_id == department_id)
            count_query = count_query.where(User.department_id == department_id)

        if keyword:
            pattern = f"%{keyword}%"
            base_query = base_query.where(
                (User.username.ilike(pattern)) | (User.real_name.ilike(pattern)) | (User.phone.ilike(pattern))
            )
            count_query = count_query.where(
                (User.username.ilike(pattern)) | (User.real_name.ilike(pattern)) | (User.phone.ilike(pattern))
            )
        if role_id is not None:
            base_query = base_query.where(User.role_id == role_id)
            count_query = count_query.where(User.role_id == role_id)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        items_result = await self.db.execute(
            base_query.offset(offset).limit(page_size)
        )
        users: List[User] = list(items_result.scalars().all())

        return {
            "total": total,
            "items": [_build_user_response(u) for u in users],
        }

    async def get_user_detail(self, user_id: int) -> dict:
        """获取单个用户的详细信息（含手机号、个人说明）"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ResourceNotFoundError(detail="用户不存在")
        return _build_user_response(user)

    async def change_password(self, user: User, old_password: str, new_password: str) -> dict:
        """修改当前用户密码：验证旧密码，更新为新密码"""
        if not verify_password(old_password, user.password_hash):
            raise BusinessError(detail="旧密码错误")
        user.password_hash = hash_password(new_password)
        await self.db.commit()
        return {"detail": "密码修改成功"}

    async def update_phone(self, user: User, phone: str) -> dict:
        """更新当前用户电话号码"""
        user.phone = phone
        await self.db.commit()
        await self.db.refresh(user)
        return _build_user_response(user)

    async def get_users_by_filters(
        self,
        filters,
        operator_role_code: Optional[str] = None,
        operator_department_id: Optional[int] = None,
        operator_id: Optional[int] = None,
        return_details: bool = False,
    ):
        """
        三路 UNION 匹配员工：
        1. role_codes → 按角色筛选
        2. tag_filters → 按标签作用域筛选
        3. user_ids → 按ID精确指定

        过滤规则：
        - 排除 SUPER_ADMIN（超级管理员无需授权）
        - 排除被禁用的用户（status != 1）
        - ADMIN 操作时只匹配同部门员工
        - 排除操作员自己

        返回值：
        - return_details=False → List[int] 去重后的 user_id 列表
        - return_details=True  → List[dict] 用户详情列表（用于前端预览）
        """
        from sqlalchemy import union, or_ as sa_or_, and_ as sa_and_
        from app.models.role import Role

        queries = []

        # ========= 路1：角色筛选 =========
        if filters.role_codes:
            valid_role_codes = [rc for rc in filters.role_codes if rc != "SUPER_ADMIN"]
            if valid_role_codes:
                role_query = (
                    select(User.id)
                    .join(Role, User.role_id == Role.id)
                    .where(
                        Role.role_code.in_(valid_role_codes),
                        User.status == 1,
                    )
                )
                queries.append(role_query)

        # ========= 路2：标签作用域筛选（每种标签可多选，OR 匹配；多类型之间 AND 匹配）=========
        if filters.tag_filters:
            tf = filters.tag_filters
            tag_conds = []

            # 车型标签多选（精确匹配，多值 OR）
            if tf.model_tags:
                stripped_model_tags = [t.strip() for t in tf.model_tags if t.strip()]
                if stripped_model_tags:
                    tag_conds.append(UserDataScope.model_tag.in_(stripped_model_tags))

            # 区域标签多选（精确匹配，多值 OR）
            if tf.region_tags:
                stripped_region_tags = [t.strip() for t in tf.region_tags if t.strip()]
                if stripped_region_tags:
                    tag_conds.append(UserDataScope.region_tag.in_(stripped_region_tags))

            # 文档类型标签多选（精确匹配，多值 OR）
            if tf.doc_type_tags:
                stripped_doc_tags = [t.strip() for t in tf.doc_type_tags if t.strip()]
                if stripped_doc_tags:
                    tag_conds.append(UserDataScope.doc_type_tag.in_(stripped_doc_tags))

            if tag_conds:
                tag_query = (
                    select(UserDataScope.user_id)
                    .where(sa_and_(*tag_conds))
                    .distinct()
                )
                queries.append(tag_query)

        # ========= 路3：ID精确指定 =========
        if filters.user_ids:
            id_query = select(User.id).where(
                User.id.in_(filters.user_ids),
                User.status == 1,
            )
            queries.append(id_query)

        if not queries:
            return [] if not return_details else []

        # ========= UNION 合并去重 =========
        if len(queries) == 1:
            combined = queries[0]
        else:
            combined = union(*queries)

        matched_ids_subq = combined.alias("matched_ids")

        # ========= 构建最终查询 =========
        # 基础过滤：排除 SUPER_ADMIN、排除禁用用户、排除操作员自己
        from app.models.department import Department

        exclude_super_admin_subq = select(Role.id).where(Role.role_code == "SUPER_ADMIN").scalar_subquery()

        final_where_conds = [
            User.id == matched_ids_subq.c.id,
            User.role_id != exclude_super_admin_subq,
            User.status == 1,
        ]

        if operator_id is not None:
            final_where_conds.append(User.id != operator_id)

        # ADMIN 操作时限制为同部门
        if operator_role_code == "ADMIN" and operator_department_id is not None:
            final_where_conds.append(User.department_id == operator_department_id)

        final_where = sa_and_(*final_where_conds)

        if not return_details:
            id_result = await self.db.execute(select(matched_ids_subq.c.id).where(final_where).distinct())
            return [row[0] for row in id_result.all()]

        # 返回用户详情（用于前端预览）
        detail_query = (
            select(
                User.id,
                User.username,
                User.real_name,
                Role.role_code,
                Department.name.label("department_name"),
            )
            .join(Role, User.role_id == Role.id, isouter=True)
            .join(Department, User.department_id == Department.id, isouter=True)
            .where(final_where)
            .distinct()
            .order_by(User.real_name)
        )

        detail_result = await self.db.execute(detail_query)
        rows = detail_result.all()

        return [
            {
                "id": row.id,
                "username": row.username,
                "real_name": row.real_name,
                "role_code": row.role_code or "",
                "department_name": row.department_name or "",
            }
            for row in rows
        ]

    async def update_description(self, user: User, personal_description: str) -> dict:
        """更新当前用户个人说明"""
        user.personal_description = personal_description
        await self.db.commit()
        await self.db.refresh(user)
        return _build_user_response(user)