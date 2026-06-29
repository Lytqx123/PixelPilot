import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000, description="用户问题")
    top_k: int = Field(7, ge=1, le=20, description="检索数量")
    conversation_id: Optional[int] = Field(None, description="对话会话ID，用于持久化")
    use_large_model: bool = Field(False, description="是否使用 14B 大模型进行更高质量的回答（推理较慢）")


class SourceInfo(BaseModel):
    document_id: int
    document_name: str
    format: str = ""  # 文件格式后缀（如 .pdf, .docx 等），用于前端判断是否显示查看按钮和文段
    page_number: Optional[int] = None
    paragraph: Optional[str] = None
    content_snippet: str = ""
    highlighted_snippet: str = ""  # 带有 <strong> 高亮的 HTML 片段（≤120字）
    access_type: str = "DIRECT"
    score: float = 0.0
    can_download: bool = False   # 是否可直接下载
    can_view: bool = False       # 是否可查看预览
    is_favorited: bool = False   # 是否已收藏
    permission_expires_at: Optional[datetime] = None  # 限时授权到期时间，None=永久或无授权
    has_pending_application: bool = False  # 是否存在待审核的访问申请


class QAResponse(BaseModel):
    answer: str
    sources: List[SourceInfo] = []
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ConversationCreate(BaseModel):
    title: str = Field("新对话", max_length=200)


class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]


class ConversationMessageResponse(BaseModel):
    id: int
    question: str
    answer: str
    sources: Optional[List[SourceInfo]] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class ConversationMessagesResponse(BaseModel):
    messages: List[ConversationMessageResponse]