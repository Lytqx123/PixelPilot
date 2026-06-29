from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class TagCreate(BaseModel):
    tag_type: str = Field(..., description="标签类型: model / region / doc_type")
    tag_value: str = Field(..., min_length=1, max_length=64, description="标签值")


class TagUpdate(BaseModel):
    tag_value: str = Field(..., min_length=1, max_length=64, description="新标签值")


class TagResponse(BaseModel):
    id: int
    tag_type: str
    tag_value: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TagListResponse(BaseModel):
    total: int
    items: list[TagResponse]


class TagsByTypeResponse(BaseModel):
    model_tags: list[str] = []
    region_tags: list[str] = []
    doc_type_tags: list[str] = []


# ==================== 数据标签分类（新） ====================

class DataTagCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="分类名称")
    code: str = Field(..., min_length=1, max_length=64, description="分类编码（英文/数字/下划线）")
    description: Optional[str] = Field(None, max_length=255, description="描述")
    color: str = Field("primary", max_length=16, description="标签颜色主题: primary/success/warning/danger/info")
    sort_order: int = Field(0, description="排序顺序")


class DataTagCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64, description="分类名称")
    description: Optional[str] = Field(None, max_length=255, description="描述")
    color: Optional[str] = Field(None, max_length=16, description="标签颜色主题")
    sort_order: Optional[int] = Field(None, description="排序顺序")


class DataTagCategoryResponse(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    color: str
    sort_order: int
    is_system: int
    tag_count: int = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DataTagCategoryDetailResponse(DataTagCategoryResponse):
    tags: List["DataTagResponse"] = []


# ==================== 数据标签值（新） ====================

class DataTagCreate(BaseModel):
    category_id: int = Field(..., description="所属分类ID")
    name: str = Field(..., min_length=1, max_length=64, description="标签名称")
    description: Optional[str] = Field(None, max_length=255, description="描述")
    sort_order: int = Field(0, description="排序顺序")


class DataTagUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64, description="标签名称")
    description: Optional[str] = Field(None, max_length=255, description="描述")
    sort_order: Optional[int] = Field(None, description="排序顺序")


class DataTagResponse(BaseModel):
    id: int
    category_id: int
    name: str
    description: Optional[str] = None
    sort_order: int
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DataTagSimpleResponse(BaseModel):
    """简化版标签响应，包含分类信息，用于文档列表展示"""
    id: int
    category_id: int
    name: str
    category_name: str = ""
    category_code: str = ""
    color: str = "primary"


class DataTagListResponse(BaseModel):
    total: int
    items: List[DataTagResponse]


DataTagCategoryDetailResponse.model_rebuild()