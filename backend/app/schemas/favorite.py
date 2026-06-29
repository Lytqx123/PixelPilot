from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class FavoriteCreate(BaseModel):
    document_id: int


class FavoriteResponse(BaseModel):
    id: int
    user_id: int
    document_id: int
    document_name: Optional[str] = ""
    file_size: Optional[int] = 0
    model_tag: Optional[str] = ""
    region_tag: Optional[str] = ""
    doc_type_tag: Optional[str] = ""
    status: Optional[int] = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}