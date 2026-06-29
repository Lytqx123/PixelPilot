from typing import Optional, Union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


async def get_config_value(
    db: AsyncSession,
    key: str,
    fallback: Union[int, float, str],
    value_type: str = "str"
) -> Union[int, float, str]:
    """
    从 system_configs 表动态读取配置，失败时回退到默认值。
    注意：SQL 查询失败时必须回滚事务，否则 PostgreSQL 会将整个事务标记为 aborted，
    后续所有 SQL 都会报错"current transaction is aborted, commands ignored until end of transaction block"。
    
    Args:
        db: 数据库会话
        key: 配置键名
        fallback: 默认值
        value_type: 值类型 ("int", "float", "str")
    """
    try:
        from app.models.system_config import SystemConfig
        result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
        row = result.scalar_one_or_none()
        if row and row.config_value is not None:
            if value_type == "int":
                return int(row.config_value)
            elif value_type == "float":
                return float(row.config_value)
            else:
                return str(row.config_value)
    except Exception:
        await db.rollback()
    return fallback


async def get_config_int(db: AsyncSession, key: str, fallback: int) -> int:
    """读取 int 类型配置"""
    result = await get_config_value(db, key, fallback, "int")
    return int(result)


async def get_config_float(db: AsyncSession, key: str, fallback: float) -> float:
    """读取 float 类型配置"""
    result = await get_config_value(db, key, fallback, "float")
    return float(result)


async def get_config_str(db: AsyncSession, key: str, fallback: str) -> str:
    """读取 str 类型配置"""
    result = await get_config_value(db, key, fallback, "str")
    return str(result)
