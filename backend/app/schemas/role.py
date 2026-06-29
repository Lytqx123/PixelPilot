from typing import Optional
from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    role_code: str = Field(..., min_length=2, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")
    role_name: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = Field(default=None, max_length=255)
    department_id: int = Field(..., description="所属部门ID（必填）")


class RoleUpdate(BaseModel):
    role_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    description: Optional[str] = Field(default=None, max_length=255)
    department_id: Optional[int] = None


class RoleResponse(BaseModel):
    id: int
    role_code: str
    role_name: str
    description: Optional[str] = None
    is_system: bool = False
    user_count: int = 0
    department_id: Optional[int] = None
    department_name: str = ""

    model_config = {"from_attributes": True}
