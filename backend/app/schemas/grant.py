from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator


class TagFilters(BaseModel):
    model_tags: Optional[List[str]] = Field(None, description="车型标签（可多选）")
    region_tags: Optional[List[str]] = Field(None, description="区域标签（可多选）")
    doc_type_tags: Optional[List[str]] = Field(None, description="文档类型标签（可多选）")

    @model_validator(mode="after")
    def check_has_any_filter(self) -> "TagFilters":
        has_any = (
            bool(self.model_tags) or
            bool(self.region_tags) or
            bool(self.doc_type_tags)
        )
        if not has_any:
            raise ValueError("标签筛选至少需要提供一种标签类型")
        return self


class UserFilters(BaseModel):
    role_codes: Optional[List[str]] = Field(None, description="按角色筛选（可多选）")
    tag_filters: Optional[TagFilters] = Field(None, description="多条件标签作用域筛选")
    user_ids: Optional[List[int]] = Field(None, description="按员工ID精确指定（可多选）")

    @model_validator(mode="after")
    def check_has_any_condition(self) -> "UserFilters":
        has_any = (
            bool(self.role_codes) or
            bool(self.tag_filters) or
            bool(self.user_ids)
        )
        if not has_any:
            raise ValueError("至少需要提供一种员工筛选条件")
        return self


class GrantRequest(BaseModel):
    """单用户授权请求"""
    permission_type: Optional[str] = Field("download", description="授权类型: view_only / download")
    expires_at: Optional[str] = Field(None, description="授权到期时间（ISO格式，可选）")

    @field_validator("permission_type")
    @classmethod
    def validate_permission_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("view_only", "download"):
            raise ValueError('permission_type 只能是 "view_only" 或 "download"')
        return v

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        from datetime import datetime
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            raise ValueError("expires_at 必须是有效的 ISO 格式日期时间字符串")
        return v


class BatchGrantRequest(BaseModel):
    document_ids: List[int] = Field(..., description="要授权的文档ID列表（必填）")
    user_filters: UserFilters = Field(..., description="多条件员工筛选")
    permission_type: str = Field("download", description="授权类型: view_only / download")
    expires_at: Optional[str] = Field(None, description="授权到期时间（ISO格式，可选）")

    @field_validator("document_ids")
    @classmethod
    def validate_document_ids(cls, v: List[int]) -> List[int]:
        if not v:
            raise ValueError("document_ids 不能为空")
        if len(v) != len(set(v)):
            raise ValueError("document_ids 存在重复ID")
        return v

    @field_validator("permission_type")
    @classmethod
    def validate_permission_type(cls, v: str) -> str:
        if v not in ("view_only", "download"):
            raise ValueError('permission_type 只能是 "view_only" 或 "download"')
        return v

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        from datetime import datetime
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            raise ValueError("expires_at 必须是有效的 ISO 格式日期时间字符串")
        return v


class BatchGrantPreviewUser(BaseModel):
    id: int
    username: str
    real_name: str
    role_code: str
    department_name: Optional[str] = None


class BatchGrantPreviewResponse(BaseModel):
    total_users: int
    users: List[BatchGrantPreviewUser]
    total_documents: int
