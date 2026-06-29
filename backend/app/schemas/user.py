from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class DataScopeCreate(BaseModel):
    model_tag: str
    region_tag: str
    doc_type_tag: str


class DataScopeResponse(BaseModel):
    id: int
    model_tag: str
    region_tag: str
    doc_type_tag: str

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str
    password: str
    real_name: str
    gender: str = ""
    role_id: int
    department_id: Optional[int] = None
    phone: str = ""
    personal_description: str = ""
    data_scopes: List[DataScopeCreate] = []


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    gender: Optional[str] = None
    role_id: Optional[int] = None
    department_id: Optional[int] = None
    status: Optional[int] = None
    phone: Optional[str] = None
    data_scopes: Optional[List[DataScopeCreate]] = None


class UserResponse(BaseModel):
    id: int
    username: str
    real_name: str
    gender: str = ""
    phone: str = ""
    personal_description: str = ""
    role_id: int
    role_code: str = ""
    role_name: str = ""
    department_id: Optional[int] = None
    department_name: str = ""
    status: int
    data_scopes: List[DataScopeResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserDetailResponse(BaseModel):
    id: int
    username: str
    real_name: str
    gender: str = ""
    phone: str = ""
    personal_description: str = ""
    role_id: int
    role_code: str = ""
    role_name: str = ""
    department_id: Optional[int] = None
    department_name: str = ""
    status: int
    data_scopes: List[DataScopeResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    total: int
    items: List[UserResponse]


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=64)


class UpdatePhoneRequest(BaseModel):
    phone: str = Field(..., max_length=32)


class UpdateDescriptionRequest(BaseModel):
    personal_description: str = Field(default="", max_length=512)