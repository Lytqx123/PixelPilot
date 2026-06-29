from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.schemas.auth import UserInfo, MenuItem


# 角色->菜单映射表（三级结构：角色大类 → 功能模块 → 具体操作）
# 默认菜单（自定义角色和未知角色统一使用）
_DEFAULT_MENU = [
    {
        "key": "group_knowledge", "label": "知识服务", "icon": "Search",
        "children": [
            {"key": "/knowledge", "label": "智能问答", "icon": "ChatDotRound"},
            {"key": "/documents", "label": "文档管理", "icon": "Document"},
            {"key": "/documents/upload", "label": "文件上传", "icon": "Upload"},
            {"key": "/documents/favorites", "label": "我的收藏", "icon": "Star"},
            {"key": "/documents/download-history", "label": "下载历史", "icon": "Download"},
        ],
    },
]

ROLE_MENUS: dict[str, list] = {
    "SUPER_ADMIN": [
        {
            "key": "group_knowledge", "label": "知识服务", "icon": "Search",
            "children": [
                {"key": "/knowledge", "label": "智能问答", "icon": "ChatDotRound"},
                {"key": "/documents", "label": "文档管理", "icon": "Document"},
                {"key": "/documents/upload", "label": "文件上传", "icon": "Upload"},
                {"key": "/documents/favorites", "label": "我的收藏", "icon": "Star"},
                {"key": "/documents/download-history", "label": "下载历史", "icon": "Download"},
            ],
        },
        {
            "key": "group_review", "label": "文档审核中心", "icon": "Checked",
            "children": [
                {"key": "/review/history", "label": "审核历史", "icon": "Clock"},
            ],
        },
        {
            "key": "group_admin", "label": "系统管理", "icon": "Setting",
            "children": [
                {"key": "/admin/users", "label": "人员管理", "icon": "UserFilled"},
                {"key": "/admin/settings", "label": "系统设置", "icon": "Tools"},
                {"key": "/admin/audit", "label": "审计日志", "icon": "Monitor"},
            ],
        },
    ],
    "ADMIN": [
        {
            "key": "group_knowledge", "label": "知识服务", "icon": "Search",
            "children": [
                {"key": "/knowledge", "label": "智能问答", "icon": "ChatDotRound"},
                {"key": "/documents", "label": "文档管理", "icon": "Document"},
                {"key": "/documents/upload", "label": "文件上传", "icon": "Upload"},
                {"key": "/documents/favorites", "label": "我的收藏", "icon": "Star"},
                {"key": "/documents/download-history", "label": "下载历史", "icon": "Download"},
            ],
        },
        {
            "key": "group_review", "label": "文档审核中心", "icon": "Checked",
            "children": [
                {"key": "/review/documents", "label": "文档审核", "icon": "DocumentChecked"},
                {"key": "/review/applications", "label": "访问申请", "icon": "Tickets"},
                {"key": "/review/history", "label": "审核历史", "icon": "Clock"},
            ],
        },
        {
            "key": "group_admin", "label": "系统管理", "icon": "Setting",
            "children": [
                {"key": "/admin/users", "label": "人员管理", "icon": "UserFilled"},
                {"key": "/admin/audit", "label": "审计日志", "icon": "Monitor"},
            ],
        },
    ],
    "REVIEWER": [
        {
            "key": "group_knowledge", "label": "知识服务", "icon": "Search",
            "children": [
                {"key": "/knowledge", "label": "智能问答", "icon": "ChatDotRound"},
                {"key": "/documents", "label": "文档管理", "icon": "Document"},
                {"key": "/documents/upload", "label": "文件上传", "icon": "Upload"},
                {"key": "/documents/favorites", "label": "我的收藏", "icon": "Star"},
                {"key": "/documents/download-history", "label": "下载历史", "icon": "Download"},
            ],
        },
        {
            "key": "group_review", "label": "审核工作", "icon": "Checked",
            "children": [
                {"key": "/review/documents", "label": "待审文档", "icon": "DocumentChecked"},
                {"key": "/review/applications", "label": "访问申请审批", "icon": "Tickets"},
                {"key": "/review/history", "label": "审核历史", "icon": "Clock"},
            ],
        },
    ],
}


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """验证用户名密码，成功返回 User，失败返回 None"""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            return None
        if user.status == 0:
            return None
        return user

    def generate_token(self, user: User) -> str:
        """为用户生成 JWT Token"""
        role_code = user.role.role_code if user.role else ""
        return create_access_token({"sub": str(user.id), "role": role_code})

    @staticmethod
    def get_user_menus(role_code: str) -> list[MenuItem]:
        """根据角色编码返回菜单树"""
        raw_menus = ROLE_MENUS.get(role_code, _DEFAULT_MENU)
        return [MenuItem(**m) for m in raw_menus]

    def build_user_info(self, user: User) -> UserInfo:
        """从 User 模型构建 UserInfo 响应"""
        role_code = user.role.role_code if user.role else ""
        role_name = user.role.role_name if user.role else ""
        department_id = user.department_id
        department_name = user.department.name if user.department else ""
        return UserInfo(
            id=user.id,
            username=user.username,
            real_name=user.real_name,
            gender=user.gender or "",
            phone=user.phone or "",
            personal_description=user.personal_description or "",
            role_code=role_code,
            role_name=role_name,
            department_id=department_id,
            department_name=department_name,
            status=user.status,
        )
