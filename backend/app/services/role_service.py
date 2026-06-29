from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError, BusinessError
from app.models.role import Role
from app.models.user import User
from app.models.department import Department
from app.schemas.role import RoleCreate, RoleUpdate


class RoleService:
    """角色管理服务 — 仅 SUPER_ADMIN 可操作"""

    SYSTEM_ROLES = {"SUPER_ADMIN", "ADMIN", "REVIEWER"}

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_roles(self) -> list[dict]:
        """获取所有角色列表，含每个角色下的用户数量和所属部门"""
        user_count_subq = (
            select(Role.id, func.count(User.id).label("cnt"))
            .outerjoin(User, User.role_id == Role.id)
            .group_by(Role.id)
            .subquery()
        )
        stmt = (
            select(Role, func.coalesce(user_count_subq.c.cnt, 0).label("user_count"))
            .outerjoin(user_count_subq, Role.id == user_count_subq.c.id)
            .outerjoin(Department, Role.department_id == Department.id)
            .order_by(Role.id)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        dept_map = {}
        for row in rows:
            if row.Role.department:
                dept_map[row.Role.id] = row.Role.department.name
        return [
            {
                "id": row.Role.id,
                "role_code": row.Role.role_code,
                "role_name": row.Role.role_name,
                "description": row.Role.description,
                "is_system": row.Role.is_system,
                "user_count": row.user_count,
                "department_id": row.Role.department_id,
                "department_name": dept_map.get(row.Role.id, ""),
            }
            for row in rows
        ]

    async def create_role(self, data: RoleCreate) -> dict:
        """创建自定义角色（仅 SUPER_ADMIN 可创建），必须指定所属部门"""
        existing = await self.db.execute(
            select(Role).where(Role.role_code == data.role_code)
        )
        if existing.scalar_one_or_none():
            raise BusinessError(detail="角色编码已存在")

        if data.role_code in self.SYSTEM_ROLES:
            raise BusinessError(detail="不可使用系统保留角色编码")

        if not data.department_id:
            raise BusinessError(detail="必须指定所属部门")

        from app.models.department import Department as DeptModel
        dept_result = await self.db.execute(
            select(DeptModel).where(DeptModel.id == data.department_id)
        )
        if not dept_result.scalar_one_or_none():
            raise BusinessError(detail="指定的部门不存在")

        role = Role(
            role_code=data.role_code,
            role_name=data.role_name,
            description=data.description,
            is_system=False,
            department_id=data.department_id,
        )
        self.db.add(role)
        await self.db.commit()
        await self.db.refresh(role)
        return await self._to_dict(role)

    async def update_role(self, role_id: int, data: RoleUpdate) -> dict:
        """修改自定义角色名称/描述/部门（系统角色不可编辑）"""
        role = await self._get_role(role_id)
        if role.is_system:
            raise BusinessError(detail="系统内置角色不可编辑")

        if data.role_name is not None:
            role.role_name = data.role_name
        if data.description is not None:
            role.description = data.description
        if data.department_id is not None:
            role.department_id = data.department_id

        await self.db.commit()
        await self.db.refresh(role)
        return await self._to_dict(role)

    async def delete_role(self, role_id: int) -> dict:
        """删除自定义角色（系统角色不可删除，有用户的角色不可删除）"""
        role = await self._get_role(role_id)

        if role.is_system:
            raise BusinessError(detail="系统内置角色不可删除")

        user_count_result = await self.db.execute(
            select(func.count(User.id)).where(User.role_id == role_id)
        )
        user_count = user_count_result.scalar() or 0
        if user_count > 0:
            raise BusinessError(
                detail=f"该角色下还有 {user_count} 名员工，请先将员工转移到其他角色后再删除"
            )

        await self.db.delete(role)
        await self.db.commit()
        return {"detail": f"角色 {role.role_name} 已删除"}

    async def _get_role(self, role_id: int) -> Role:
        result = await self.db.execute(select(Role).where(Role.id == role_id))
        role = result.scalar_one_or_none()
        if not role:
            raise ResourceNotFoundError(detail="角色不存在")
        return role

    async def _to_dict(self, role: Role) -> dict:
        user_count_result = await self.db.execute(
            select(func.count(User.id)).where(User.role_id == role.id)
        )
        department_name = role.department.name if role.department else ""
        return {
            "id": role.id,
            "role_code": role.role_code,
            "role_name": role.role_name,
            "description": role.description,
            "is_system": role.is_system,
            "user_count": user_count_result.scalar() or 0,
            "department_id": role.department_id,
            "department_name": department_name,
        }