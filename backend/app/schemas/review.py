from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class PendingDocument(BaseModel):
    id: int
    name: str
    uploader_name: str = ""
    uploader_id: int = 0
    model_tag: str = ""
    region_tag: str = ""
    doc_type_tag: str = ""
    format: str = ""
    file_size: int = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PendingDocumentList(BaseModel):
    total: int
    items: List[PendingDocument]


class ReviewAction(BaseModel):
    comment: Optional[str] = Field(None, max_length=500, description="审核意见")


class ApproveDocumentRequest(BaseModel):
    """审核通过文档请求（可设置访问模式）"""
    comment: Optional[str] = Field(None, max_length=500, description="审核意见")
    access_mode: Optional[str] = Field(
        None,
        description="访问模式: department_public(部门内公开) / apply_required(需申请访问)，不传则使用默认",
    )


class ReviewDocumentResponse(BaseModel):
    """审核文档响应"""
    message: str
    status: int


class PendingApplication(BaseModel):
    id: int
    applicant_id: int = 0
    applicant_name: str = ""
    document_id: int = 0
    document_name: str = ""
    format: str = ""
    reason: str = ""
    status: int = 0
    assigned_reviewer_ids: Optional[List[int]] = None
    expected_hours: Optional[int] = None
    reviewer_id: Optional[int] = None
    reviewer_name: Optional[str] = ""
    review_time: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PendingApplicationList(BaseModel):
    total: int
    items: List[PendingApplication]


class ApproveApplicationRequest(BaseModel):
    """审核员通过申请时的授权配置"""
    permission_type: str = Field("download", description="授权类型: view_only | download")
    expires_in_hours: Optional[int] = Field(None, ge=0, le=720, description="自定义授权时长（小时），0=永久，None=使用系统默认")


class ReviewHistoryItem(BaseModel):
    id: int
    type: str  # "document" | "application"
    target_name: str = ""
    target_id: int = 0
    action: str  # "approved" | "rejected"
    review_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReviewHistoryList(BaseModel):
    total: int
    items: List[ReviewHistoryItem]


class ReviewerInfo(BaseModel):
    """可选审核员/管理员信息"""
    id: int
    username: str
    real_name: str
    role_code: str
    role_name: str

    model_config = {"from_attributes": True}


class PendingApplicationCountResponse(BaseModel):
    """待处理申请数量（红色铃铛用）"""
    count: int = 0