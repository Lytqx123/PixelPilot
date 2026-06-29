# 初始化数据库：创建默认部门、角色和根管理员账号
import asyncio
import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ROOT_ADMIN_USERNAME
from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.models.department import Department
from app.models.role import Role
from app.models.user import User

logger = logging.getLogger(__name__)

DEFAULT_ROOT_ADMIN_PASSWORD = "admin123"


async def _ensure_departments(db: AsyncSession) -> Department:
    """确保存在默认部门，返回超级管理员所属部门"""
    result = await db.execute(select(Department).where(Department.code == "HEADQUARTERS"))
    dept = result.scalar_one_or_none()

    if not dept:
        dept = Department(
            code="HEADQUARTERS",
            name="公司总部",
            description="公司总部部门，内置部门，不可删除",
        )
        db.add(dept)
        await db.flush()
        logger.info("Created default department: HEADQUARTERS")
    else:
        logger.info("Department HEADQUARTERS already exists")
    return dept


async def _ensure_roles(db: AsyncSession, dept: Department) -> dict:
    """确保存在三个系统内置角色，返回 role_code -> Role 映射"""
    required_roles = [
        {"role_code": "SUPER_ADMIN", "role_name": "超级管理员", "description": "系统根管理员，全局唯一", "is_system": True},
        {"role_code": "ADMIN", "role_name": "管理员", "description": "部门管理员，负责本部门员工及文档管理", "is_system": True},
        {"role_code": "REVIEWER", "role_name": "审核员", "description": "文档审核员，负责文档审核与访问申请审批", "is_system": True},
    ]

    roles = {}
    for r in required_roles:
        result = await db.execute(select(Role).where(Role.role_code == r["role_code"]))
        role = result.scalar_one_or_none()
        if not role:
            role = Role(**r, department_id=dept.id)
            db.add(role)
            await db.flush()
            logger.info(f"Created system role: {r['role_code']}")
        else:
            logger.info(f"Role {r['role_code']} already exists")
        roles[r["role_code"]] = role
    return roles


async def _ensure_root_admin(db: AsyncSession, super_admin_role: Role, dept: Department) -> User:
    """确保存在根管理员账号（ROOT_ADMIN_USERNAME）"""
    result = await db.execute(select(User).where(User.username == ROOT_ADMIN_USERNAME))
    user = result.scalar_one_or_none()

    if not user:
        hashed_pw = hash_password(DEFAULT_ROOT_ADMIN_PASSWORD)
        user = User(
            username=ROOT_ADMIN_USERNAME,
            password_hash=hashed_pw,
            real_name="妤唯欢",
            gender="男",
            phone="",
            personal_description="系统内置超级管理员账号",
            role_id=super_admin_role.id,
            department_id=dept.id,
            status=1,
        )
        db.add(user)
        await db.flush()
        logger.info(f"Created root admin user: {ROOT_ADMIN_USERNAME}")
    else:
        logger.info(f"Root admin {ROOT_ADMIN_USERNAME} already exists")
    return user


async def _ensure_system_configs(db: AsyncSession) -> None:
    """确保系统配置表有默认值（幂等：已存在的 key 不覆盖）"""
    from app.models.system_config import SystemConfig
    from app.config import settings

    defaults = [
        ("temp_token_expire_hours", str(settings.TEMP_TOKEN_EXPIRE_HOURS), "临时令牌有效期（小时）"),
        ("application_cooldown_days", str(settings.APPLICATION_COOLDOWN_DAYS), "申请冷却期（天）"),
        ("dedup_similarity_threshold", str(settings.DEDUP_SIMILARITY_THRESHOLD), "文档去重相似度阈值"),
        ("application_expiry_days", str(settings.APPLICATION_EXPIRY_DAYS), "申请过期时间（天）"),
        ("retrieval_top_k", str(settings.RETRIEVAL_TOP_K), "检索返回数量"),
        ("retrieval_similarity_threshold", str(settings.RETRIEVAL_SIMILARITY_THRESHOLD), "检索相似度阈值"),
    ]

    for key, value, desc in defaults:
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.config_key == key)
        )
        if not result.scalar_one_or_none():
            cfg = SystemConfig(config_key=key, config_value=value, description=desc)
            db.add(cfg)
            logger.info(f"Created system config: {key}={value}")
    await db.flush()


async def init_database_data() -> None:
    """初始化数据库：部门 -> 角色 -> 根管理员 -> 系统配置。幂等安全，可多次调用"""
    logger.info("Starting database initialization...")

    async with AsyncSessionLocal() as session:
        try:
            dept = await _ensure_departments(session)
            roles = await _ensure_roles(session, dept)
            await _ensure_root_admin(session, roles["SUPER_ADMIN"], dept)
            await _ensure_system_configs(session)
            await session.commit()
            logger.info("✅ Database initialization completed successfully")

            user_count = await session.execute(select(func.count(User.id)))
            role_count = await session.execute(select(func.count(Role.id)))
            dept_count = await session.execute(select(func.count(Department.id)))

            logger.info(
                f"Database status: {dept_count.scalar()} departments, "
                f"{role_count.scalar()} roles, {user_count.scalar()} users"
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Database initialization failed: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(init_database_data())
