from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.core.permissions import role_required
from app.models.user import User
from app.schemas.review import ReviewAction, ApproveDocumentRequest, ApproveApplicationRequest
from app.services.review_service import ReviewService
from app.services.document_service import DocumentService

router = APIRouter(prefix="/review", tags=["审核管理"])

# 审核类接口仅对 ADMIN 和 REVIEWER 开放，SUPER_ADMIN 不参与具体文档审核和访问申请处理
require_reviewer = role_required("REVIEWER", "ADMIN")
# 审核历史接口：超级管理员可查看全部，部门管理员/审核员查看本部门记录
require_history_viewer = role_required("SUPER_ADMIN", "ADMIN", "REVIEWER")


@router.get("/documents/pending")
async def list_pending_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None, description="按文档名/上传人搜索"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_reviewer),
):
    """获取待审核文档列表（分页）"""
    svc = ReviewService(db)
    return await svc.get_pending_documents(current_user, page, page_size, keyword)


@router.post("/documents/{document_id}/approve")
async def approve_document(
    document_id: int,
    action: ApproveDocumentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_reviewer),
):
    """审核通过文档（可设置访问模式）"""
    svc = ReviewService(db)
    return await svc.approve_document(
        document_id,
        current_user.id,
        action.comment,
        action.access_mode,
    )


@router.post("/documents/{document_id}/reject")
async def reject_document(
    document_id: int,
    action: ReviewAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_reviewer),
):
    """审核拒绝文档"""
    svc = ReviewService(db)
    return await svc.reject_document(document_id, current_user.id, action.comment)


@router.get("/documents/{document_id}/preview")
async def preview_pending_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_reviewer),
):
    """预览待审核文档内容（审核员在审批前可查看）"""
    svc = DocumentService(db)
    return await svc.view_document(current_user, document_id)


@router.get("/applications/pending")
async def list_pending_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None, description="按申请人/文档名搜索"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_reviewer),
):
    """获取待处理访问申请列表（按指定审核员+部门过滤，分页）"""
    svc = ReviewService(db)
    return await svc.get_pending_applications(current_user, page, page_size, keyword)


@router.post("/applications/{application_id}/approve")
async def approve_application(
    application_id: int,
    body: ApproveApplicationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_reviewer),
):
    """审核通过访问申请（生成临时令牌，支持细粒度授权）"""
    svc = ReviewService(db)
    return await svc.approve_application(application_id, current_user.id, body.permission_type, body.expires_in_hours)


@router.post("/applications/{application_id}/reject")
async def reject_application(
    application_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_reviewer),
):
    """审核拒绝访问申请（含冷却期检查）"""
    svc = ReviewService(db)
    return await svc.reject_application(application_id, current_user.id)


@router.get("/history")
async def get_review_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None, description="按文档名搜索"),
    department_id: int = Query(None, description="按部门筛选（仅超级管理员可用）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_history_viewer),
):
    """获取审核历史记录（文档+申请合并，分页）。普通管理员/审核员只能查看本部门记录，超级管理员可按部门筛选。"""
    svc = ReviewService(db)
    return await svc.get_review_history(current_user, page, page_size, department_id, keyword)
