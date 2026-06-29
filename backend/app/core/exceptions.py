from typing import Optional, Any, Dict

from fastapi import HTTPException, status


class AuthenticationError(HTTPException):
    """认证异常 (401)"""

    def __init__(self, detail: str = "认证失败"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class PermissionDeniedError(HTTPException):
    """权限不足异常 (403)，支持携带 document_id 等额外字段供前端处理"""

    def __init__(self, detail: str = "权限不足", extra: Optional[Dict[str, Any]] = None):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
        self.extra = extra or {}


class ResourceNotFoundError(HTTPException):
    """资源未找到异常 (404)"""

    def __init__(self, detail: str = "资源未找到"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class BusinessError(HTTPException):
    """业务逻辑异常 (400)"""

    def __init__(self, detail: str = "请求参数错误"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)