# 全局常量：根管理员、支持格式、大小限制、水印配置等
import os

# 系统根管理员用户名（硬编码，不可被删除/禁用/编辑，全局唯一）
ROOT_ADMIN_USERNAME = "758441925"

# 可以浏览器预览的文件格式（新标签页打开）
VIEWABLE_FORMATS = {".pdf", ".md", ".txt", ".png", ".jpg", ".jpeg"}

# 可以显示文段内容（关键词高亮）的格式
TEXT_CONTENT_FORMATS = {".pdf", ".docx", ".xlsx", ".md", ".txt", ".csv"}

# 支持上传的文件格式及其大小上限
ALLOWED_EXTENSIONS = {
    ".pdf": 50 * 1024 * 1024,      # 50MB
    ".docx": 50 * 1024 * 1024,     # 50MB
    ".doc": 50 * 1024 * 1024,      # 50MB
    ".xlsx": 50 * 1024 * 1024,     # 50MB
    ".xls": 50 * 1024 * 1024,      # 50MB
    ".txt": 50 * 1024 * 1024,      # 50MB
    ".md": 50 * 1024 * 1024,       # 50MB
    ".csv": 50 * 1024 * 1024,      # 50MB
    ".png": 50 * 1024 * 1024,      # 50MB
    ".jpg": 50 * 1024 * 1024,      # 50MB
    ".jpeg": 50 * 1024 * 1024,     # 50MB
    ".dwg": 200 * 1024 * 1024,     # 200MB (CAD)
    ".dxf": 200 * 1024 * 1024,     # 200MB (CAD)
}

# MIME 类型映射
MIME_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".dwg": "application/octet-stream",
    ".dxf": "application/dxf",
}

# 角色编码与名称映射（仅包含系统内置角色，自定义角色从数据库读取）
ROLE_CODES = {
    "SUPER_ADMIN": "超级管理员",
    "ADMIN": "管理员",
    "REVIEWER": "审核员",
}

# 特权角色：上传文档时免审核（自动通过），并可管理本部门文档
# 注意：ADMIN/REVIEWER 仅对本部门文档有特权，跨部门仍受 access_mode 控制；
#       仅 SUPER_ADMIN 对全部文档有特权。
PRIVILEGED_ROLES = {"SUPER_ADMIN", "ADMIN", "REVIEWER"}

# 文档状态
DOC_STATUS_PENDING = 0      # 待审核
DOC_STATUS_APPROVED = 1     # 已通过
DOC_STATUS_REJECTED = 2     # 已拒绝

# 访问申请状态
APPLICATION_STATUS_PENDING = 0      # 待审核
APPLICATION_STATUS_APPROVED = 1     # 已通过
APPLICATION_STATUS_REJECTED = 2     # 已拒绝

# 用户状态
USER_STATUS_ACTIVE = 1      # 正常
USER_STATUS_DISABLED = 0    # 禁用

# 向量配置
VECTOR_DIMENSION = 1024

def get_mime_type(filename: str) -> str:
    """根据文件名扩展名返回正确的 MIME 类型"""
    ext = os.path.splitext(filename)[1].lower()
    return MIME_MAP.get(ext, "application/octet-stream")


def get_format_type(filename: str) -> str:
    """根据文件名返回格式类型标识（小写扩展名）"""
    return os.path.splitext(filename)[1].lower()


def is_viewable_format(filename: str) -> bool:
    """判断文件格式是否支持浏览器预览"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in VIEWABLE_FORMATS


def is_text_content_format(filename: str) -> bool:
    """判断文件格式是否支持文段内容显示（关键词高亮）"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in TEXT_CONTENT_FORMATS


def get_allowed_max_size(filename: str) -> int:
    """获取文件允许的最大上传大小"""
    ext = os.path.splitext(filename)[1].lower()
    return ALLOWED_EXTENSIONS.get(ext, 50 * 1024 * 1024)