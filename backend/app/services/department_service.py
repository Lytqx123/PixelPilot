from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError, BusinessError
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentResponse


class DepartmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_departments(self) -> List[DepartmentResponse]:
        result = await self.db.execute(select(Department).order_by(Department.id))
        departments = result.scalars().all()
        return [
            DepartmentResponse(id=d.id, name=d.name, code=d.code, description=d.description)
            for d in departments
        ]

    async def create_department(self, data: DepartmentCreate) -> DepartmentResponse:
        existing = await self.db.execute(
            select(Department).where(Department.code == data.code)
        )
        if existing.scalar_one_or_none():
            raise BusinessError(detail="部门编码已存在")

        dept = Department(name=data.name, code=data.code, description=data.description)
        self.db.add(dept)
        await self.db.commit()
        await self.db.refresh(dept)
        return DepartmentResponse(id=dept.id, name=dept.name, code=dept.code, description=dept.description)

    async def update_department(self, department_id: int, data: DepartmentUpdate) -> DepartmentResponse:
        result = await self.db.execute(select(Department).where(Department.id == department_id))
        dept = result.scalar_one_or_none()
        if not dept:
            raise ResourceNotFoundError(detail="部门不存在")

        if data.name is not None:
            dept.name = data.name
        if data.code is not None:
            existing = await self.db.execute(
                select(Department).where(Department.code == data.code, Department.id != department_id)
            )
            if existing.scalar_one_or_none():
                raise BusinessError(detail="部门编码已存在")
            dept.code = data.code
        if data.description is not None:
            dept.description = data.description

        await self.db.commit()
        await self.db.refresh(dept)
        return DepartmentResponse(id=dept.id, name=dept.name, code=dept.code, description=dept.description)

    async def delete_department(self, department_id: int) -> dict:
        result = await self.db.execute(select(Department).where(Department.id == department_id))
        dept = result.scalar_one_or_none()
        if not dept:
            raise ResourceNotFoundError(detail="部门不存在")

        from app.models.user import User
        user_count_result = await self.db.execute(
            select(func.count(User.id)).where(User.department_id == department_id)
        )
        if (user_count_result.scalar() or 0) > 0:
            raise BusinessError(detail="该部门下还有员工，无法删除")

        from app.models.role import Role
        role_count_result = await self.db.execute(
            select(func.count(Role.id)).where(Role.department_id == department_id)
        )
        if (role_count_result.scalar() or 0) > 0:
            raise BusinessError(detail="该部门下还有角色，无法删除")

        await self.db.delete(dept)
        await self.db.commit()
        return {"detail": "部门已删除"}