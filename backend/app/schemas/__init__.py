# Pydantic请求/响应模型，统一导出方便引用
# 兼容旧按名导入（from app.schemas import SomeClass）
from app.schemas.auth import LoginRequest, LoginResponse, UserInfo, MenuResponse, MenuItem
from app.schemas.user import UserCreate, UserUpdate, UserListResponse, DataScopeResponse, ChangePasswordRequest, UpdatePhoneRequest, UpdateDescriptionRequest
from app.schemas.document import (
    DocumentUpload, DocumentResponse, DocumentListResponse,
    DocumentApplyRequest, ExportRequest, DocumentUpdateTags,
    DocumentViewUrl, DocumentDownloadUrl, SetAccessModeRequest,
    DownloadHistoryItem, DownloadHistoryList, DocumentUploadResponse,
)
from app.schemas.query import (
    QueryRequest, QAResponse, SourceInfo,
    ConversationCreate, ConversationResponse, ConversationListResponse,
    ConversationMessageResponse, ConversationMessagesResponse,
)
from app.schemas.review import (
    ReviewAction, ApproveDocumentRequest, ApproveApplicationRequest,
    PendingDocument, PendingDocumentList,
    PendingApplication, PendingApplicationList,
    ReviewHistoryItem, ReviewHistoryList,
    ReviewerInfo, PendingApplicationCountResponse,
    ReviewDocumentResponse,
)
from app.schemas.audit import AuditLogQuery, AuditLogListResponse, AuditLogResponse
from app.schemas.tag import TagCreate, TagUpdate, TagsByTypeResponse
from app.schemas.favorite import FavoriteCreate
from app.schemas.grant import GrantRequest, BatchGrantRequest, UserFilters, TagFilters
from app.schemas.role import RoleCreate, RoleUpdate, RoleResponse

__all__ = [
    "LoginRequest", "LoginResponse", "UserInfo", "MenuResponse", "MenuItem",
    "UserCreate", "UserUpdate", "UserListResponse", "DataScopeResponse",
    "ChangePasswordRequest", "UpdatePhoneRequest", "UpdateDescriptionRequest",
    "DocumentUpload", "DocumentResponse", "DocumentListResponse",
    "DocumentApplyRequest", "ExportRequest", "DocumentUpdateTags",
    "DocumentViewUrl", "DocumentDownloadUrl", "SetAccessModeRequest",
    "DownloadHistoryItem", "DownloadHistoryList", "DocumentUploadResponse",
    "QueryRequest", "QAResponse", "SourceInfo",
    "ConversationCreate", "ConversationResponse", "ConversationListResponse",
    "ConversationMessageResponse", "ConversationMessagesResponse",
    "ReviewAction", "ApproveDocumentRequest", "ApproveApplicationRequest",
    "PendingDocument", "PendingDocumentList",
    "PendingApplication", "PendingApplicationList",
    "ReviewHistoryItem", "ReviewHistoryList",
    "ReviewerInfo", "PendingApplicationCountResponse",
    "ReviewDocumentResponse",
    "AuditLogQuery", "AuditLogListResponse", "AuditLogResponse",
    "TagCreate", "TagUpdate", "TagsByTypeResponse",
    "FavoriteCreate",
    "GrantRequest", "BatchGrantRequest", "UserFilters", "TagFilters",
    "RoleCreate", "RoleUpdate", "RoleResponse",
]
