from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.tag import DataTagSimpleResponse


class DocumentUpload(BaseModel):
    tag_ids: List[int] = Field(default_factory=list, description="选中的数据标签ID列表")
    upload_type: str = "regular"  # regular | cad


class DocumentResponse(BaseModel):
    id: int
    name: str
    file_size: int = 0
    tags: List[DataTagSimpleResponse] = Field(default_factory=list)
    format: str = ""
    source_type: str = ""
    status: int
    status_text: str = ""
    uploader_name: str = ""
    uploader_id: int = 0
    department_id: Optional[int] = None
    access_type: str = "APPLY_REQUIRED"
    access_mode: str = "department_public"
    is_public_to_all: int = 0
    is_favorited: bool = False
    is_parsed: int = 0  # 0=未解析, 1=已解析
    chunk_count: int = 0  # 解析后的分块数量
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        if hasattr(obj, '__dict__') and hasattr(obj, 'tags'):
            tags_simple = []
            for t in obj.tags:
                cat = t.category
                tags_simple.append(DataTagSimpleResponse(
                    id=t.id,
                    name=t.name,
                    category_id=t.category_id,
                    category_name=cat.name if cat else "",
                    color=cat.color if cat else "primary",
                    category_code=cat.code if cat else "",
                ))
            obj.tags = tags_simple
        return super().model_validate(obj, *args, **kwargs)


class DocumentListResponse(BaseModel):
    total: int
    items: List[DocumentResponse]


class DocumentApplyRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500, description="申请原因")
    reviewer_ids: List[int] = Field(..., min_length=1, description="指定的审核员/管理员ID列表（至少1人）")
    expected_hours: int = Field(24, ge=0, le=720, description="期望授权时长（小时），0表示永久，默认24")


class ExportRequest(BaseModel):
    query: Optional[str] = None
    document_ids: Optional[List[int]] = None
    tag_ids: Optional[List[int]] = None
    format: str = Field("pdf", description="导出格式: pdf | csv")


class DocumentUpdateTags(BaseModel):
    tag_ids: List[int] = Field(default_factory=list, description="选中的数据标签ID列表")


class SetAccessModeRequest(BaseModel):
    """设置文档访问模式请求"""
    access_mode: str = Field(
        "department_public",
        description="访问模式: department_public(部门内公开) / apply_required(需申请访问)",
    )


class DocumentViewUrl(BaseModel):
    """文档查看/预览 URL 响应"""
    url: str
    mime_type: str


class DocumentDownloadUrl(BaseModel):
    """文档下载 URL 响应"""
    url: str
    filename: str
    mime_type: str


class DownloadHistoryItem(BaseModel):
    id: int
    document_id: int
    document_name: str
    operation_type: str = ""
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DownloadHistoryList(BaseModel):
    total: int
    items: List[DownloadHistoryItem]


class DocumentUploadResponse(BaseModel):
    id: int
    name: str
    message: str = "上传成功，等待审核"
    status: int

    model_config = {"from_attributes": True}
