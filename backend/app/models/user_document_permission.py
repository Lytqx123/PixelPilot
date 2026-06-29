from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, BigInteger, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.document import Document


class UserDocumentPermission(Base):
    """超级管理员手动授权：指定用户对特定文档的直接访问权限（含有效期）"""
    __tablename__ = "user_document_permissions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("documents.id"), nullable=False, index=True)
    granted_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    permission_type: Mapped[str] = mapped_column(String(16), default="download", nullable=False)  # "view_only" | "download"
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship("User", foreign_keys=[user_id], lazy="joined")
    document: Mapped[Document] = relationship("Document", lazy="joined")
    granter: Mapped[User] = relationship("User", foreign_keys=[granted_by], lazy="joined")

    def __repr__(self):
        return f"<UserDocumentPermission(user={self.user_id}, doc={self.document_id})>"
