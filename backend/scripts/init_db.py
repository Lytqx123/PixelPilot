"""
系统初始化脚本

独立运行：python scripts/init_db.py

功能：
1. 同步方式连接数据库，创建所有表
2. 初始化 7 个默认角色（含 ADMIN）
3. 创建默认超级管理员账号 (758441925 / admin123)
4. 初始化默认系统标签数据（车型/区域/文档类型）
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.database import Base
from app.models import Role, User
from app.models import (  # noqa: F401
    UserDataScope,
    Document,
    DocumentChunk,
    AccessApplication,
    TempAccessToken,
    AuditLog,
    SystemTag,
    SystemConfig,
    UserFavorite,
    UserDocumentPermission,
    Conversation,
    ConversationMessage,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEFAULT_ROLES = [
    {"role_code": "SUPER_ADMIN", "role_name": "超级管理员", "description": "系统最高权限，可管理所有账号（含管理员）", "is_system": True},
    {"role_code": "ADMIN", "role_name": "管理员", "description": "系统管理权限，负责系统运维与管控（不可操作超级管理员）", "is_system": True},
    {"role_code": "REVIEWER", "role_name": "审核员", "description": "负责文档审核与权限申请审核", "is_system": True},
]

DEFAULT_SYSTEM_TAGS = [
    {"tag_type": "model", "tag_value": "Model_X"},
    {"tag_type": "model", "tag_value": "Model_Y"},
    {"tag_type": "model", "tag_value": "Model_Z"},
    {"tag_type": "model", "tag_value": "Model_W"},
    {"tag_type": "region", "tag_value": "CN"},
    {"tag_type": "region", "tag_value": "EU"},
    {"tag_type": "region", "tag_value": "NA"},
    {"tag_type": "region", "tag_value": "JP"},
    {"tag_type": "doc_type", "tag_value": "TEST_REPORT"},
    {"tag_type": "doc_type", "tag_value": "BUG_REPORT"},
    {"tag_type": "doc_type", "tag_value": "REGULATION"},
    {"tag_type": "doc_type", "tag_value": "ENGINEERING_DRAWING"},
    {"tag_type": "doc_type", "tag_value": "ROAD_TEST_DATA"},
    {"tag_type": "doc_type", "tag_value": "MAINTENANCE_GUIDE"},
]

DEFAULT_ADMIN = {
    "username": "758441925",
    "password": "admin123",
    "real_name": "妤唯欢",
    "gender": "男",
    "phone": "",
    "personal_description": "",
}


def get_sync_db_url() -> str:
    from app.config import settings
    url = settings.DATABASE_URL
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "+psycopg2")
    return url


def init():
    sync_url = get_sync_db_url()
    engine = create_engine(sync_url, echo=False)

    print("正在创建数据库表...")
    Base.metadata.create_all(engine)
    print("数据库表创建完成（含 system_tags 标签管理表）。")

    with Session(engine) as session:
        print("正在初始化默认角色...")
        for role_data in DEFAULT_ROLES:
            existing = session.execute(
                select(Role).where(Role.role_code == role_data["role_code"])
            ).scalar_one_or_none()
            if not existing:
                role = Role(**role_data)
                session.add(role)
                print(f"  + 创建角色: {role_data['role_name']} ({role_data['role_code']})")
            else:
                print(f"  - 角色已存在: {role_data['role_code']}，跳过")
        session.commit()

        print("正在初始化超级管理员账号...")
        existing_admin = session.execute(
            select(User).where(User.username == DEFAULT_ADMIN["username"])
        ).scalar_one_or_none()

        if not existing_admin:
            admin_role = session.execute(
                select(Role).where(Role.role_code == "SUPER_ADMIN")
            ).scalar_one()

            admin = User(
                username=DEFAULT_ADMIN["username"],
                password_hash=pwd_context.hash(DEFAULT_ADMIN["password"]),
                real_name=DEFAULT_ADMIN["real_name"],
                gender=DEFAULT_ADMIN.get("gender", ""),
                phone=DEFAULT_ADMIN["phone"],
                personal_description=DEFAULT_ADMIN["personal_description"],
                role_id=admin_role.id,
                status=1,
            )
            session.add(admin)
            session.commit()
            print(f"  + 创建管理员账号: {DEFAULT_ADMIN['username']}")
        else:
            print(f"  - 管理员账号已存在，跳过。")

        print("正在初始化默认系统标签...")

        for tag_data in DEFAULT_SYSTEM_TAGS:
            existing = session.execute(
                select(SystemTag).where(
                    SystemTag.tag_type == tag_data["tag_type"],
                    SystemTag.tag_value == tag_data["tag_value"],
                )
            ).scalar_one_or_none()
            if not existing:
                tag = SystemTag(tag_type=tag_data["tag_type"], tag_value=tag_data["tag_value"])
                session.add(tag)
                print(f"  + 创建标签: [{tag_data['tag_type']}] {tag_data['tag_value']}")
        session.commit()

        print("正在初始化默认系统配置...")
        from app.models.system_config import SystemConfig

        DEFAULT_SYSTEM_CONFIGS = [
            {"config_key": "access_token_expire_minutes", "config_value": "480", "description": "JWT 令牌有效期（分钟）"},
            {"config_key": "temp_token_expire_hours", "config_value": "24", "description": "临时访问令牌有效期（小时）"},
            {"config_key": "application_cooldown_days", "config_value": "7", "description": "访问申请冷却期（天）"},
            {"config_key": "upload_max_size_mb", "config_value": "50", "description": "文件上传大小上限（MB）"},
            {"config_key": "vector_dimension", "config_value": "1024", "description": "向量维度（bge-m3 = 1024维）"},
            {"config_key": "vector_distance_metric", "config_value": "Cosine", "description": "向量距离度量方式"},
            {"config_key": "dedup_similarity_threshold", "config_value": "0.98", "description": "文档去重相似度阈值（0-1）"},
        ]

        for cfg_data in DEFAULT_SYSTEM_CONFIGS:
            existing = session.execute(
                select(SystemConfig).where(SystemConfig.config_key == cfg_data["config_key"])
            ).scalar_one_or_none()
            if not existing:
                cfg = SystemConfig(**cfg_data)
                session.add(cfg)
                print(f"  + 创建配置: {cfg_data['config_key']} = {cfg_data['config_value']}")
            else:
                print(f"  - 配置已存在: {cfg_data['config_key']}，跳过")
        session.commit()

    engine.dispose()

    print("\n默认标签体系已就绪:")
    by_type = {}
    for t in DEFAULT_SYSTEM_TAGS:
        by_type.setdefault(t["tag_type"], []).append(t["tag_value"])
    for tag_type, values in by_type.items():
        type_label = {"model": "车型标签", "region": "区域标签", "doc_type": "文档类型标签"}.get(tag_type, tag_type)
        print(f"  [{type_label}] {', '.join(values)}")

    print("\n" + "=" * 50)
    print("系统初始化完成！")
    print(f"  14 张数据表已就绪")
    print(f"  默认超级管理员账号: {DEFAULT_ADMIN['username']}")
    print(f"  默认超级管理员密码: {DEFAULT_ADMIN['password']}")
    print(f"  标签管理: 超级管理员/管理员可在「系统设置」页面管理标签（增删改）")
    print("=" * 50)


if __name__ == "__main__":
    init()