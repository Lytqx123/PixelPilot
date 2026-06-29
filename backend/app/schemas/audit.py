from typing import Optional, Any, Dict, List
from datetime import datetime
from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    username: str = ""
    real_name: str = ""
    operation_type: str
    operation_content: Optional[Dict[str, Any]] = None
    ip_address: str = ""
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    total: int
    items: List[AuditLogResponse]


class AuditLogQuery(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=10000)
    user_id: Optional[int] = None
    operation_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None