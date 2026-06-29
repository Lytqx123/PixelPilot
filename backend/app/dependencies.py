from typing import Optional

from fastapi import Depends, Header, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.security import decode_access_token
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.models.user import User, UserDataScope

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    bearer = token
    if not bearer and authorization:
        bearer = authorization.replace("Bearer ", "")
    # 支持?token=xxx方式，方便浏览器直接打开预览链接
    if not bearer:
        bearer = request.query_params.get("token")

    if not bearer:
        raise AuthenticationError(detail="缺少认证凭证")

    try:
        payload = decode_access_token(bearer)
    except ValueError as e:
        raise AuthenticationError(detail=str(e))

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError(detail="认证凭证格式错误")

    result = await db.execute(
        select(User)
        .options(selectinload(User.role), selectinload(User.department))
        .where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise AuthenticationError(detail="用户不存在")
    if user.status == 0:
        raise AuthenticationError(detail="账号已被禁用")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.status != 1:
        raise AuthenticationError(detail="账号已被禁用")
    return current_user


async def get_current_user_data_scopes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserDataScope]:
    result = await db.execute(
        select(UserDataScope).where(UserDataScope.user_id == current_user.id)
    )
    return list(result.scalars().all())


def require_role(*role_codes: str):
    # 角色检查装饰器
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role and current_user.role.role_code in role_codes:
            return current_user
        raise PermissionDeniedError(detail="权限不足")

    return role_checker