from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, BigInteger, DateTime, func, UniqueConstraint, ForeignKey, Integer, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.document import Document

document_tags = Table(
    "document_tags",
    Base.metadata,
    Column("document_id", BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", BigInteger, ForeignKey("data_tags.id", ondelete="CASCADE"), primary_key=True),
)


class DataTagCategory(Base):
    """数据标签分类 - 类似部门管理，全局可自定义"""
    __tablename__ = "data_tag_categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    color: Mapped[str] = mapped_column(String(16), default="primary")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_system: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tags: Mapped[List["DataTag"]] = relationship(
        "DataTag", back_populates="category", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<DataTagCategory(id={self.id}, name={self.name}, code={self.code})>"


class DataTag(Base):
    """数据标签值 - 属于某个分类"""
    __tablename__ = "data_tags"
    __table_args__ = (
        UniqueConstraint("category_id", "name", name="uq_category_tag_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("data_tag_categories.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    category: Mapped[DataTagCategory] = relationship("DataTagCategory", back_populates="tags", lazy="joined")
    documents: Mapped[List["Document"]] = relationship(
        "Document", secondary=document_tags, back_populates="tags", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<DataTag(id={self.id}, category_id={self.category_id}, name={self.name})>"
