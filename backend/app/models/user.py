from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, BigInteger, SmallInteger, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.role import Role
    from app.models.department import Department
    from app.models.document import Document


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    real_name: Mapped[str] = mapped_column(String(64), nullable=False)
    gender: Mapped[str] = mapped_column(String(8), default="", nullable=False)  # 男/女/ (空为未设置)
    phone: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    personal_description: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("roles.id"), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("departments.id"), nullable=True)
    status: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)  # 1=正常, 0=禁用
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    role: Mapped[Role] = relationship("Role", back_populates="users", lazy="selectin")
    department: Mapped[Optional[Department]] = relationship("Department", back_populates="users", foreign_keys=[department_id], lazy="selectin")
    data_scopes: Mapped[List[UserDataScope]] = relationship(
        "UserDataScope", back_populates="user", lazy="selectin", cascade="all, delete-orphan"
    )
    documents: Mapped[List[Document]] = relationship(
        "Document", back_populates="uploader", foreign_keys="Document.uploader_id", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"


class UserDataScope(Base):
    __tablename__ = "user_data_scopes"
    __table_args__ = (
        UniqueConstraint("user_id", "model_tag", "region_tag", "doc_type_tag", name="uq_user_scope"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    model_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    region_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_type_tag: Mapped[str] = mapped_column(String(64), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="data_scopes")

    def __repr__(self) -> str:
        return f"<UserDataScope(id={self.id}, user_id={self.user_id})>"