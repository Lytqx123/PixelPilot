from typing import List, Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: int
    username: str
    real_name: str
    gender: str = ""
    phone: str = ""
    personal_description: str = ""
    role_code: str
    role_name: str
    department_id: Optional[int] = None
    department_name: str = ""
    status: int = 1

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_info: UserInfo


class MenuItem(BaseModel):
    key: str
    label: str
    icon: Optional[str] = None
    children: Optional[List["MenuItem"]] = None


class MenuResponse(BaseModel):
    menus: List[MenuItem]