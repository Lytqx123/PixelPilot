import os
import json
from typing import Optional, List

from fastapi import APIRouter, Depends, File, UploadFile, Form, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.document import DocumentApplyRequest, DocumentUpdateTags, SetAccessModeRequest
from app.services.document_service import DocumentService
from app.services.data_tag_service import DataTagService
from app.services.favorite_service import FavoriteService
from app.schemas.favorite import FavoriteCreate

router = APIRouter(prefix="/documents", tags=["文档管理"])


@router.get("")
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    department_id: int = Query(None, description="按部门筛选（仅超级管理员可选）"),
    tag_ids: Optional[List[int]] = Query(None, description="按标签ID筛选（多选）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    svc = DocumentService(db)
    return await svc.get_document_list(current_user, page, page_size, keyword, department_id, tag_ids)


@router.get("/departments")
async def get_available_departments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取当前用户可用于筛选的部门列表"""
    svc = DocumentService(db)
    return await svc.get_departments_for_filter(current_user)


@router.get("/data-tags")
async def get_all_data_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取所有数据标签分类和标签，用于上传和筛选"""
    svc = DataTagService(db)
    return await svc.get_all_categories_with_tags()


@router.put("/{document_id}/access-mode")
async def set_document_access_mode(
    document_id: int,
    body: SetAccessModeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """设置文档的访问模式（部门内公开/需申请访问）"""
    svc = DocumentService(db)
    return await svc.set_document_access_mode(current_user, document_id, body.access_mode)


@router.get("/tags")
async def get_document_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """兼容旧API，返回数据标签"""
    svc = DataTagService(db)
    categories = await svc.get_all_categories_with_tags()
    result = {}
    for cat in categories:
        result[cat["code"]] = [t["name"] for t in cat["tags"]]
    return result


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(..., description="上传文件"),
    tag_ids: str = Form("", description="标签ID列表，JSON数组字符串如 [1,2,3]"),
    upload_type: str = Form("regular", description="上传类型: regular(常规文档) / cad(工程图纸)"),
    reviewer_id: Optional[int] = Form(None, description="指定审核员ID（普通员工必填）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # 解析tag_ids
    parsed_tag_ids = []
    if tag_ids:
        try:
            parsed_tag_ids = json.loads(tag_ids)
            if not isinstance(parsed_tag_ids, list):
                parsed_tag_ids = []
        except json.JSONDecodeError:
            parsed_tag_ids = []

    svc = DocumentService(db)
    return await svc.upload_document(current_user, file, parsed_tag_ids, upload_type, reviewer_id)


@router.post("/{document_id}/apply")
async def apply_access(
    document_id: int,
    request: DocumentApplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    svc = DocumentService(db)
    return await svc.apply_document_access(current_user, document_id, request.reason, request.reviewer_ids, request.expected_hours)


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    svc = DocumentService(db)
    return await svc.download_document(current_user, document_id)


@router.get("/{document_id}/view")
async def view_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """在线查看文档（PDF加水印）"""
    svc = DocumentService(db)
    return await svc.view_document(current_user, document_id)


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    svc = DocumentService(db)
    return await svc.delete_document(current_user, document_id)


@router.get("/download-by-token/{token}")
async def download_by_token(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    svc = DocumentService(db)
    return await svc.download_by_token(token)


# ==================== 收藏功能 ====================

@router.post("/favorites")
async def add_favorite(
    req: FavoriteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    svc = FavoriteService(db)
    return await svc.add_favorite(current_user, req.document_id)


@router.delete("/favorites/{document_id}")
async def remove_favorite(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    svc = FavoriteService(db)
    return await svc.remove_favorite(current_user, document_id)


@router.get("/favorites")
async def list_favorites(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    svc = FavoriteService(db)
    return await svc.get_user_favorites(current_user, page, page_size)


@router.get("/download-history")
async def list_download_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    svc = FavoriteService(db)
    return await svc.get_download_history(current_user, page, page_size)


@router.put("/{document_id}/tags")
async def update_document_tags(
    document_id: int,
    tag_update: DocumentUpdateTags,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """更新文档标签（仅超级管理员或文档所属部门管理员/审核员可操作）"""
    svc = DocumentService(db)
    return await svc.update_document_tags(
        current_user,
        document_id,
        tag_update.tag_ids,
    )
