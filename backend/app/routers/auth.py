from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, MenuResponse
from app.schemas.user import ChangePasswordRequest, UpdatePhoneRequest, UpdateDescriptionRequest
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    """用户登录：验证账号密码，检查状态，生成 JWT Token，记录审计日志"""
    svc = AuthService(db)
    user = await svc.authenticate_user(request.username, request.password)

    if not user:
        raise AuthenticationError(detail="账号或密码错误")

    if user.status == 0:
        raise PermissionDeniedError(detail="账号已被禁用，请联系管理员")

    token = svc.generate_token(user)
    user_info = svc.build_user_info(user)

    audit_svc = AuditService(db)
    await audit_svc.create_audit_log(
        user_id=user.id,
        operation_type="LOGIN",
        operation_content={"username": request.username},
        ip_address=http_request.client.host if http_request.client else "",
    )

    return LoginResponse(access_token=token, user_info=user_info)


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户完整信息（含角色、数据权限范围）"""
    from app.core.permissions import get_user_data_scopes

    svc = AuthService(db)
    user_info = svc.build_user_info(current_user)

    scopes = await get_user_data_scopes(db, current_user.id)

    return {
        "id": user_info.id,
        "username": user_info.username,
        "real_name": user_info.real_name,
        "gender": user_info.gender,
        "phone": user_info.phone,
        "personal_description": user_info.personal_description,
        "role_code": user_info.role_code,
        "role_name": user_info.role_name,
        "department_id": user_info.department_id,
        "department_name": user_info.department_name,
        "status": user_info.status,
        "data_scopes": scopes,
    }


@router.get("/menus", response_model=MenuResponse)
async def get_menus(current_user: User = Depends(get_current_user)):
    """根据用户角色动态返回菜单数据"""
    role_code = current_user.role.role_code if current_user.role else ""
    menus = AuthService.get_user_menus(role_code)
    return MenuResponse(menus=menus)


@router.put("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """个人中心：修改密码"""
    svc = UserService(db)
    return await svc.change_password(current_user, request.old_password, request.new_password)


@router.put("/update-phone")
async def update_phone(
    request: UpdatePhoneRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """个人中心：修改电话号码"""
    svc = UserService(db)
    return await svc.update_phone(current_user, request.phone)


@router.put("/update-description")
async def update_description(
    request: UpdateDescriptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """个人中心：修改个人说明"""
    svc = UserService(db)
    return await svc.update_description(current_user, request.personal_description)