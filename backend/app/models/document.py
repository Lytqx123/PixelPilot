from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, BigInteger, DateTime, func, Text, SmallInteger, Integer, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.data_tag import document_tags

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.department import Department
    from app.models.data_tag import DataTag


ACCESS_MODE_DEPARTMENT_PUBLIC = "department_public"
ACCESS_MODE_APPLY_REQUIRED = "apply_required"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    uploader_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("departments.id"), nullable=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    model_tag: Mapped[str] = mapped_column(String(512), default="")
    region_tag: Mapped[str] = mapped_column(String(512), default="")
    doc_type_tag: Mapped[str] = mapped_column(String(512), default="")
    upload_type: Mapped[str] = mapped_column(String(16), default="regular", nullable=False)
    access_mode: Mapped[str] = mapped_column(String(32), default=ACCESS_MODE_DEPARTMENT_PUBLIC, nullable=False)
    is_public_to_all: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)  # 1=全员可见（超级管理员上传的文档），0=按部门/授权控制
    status: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)  # 0=待审核, 1=已通过, 2=已拒绝
    reviewer_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    review_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 解析后的分块数量,0=未解析
    is_parsed: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)  # 0=未解析, 1=已解析
    parsed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # 解析完成时间
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    uploader: Mapped[User] = relationship(
        "User", back_populates="documents", foreign_keys=[uploader_id], lazy="joined"
    )
    department: Mapped[Optional[Department]] = relationship("Department", foreign_keys=[department_id], lazy="joined")
    reviewer: Mapped[Optional[User]] = relationship("User", foreign_keys=[reviewer_id], lazy="joined")
    chunks: Mapped[List[DocumentChunk]] = relationship(
        "DocumentChunk", back_populates="document", lazy="selectin", cascade="all, delete-orphan"
    )
    tags: Mapped[List["DataTag"]] = relationship(
        "DataTag", secondary=document_tags, back_populates="documents", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, name={self.name})>"


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("documents.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, default=0)
    paragraph: Mapped[str] = mapped_column(String(64), default="")
    vector_id: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id})>"